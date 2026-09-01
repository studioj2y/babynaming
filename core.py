import os, json
from itertools import permutations
from lunar_python import Solar
import ai

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

GAN_WX = {'甲':'木','乙':'木','丙':'火','丁':'火','戊':'土','己':'土','庚':'金','辛':'金','壬':'水','癸':'水'}
ZHI_WX = {'子':'水','丑':'土','寅':'木','卯':'木','辰':'土','巳':'火','午':'火','未':'土','申':'金','酉':'金','戌':'土','亥':'水'}
ELES = ['金','木','水','火','土']

ZODIAC_PREF = {
 '鼠':{'xi':['宀','冖','米','豆','禾','田','艹'],'ji':['日','火']},
 '牛':{'xi':['艹','田','车','宀'],'ji':['羊','马','刀']},
 '虎':{'xi':['山','林','王','木'],'ji':['申','辶','人']},
 '兔':{'xi':['艹','禾','木','宀'],'ji':['酉','刀']},
 '龙':{'xi':['氵','雨','云','日'],'ji':['戌','山']},
 '蛇':{'xi':['艹','虫','田','木'],'ji':['猪','虎']},
 '马':{'xi':['艹','巾','纟','木'],'ji':['子','牛']},
 '羊':{'xi':['艹','禾','木','宀'],'ji':['丑','鼠']},
 '猴':{'xi':['木','人','言','宀'],'ji':['虎','猪']},
 '鸡':{'xi':['禾','米','宀','冊'],'ji':['兔','犬']},
 '狗':{'xi':['亻','宀','马'],'ji':['龙','鸡']},
 '猪':{'xi':['宀','冖','豆','米'],'ji':['蛇','猴']},
}

NEG_HOMO = ['baichi','sharen','fengzi','shaizi','aocao','fanren','yangwei','duziteng','shabi','tama','nima','wangba']
# 明显不宜作姓氏的脏字/ insult 字符（轻量校验）
DIRTY_CHARS = set('傻滚操屁屎尿疯贱婊')
# 高频用字（重名近似：含其一则重名概率偏高）
HIGH_FREQ = set('伟芳娜秀英华建国婷浩鑫梓涵轩宇睿欣怡晨子凡一')

DEFAULT_WEIGHTS = {
 'wuxing':0.20,'zodiac':0.12,'pronounce':0.18,'homophone':0.15,'meaning':0.15,'stroke':0.10,'gender':0.10
}

_CHARS = None
_GOOD = None

def chars():
    global _CHARS
    if _CHARS is None:
        with open(os.path.join(DATA, 'chars.json'), encoding='utf-8') as f:
            _CHARS = json.load(f)
    return _CHARS

def good():
    global _GOOD
    if _GOOD is None:
        with open(os.path.join(DATA, 'good_chars.json'), encoding='utf-8') as f:
            _GOOD = json.load(f)
    return _GOOD

def to_ascii(s):
    return ''.join(ch for ch in (s or '') if ord(ch) < 128).lower()

def analyze_birth(year, month, day, hour):
    solar = Solar.fromYmdHms(year, month, day, hour, 0, 0)
    lunar = solar.getLunar()
    ec = lunar.getEightChar()
    gz = [ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()]
    flat = ''.join(gz)
    counts = {e: 0 for e in ELES}
    for ch in flat:
        if ch in GAN_WX:
            counts[GAN_WX[ch]] += 1
        elif ch in ZHI_WX:
            counts[ZHI_WX[ch]] += 1
    missing = [e for e in ELES if counts[e] == 0]
    if missing:
        need = missing
    else:
        mn = min(counts.values())
        need = [e for e in ELES if counts[e] == mn]
    zodiac = lunar.getYearShengXiao()
    return {'gz': gz, 'counts': counts, 'need': need, 'zodiac': zodiac}

# ---------- 姓氏校验与构造 ----------
def validate_surname(s):
    s = (s or '').strip()
    if not s:
        return '姓氏不能为空'
    if len(s) > 2:
        return '姓氏不能超过 2 个字'
    if not all('\u4e00' <= c <= '\u9fff' for c in s):
        return '姓氏须为汉字'
    if any(c in DIRTY_CHARS for c in s):
        return '姓氏含有不雅用字，请更换'
    return None

def build_surname(father, mother, mode):
    father = (father or '').strip()
    mother = (mother or '').strip()
    if mode == 'M':
        return mother
    if mode == 'B':
        return father + mother  # 父姓为先，母姓其后（复姓）
    return father  # 默认随父姓

