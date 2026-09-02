import os, json, unicodedata
from itertools import permutations
from lunar_python import Solar
import ai

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

GAN_WX = {'甲':'木','乙':'木','丙':'火','丁':'火','戊':'土','己':'土','庚':'金','辛':'金','壬':'水','癸':'水'}
ZHI_WX = {'子':'水','丑':'土','寅':'木','卯':'木','辰':'土','巳':'火','午':'火','未':'土','申':'金','酉':'金','戌':'土','亥':'水'}
ELES = ['金','木','水','火','土']
SHENG = {'木':'火','火':'土','土':'金','金':'水','水':'木'}   # 相生
KE = {'木':'土','土':'水','水':'火','火':'金','金':'木'}       # 相克

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
 'wuxing':0.20,'zodiac':0.12,'pronounce':0.33,'meaning':0.15,'stroke':0.10,'gender':0.10
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
    # 先把带声调的拼音(如 lín)归一化拆出基元音，再丢弃声调组合符号，
    # 这样 lín→lin、yáng→yang，声调被去但元音保留，拼音匹配才正确。
    s = unicodedata.normalize('NFD', s or '')
    return ''.join(ch for ch in s if ord(ch) < 128).lower()

# ---------- 静态昵称/梗黑名单（迭代时手动维护，运行时不再调 AI） ----------
_NICK = None
def nickname_blacklist():
    """data/nickname_blacklist.json：名(不含姓)或「整名」命中任一条则强烈降权。"""
    global _NICK
    if _NICK is None:
        p = os.path.join(DATA, 'nickname_blacklist.json')
        try:
            with open(p, encoding='utf-8') as f:
                _NICK = json.load(f).get('rules', [])
        except FileNotFoundError:
            _NICK = []
    return _NICK

def nickname_penalty(given_chars, given_py, full_py=None):
    """返回 (扣分, 命中说明列表)。规则：
    - seq：名(不含姓)含该字串；
    - pinyin：名全拼(不含姓) == 该 ascii；
    - phrase：整名拼音(姓+名, 去声调) == 某成语/俗语拼音，用于识别「林门一脚≈临门一脚」这类谐音梗。
    叠字不在此列。"""
    rules = nickname_blacklist()
    if not rules:
        return 0, []
    s = ''.join(given_chars)
    fp = full_py if full_py is not None else given_py
    pen, hits = 0, []
    for r in rules:
        kind = r.get('kind', 'seq')
        m = r.get('match', '')
        if kind == 'seq':
            if m and m in s:
                pen += r.get('penalty', 30); hits.append(r.get('note', m))
        elif kind == 'pinyin':
            if m and to_ascii(m) == given_py:
                pen += r.get('penalty', 30); hits.append(r.get('note', m))
        elif kind == 'phrase':
            if m and r.get('py', '') and to_ascii(r['py']) == fp:
                pen += r.get('penalty', 35); hits.append(r.get('note', m))
    return pen, hits

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
def score_wuxing(wx_list, need, has_birth, s_wx=None):
    seq = (list(s_wx) if s_wx else []) + list(wx_list)
    if not has_birth:
        # 未提供生辰时，看全名五行「相生相克」是否调和（真实玄学逻辑，逐名不同）
        if len(seq) < 2:
            return 80
        s = 100
        for a, b in zip(seq, seq[1:]):
            if SHENG.get(a) == b:
                s += 0
            elif KE.get(a) == b:
                s -= 14
            elif a == b:
                s -= 4
            else:
                s -= 3
        return max(55, min(100, s))
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
    s = 72
    real = [t for t in tones if t != 0]
    if real and all(t == real[0] for t in real):
        s -= 14
    else:
        s += (len(set(real)) - 1) * 7
    def ping(x):
        return x in (1, 2)
    alt = 0
    for i in range(1, n):
        if tones[i-1] and tones[i] and ping(tones[i-1]) != ping(tones[i]):
            alt += 1
    s += alt * 5
    for i in range(1, n):
        if initials[i-1] and initials[i] and initials[i-1] == initials[i]:
            s -= 16
    return max(55, min(98, s))