def surname_info(surname):
    """返回每个字的 (py, tone, initial, radical, wx, stroke)"""
    ch = chars()
    out = []
    for c in surname:
        info = ch.get(c)
        if info:
            out.append((info['py'].split(',')[0], info['tone'], info['initial'], info['radical'], info['wx'], info['stroke']))
        else:
            out.append((c, 0, '', '', '土', 0))
    return out

# ---------- 评分（泛化支持变长） ----------
def score_wuxing(wx_list, need, has_birth):
    if not has_birth:
        return 60 if len(set(wx_list)) == 1 else 80
    fill = sum(1 for w in wx_list if w in need)
    return {len(wx_list): 100, len(wx_list)-1: 72, 0: 44}.get(fill, 50)

def score_zodiac(radicals, zodiac):
    pref = ZODIAC_PREF.get(zodiac)
    if not pref:
        return 80
    bonus = 0
    for r in radicals:
        if r in pref['xi']:
            bonus += 12
        if r in pref['ji']:
            bonus -= 18
    return max(0, min(100, 70 + bonus))

def score_pronounce(tones, initials):
    n = len(tones)
    s = 70
    real = [t for t in tones if t != 0]
    if real and all(t == real[0] for t in real):
        s -= 15
    else:
        dist = len(set(real))
        s += min(12, (dist - 1) * 6)
    def ping(x):
        return x in (1, 2)
    for i in range(1, n):
        if tones[i-1] and tones[i] and ping(tones[i-1]) != ping(tones[i]):
            s += 4
    for i in range(1, n):
        if initials[i-1] and initials[i] and initials[i-1] == initials[i]:
            s -= 18
    return max(0, min(100, s))

def score_homophone(full_py):
    for neg in NEG_HOMO:
        if neg in full_py:
            return 20
    return 100

def score_meaning(tags, chosen):
    if not chosen:
        return 86
    hit = 1 if (set(tags) & set(chosen)) else 0
    return min(100, 82 + 10 * hit)

def score_stroke(total):
    if total <= 26:
        return 100
    return max(0, 100 - (total - 26) * 3)

def score_gender(genders, req):
    bad = 0
    for g in genders:
        if req == 'M' and g == 'F':
            bad += 1
        if req == 'F' and g == 'M':
            bad += 1
    return {0: 100, 1: 55, 2: 25}.get(bad, 25)

def explain(o, meta, mode):
    out = []
    given = o['given_chars']
    wx_list = o['given_wx']
    if meta.get('has_birth'):
        need = meta['need']
        fill = [w for w in wx_list if w in need]
        if len(fill) == len(wx_list):
            txt = f"「{o['given']}」各字五行皆补命中所缺之{'/'.join(need)}，五行相生，根基稳厚，一生多得帮扶。"
        elif fill:
            txt = f"其中「{''.join(c for c,w in zip(given,wx_list) if w in need)}」恰补所缺之{'/'.join(need)}，与八字相扶；余字悄然调和，气运平顺。"
        else:
            txt = f"此名五行以{'/'.join(wx_list)}搭配，中和温润，不偏不倚，自有从容之象。"
    else:
        txt = f"「{o['given']}」五行属{'/'.join(wx_list)}，刚柔相映（未提供生辰，仅作常规搭配参考）。"
    out.append({'key': 'wuxing', 'label': '五行调和', 'text': txt})

    if meta.get('zodiac'):
        z = meta['zodiac']
        out.append({'key': 'zodiac', 'label': '生肖相宜',
                    'text': f"生肖{z}与名字部首气韵相合，寓意得天地庇佑，安然顺遂、自在无忧。"})
    else:
        out.append({'key': 'zodiac', 'label': '生肖相宜',
                    'text': "属相之宜留待添上生辰后再细参，此名意象本就周正安稳。"})

    out.append({'key': 'pronounce', 'label': '音律朗朗',
                'text': "全名声调起伏有致，念来朗朗上口、清亮悦耳，令人过耳不忘。"})
    out.append({'key': 'homophone', 'label': '读音清正',
                'text': "细细推敲，全名并无不良谐音，落落大方，叫得响亮得体。"})

    mean_parts = [f"「{c}」{m}" for c, m in zip(given, o['given_mean']) if m]
    if mean_parts:
        mean_txt = '；'.join(mean_parts)
        extra = "父母二姓皆镌于此名之中，血脉亲情一目了然。" if mode == 'B' else ""
        out.append({'key': 'meaning', 'label': '字义寄意',
                    'text': f"{mean_txt}。意境相映，寄意深远，足见长辈拳拳之心。{extra}"})
    else:
        out.append({'key': 'meaning', 'label': '字义寄意',
                    'text': "用字雅正，寄意自见；长辈之情，尽在其中。"})

    tot = o['given_stroke']
    out.append({'key': 'stroke', 'label': '字形匀称',
                'text': f"名字共 {tot} 画（不含姓氏），疏密得当，孩童习书流畅美观，写得顺手也记得牢。"})

    gd = '男孩' if o['req_gender'] == 'M' else ('女孩' if o['req_gender'] == 'F' else '孩子')
    out.append({'key': 'gender', 'label': '气韵契合',
                'text': f"字形气韵契合{gd}，温润而有筋骨，愈叫愈觉妥帖。"})

    # —— 能力2/3 本地近似（不耗 AI，明确标注）——
    hit_freq = [c for c in given if c in HIGH_FREQ]
    if hit_freq:
        out.append({'key': 'dup', 'label': '重名（近似）', 'approx': True,
                    'text': f"「{''.join(hit_freq)}」属较常见用字，重名概率略高；若求独特可换更冷僻雅字。（此为本地近似估算，真实重名率需接入户籍数据）"})
    else:
        out.append({'key': 'dup', 'label': '重名（近似）', 'approx': True,
                    'text': "用字相对独特，重名概率较低，不易与他人撞名。（此为本地近似估算，真实重名率需接入户籍数据）"})
    if o.get('dims', {}).get('homophone', 100) <= 20:
        out.append({'key': 'net', 'label': '撞梗（本地）', 'approx': True,
                    'text': "检出潜在不良谐音，建议再斟酌；网络撞梗/负面人物检测需联网检索，待后续接入。"})
    return out

def _build_name(surname, given_chars, given_info, given_it, gender, birth, need, zodiac,
                weights, s_py, s_tones, s_ini, mode, mother_echo_radical):
    """由一组「名」字符构造完整名字对象（generate 与 analyze 共用）。"""
    wx_list = [gi['wx'] for gi in given_info]
    radicals = [gi['radical'] for gi in given_info]
    tones = s_tones + [gi['tone'] for gi in given_info]
    initials = s_ini + [gi['initial'] for gi in given_info]
    full_py = to_ascii(s_py + ''.join(gi['py'].split(',')[0] for gi in given_info))
    g_tags = []
    for gi in given_it:
        g_tags += gi['t']
    g_mean = [gi['m'] for gi in given_it]
    g_stroke = sum(gi['stroke'] for gi in given_info)
    g_gender = [gi['g'] for gi in given_it]

    echo_bonus = 0
    if mother_echo_radical and any(r == mother_echo_radical for r in radicals):
        echo_bonus = 6

    dims = {
        'wuxing': score_wuxing(wx_list, need, birth is not None),
        'zodiac': score_zodiac(radicals, zodiac),
        'pronounce': score_pronounce(tones, initials),
        'homophone': score_homophone(full_py),
        'meaning': min(100, round(sum(score_meaning(gi['t'], []) for gi in given_it) / len(given_it)) + echo_bonus),
        'stroke': score_stroke(g_stroke),
        'gender': score_gender(g_gender, gender),
    }
    total = sum(dims[k] * weights[k] for k in weights) + echo_bonus * 0.05
    name = surname + ''.join(given_chars)
    o = {
        'name': name, 'surname': surname, 'given': ''.join(given_chars),
        'py': s_py.split() + [gi['py'].split(',')[0] for gi in given_info],
        'py_str': s_py + ' ' + ' '.join(gi['py'].split(',')[0] for gi in given_info),
        'given_chars': given_chars, 'given_wx': wx_list, 'given_mean': g_mean,
        'given_stroke': g_stroke, 'tags': sorted(set(g_tags)),
        'req_gender': gender, 'dims': dims, 'total': round(total, 1),
    }
    o['explain'] = explain(o, {'has_birth': birth is not None, 'need': need, 'zodiac': zodiac}, mode)
    o['dup_info'] = ('unique' if not any(c in HIGH_FREQ for c in given_chars) else 'common')
    return o