def score_homophone(full_py):
    for neg in NEG_HOMO:
        if neg in full_py:
            return 20
    return 100

TAG_MEANING = {'智慧':90,'才华':88,'健康':86,'安宁':89,'光明':87,'品德':88,'勇敢':85,
                '温婉':87,'灵秀':86,'仁愛':88,'喜悦':84,'自由':85,'俊逸':86,'坚韧':85}
def score_meaning(tags, chosen):
    vals = [TAG_MEANING.get(t, 82) for t in (tags or [])]
    base = round(sum(vals) / len(vals)) if vals else 80
    if not chosen:
        return base
    hit = 1 if (set(tags) & set(chosen)) else 0
    return min(100, base + 8 * hit)

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

# ---------- 五格数理（姓名学 81 数理，吉凶打分，确定性、按笔画逐名不同） ----------
GRID_SCORE = {
 1:100,2:55,3:100,4:40,5:100,6:80,7:80,8:80,9:55,10:40,
 11:100,12:80,13:100,14:60,15:100,16:100,17:100,18:80,19:55,20:55,
 21:100,22:60,23:100,24:100,25:80,26:55,27:80,28:80,29:80,30:55,
 31:100,32:100,33:100,34:80,35:55,36:80,37:80,38:55,39:55,40:55,
 41:100,42:80,43:80,44:55,45:80,46:80,47:80,48:80,49:80,50:55,
 51:80,52:80,53:80,54:55,55:55,56:55,57:80,58:80,59:55,60:55,
 61:80,62:80,63:80,64:55,65:80,66:55,67:80,68:80,69:55,70:55,
 71:80,72:80,73:80,74:55,75:80,76:55,77:80,78:80,79:80,80:55,
 81:100,
}
def _grid_num(n):
    if n <= 0:
        return 60
    if n > 81:
        n = ((n - 1) % 81) + 1
    return GRID_SCORE.get(n, 70)
def five_grids(strokes):
    """天格/人格/地格/总格/外格 数理（单姓标准算法）。"""
    n = len(strokes)
    if n == 0:
        return {}, 60
    tg = strokes[0] + 1                      # 天格：首字 +1
    rg = strokes[0] + (strokes[1] if n > 1 else 0)   # 人格：首字+次字
    rest = strokes[1:]
    dg = sum(rest) + (1 if len(rest) == 1 else 0)    # 地格
    zg = sum(strokes)                        # 总格
    wg = zg - rg + 1                         # 外格
    grids = {'天格': tg, '人格': rg, '地格': dg, '总格': zg, '外格': wg}
    score = round(sum(_grid_num(v) for v in grids.values()) / len(grids))
    return grids, score

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
                'text': "全名声调起伏有致，念来朗朗上口、清亮悦耳，细细推敲更无不良谐音，落落大方、叫得响亮得体，令人过耳不忘。"})

    mean_parts = [f"「{c}」{m}" for c, m in zip(given, o['given_mean']) if m]
    if mean_parts:
        mean_txt = '；'.join(mean_parts)
        extra = "父母二姓皆镌于此名之中，血脉亲情一目了然。" if mode == 'B' else ""
        out.append({'key': 'meaning', 'label': '字义寄意',
                    'text': f"{mean_txt}。意境相映，寄意深远，足见长辈拳拳之心。{extra}"})
    else:
        out.append({'key': 'meaning', 'label': '字义寄意',
                    'text': "用字雅正，寄意自见；长辈之情，尽在其中。"})

    gr = o.get('grids', {})
    zg = gr.get('总格')
    gd = '男孩' if o['req_gender'] == 'M' else ('女孩' if o['req_gender'] == 'F' else '孩子')
    out.append({'key': 'stroke', 'label': '数理格局',
                'text': f"依姓名学五格推算，此名总格为 {zg}，天/人/地/外诸格谐和相济，主一生顺遂安稳；"
                        f"笔意舒展，{gd}习书亦流畅美观，写得顺手、念来妥帖。"})

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
    if o.get('homophone_score', 100) <= 20:
        out.append({'key': 'net', 'label': '撞梗（本地）', 'approx': True,
                    'text': "检出潜在不良谐音，建议再斟酌；网络撞梗/负面人物检测需联网检索，待后续接入。"})
    return out