def generate(father, mother, mode, name_len, gender, birth, tags, avoid, topn=24, weights=None):
    ef = validate_surname(father)
    em = validate_surname(mother)
    if ef or em:
        return [], {'error': ef or em}
    surname = build_surname(father, mother, mode)
    given_len = name_len - len(surname)
    if given_len < 1:
        return [], {'error': f'当前姓氏共 {len(surname)} 字，无法组成 {name_len} 字名（名字至少需 1 个名），请改选字数或姓氏方式。'}

    gl = good()
    ch = chars()
    pool = []
    for it in gl:
        c = it['c']
        if c in surname:
            continue
        if avoid and c in avoid:
            continue
        g = it['g']
        if gender == 'M' and g == 'F':
            continue
        if gender == 'F' and g == 'M':
            continue
        if tags and not (set(it['t']) & set(tags)):
            continue
        info = ch.get(c)
        if not info:
            continue
        pool.append((c, it, info))

    if not pool:
        return [], {'error': '当前筛选（性别/寓意）下可选字过少，请放宽寓意选择或调整性别。'}

    has_birth = birth is not None
    need = birth['need'] if has_birth else None
    zodiac = birth['zodiac'] if has_birth else None
    w = weights or DEFAULT_WEIGHTS

    mother_echo_radical = None
    if mode == 'B' and mother:
        mi = ch.get(mother[0])
        if mi:
            mother_echo_radical = mi['radical']

    def base(it, info):
        s = 70
        if tags and (set(it['t']) & set(tags)):
            s += 20
        if gender in ('M', 'F') and it['g'] == gender:
            s += 10
        if has_birth and info['wx'] in need:
            s += 12
        return s
    ranked = sorted(pool, key=lambda x: base(x[1], x[2]), reverse=True)
    M = min(40, len(ranked))
    top = ranked[:M]

    s_info = surname_info(surname)
    s_py = ''.join(p[0] for p in s_info)
    s_tones = [p[1] for p in s_info]
    s_ini = [p[2] for p in s_info]

    names = []
    if given_len == 1:
        combos = [[x] for x in top]
    else:
        combos = list(permutations(top, given_len))

    for combo in combos:
        given_chars = [x[0] for x in combo]
        given_info = [x[2] for x in combo]
        given_it = [x[1] for x in combo]
        o = _build_name(surname, given_chars, given_info, given_it, gender, birth, need, zodiac,
                        w, s_py, s_tones, s_ini, mode, mother_echo_radical)
        names.append(o)

    names.sort(key=lambda x: -x['total'])
    meta = {'has_birth': has_birth, 'need': need, 'zodiac': zodiac,
            'pool_size': len(pool), 'surname': surname, 'mode': mode,
            'name_len': name_len}
    return names[:topn], meta

# ---------- 候选名字分析（能力 B：帮我观测我的候选名字） ----------
def analyze_given_name(name, gender, birth, weights=None):
    raw = (name or '').strip()
    given = [c for c in raw if '\u4e00' <= c <= '\u9fff']
    if not given:
        return [], {'error': '请输入中文名字（如：林婉婷）'}
    ch = chars()
    glmap = {it['c']: it for it in good()}
    given_info, given_it = [], []
    for c in given:
        info = ch.get(c)
        if not info:
            info = {'py': c, 'tone': 0, 'radical': '', 'stroke': 0, 'wx': '土', 'initial': '', 'final': ''}
        given_info.append(info)
        gi = glmap.get(c)
        given_it.append(gi if gi else {'t': [], 'm': '', 'g': 'U'})

    w = weights or DEFAULT_WEIGHTS
    has_birth = birth is not None
    need = birth['need'] if has_birth else None
    zodiac = birth['zodiac'] if has_birth else None
    o = _build_name('', given, given_info, given_it, gender, birth, need, zodiac,
                    w, '', [], [], None, None)
    meta = {'has_birth': has_birth, 'need': need, 'zodiac': zodiac,
            'pool_size': len(given), 'surname': raw, 'mode': None,
            'name_len': len(given), 'analyzed': True}
    return [o], meta

# ---------- 能力5：自由期许 → 标签映射（AI 优先，失败回退关键词） ----------
def map_free_text_to_tags(free_text):
    picks = ai.map_free_text(free_text, TAGS_VOCAB)
    if picks:
        return picks
    # 回退：关键词包含匹配
    return [t for t in TAGS_VOCAB if t in (free_text or '')]

# ---------- 能力1：整盘 AI 积极解读（AI 优先，失败返回 None） ----------
def ai_review_for_name(name_obj, meta):
    return ai.ai_review(name_obj['name'], name_obj['req_gender'],
                        meta.get('zodiac'), meta.get('need'), name_obj.get('dims'))

TAGS_VOCAB = ['智慧','才华','健康','安宁','光明','品德','勇敢','温婉','灵秀','仁愛','喜悦','自由','俊逸','坚韧']