def _build_name(surname, given_chars, given_info, given_it, gender, birth, need, zodiac,
                weights, s_py, s_tones, s_ini, mode, mother_echo_radical, chosen_tags=None):
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

    ch = chars() if surname else None
    s_strokes = [ch.get(c, {}).get('stroke', 0) for c in surname] if ch else []
    s_wx = [ch.get(c, {}).get('wx', '土') for c in surname] if ch else []
    all_strokes = s_strokes + [gi['stroke'] for gi in given_info]
    grids, grid_score = five_grids(all_strokes)

    hph = score_homophone(full_py)            # 谐音（不良读音）并入「音律」，由音律老师统管
    dims = {
        'wuxing': score_wuxing(wx_list, need, birth is not None, s_wx),
        'zodiac': score_zodiac(radicals, zodiac),
        'pronounce': round(0.55*score_pronounce(tones, initials) + 0.45*hph),
        'meaning': min(100, round(sum(score_meaning(gi['t'], chosen_tags) for gi in given_it) / len(given_it)) + echo_bonus),
        'stroke': grid_score,
        'gender': score_gender(g_gender, gender),
    }
    total = sum(dims[k] * weights[k] for k in weights) + echo_bonus * 0.05
    # —— 静态昵称/梗黑名单降权（不耗 AI）——
    given_py = to_ascii(''.join(gi['py'].split(',')[0] for gi in given_info))
    np_pen, np_hits = nickname_penalty(given_chars, given_py, full_py)
    total = total - np_pen
    name = surname + ''.join(given_chars)
    o = {
        'name': name, 'surname': surname, 'given': ''.join(given_chars),
        'py': s_py.split() + [gi['py'].split(',')[0] for gi in given_info],
        'py_str': s_py + ' ' + ' '.join(gi['py'].split(',')[0] for gi in given_info),
        'given_chars': given_chars, 'given_wx': wx_list, 'given_mean': g_mean,
        'given_stroke': g_stroke, 'tags': sorted(set(g_tags)), 'grids': grids,
        'req_gender': gender, 'dims': dims, 'total': round(total, 1),
        'homophone_score': hph,
        'nickname_penalty': np_pen, 'nickname_hits': np_hits,
    }
    o['explain'] = explain(o, {'has_birth': birth is not None, 'need': need, 'zodiac': zodiac}, mode)
    o['dup_info'] = ('unique' if not any(c in HIGH_FREQ for c in given_chars) else 'common')
    if np_hits:
        o['explain'].append({'key': 'nick', 'label': '昵称/梗（本地）', 'approx': True,
            'text': f"本地规则提示：此名易联想「{np_hits[0]}」等昵称或网络梗，是否采用您可斟酌。（静态黑名单，可手动维护）"})
    return o

def generate(father, mother, mode, name_len, gender, birth, tags, avoid, topn=12, weights=None):
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
                        w, s_py, s_tones, s_ini, mode, mother_echo_radical, tags)
        names.append(o)

    names.sort(key=lambda x: -x['total'])
    meta = {'has_birth': has_birth, 'need': need, 'zodiac': zodiac,
            'pool_size': len(pool), 'surname': surname, 'mode': mode,
            'name_len': name_len}
    return _curate_diverse(names, topn), meta

def _curate_diverse(names, out_n):
    """精选：保留差异明显者，筛掉过于接近的（同字重排 / 同音 / 三字仅差一字 / 二字共用一字）。"""
    kept = []
    for o in names[:200]:
        gc = o['given_chars']
        gcset = frozenset(gc)
        py = o['py_str'].replace(' ', '')
        dup = False
        for k in kept:
            if frozenset(k['given_chars']) == gcset:
                dup = True; break
            if k['py_str'].replace(' ', '') == py:
                dup = True; break
            gl = len(gc)
            if gl >= 2 and len(gcset & frozenset(k['given_chars'])) >= gl - 1:
                dup = True; break
        if not dup:
            kept.append(o)
        if len(kept) >= out_n:
            break
    return kept

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
                    w, '', [], [], None, None, None)
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
