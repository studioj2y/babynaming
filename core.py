import os, json, unicodedata, random
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

# 调候用神：依出生月令寒热燥湿取用（传统姓名学「调候为急」）。月支 → (宜补五行, 缘由)
# 冬(亥子丑)寒需火暖、夏(巳午未)热需水润、春(寅卯辰)木旺佐金裁、秋(申酉戌)金旺需水泄。
DIAO_HOU = {
 '寅': (['火','金'], '初春寒未尽，需火暖局；木渐旺，佐金裁剪'),
 '卯': (['金','火'], '仲春木最旺，需金裁剪；微寒仍喜火'),
 '辰': (['金','水'], '季春土旺，金泄土、水润局'),
 '巳': (['水'], '初夏火炎，需水济暑'),
 '午': (['水'], '盛夏火最旺，需水制炎'),
 '未': (['水'], '夏末土燥火余，需水润局'),
 '申': (['水'], '初秋金旺，需水泄润'),
 '酉': (['水'], '仲秋金最旺，需水泄金'),
 '戌': (['水','木'], '季秋土燥金相，水润、木疏'),
 '亥': (['火'], '初冬水旺，需火暖局'),
 '子': (['火'], '仲冬水最旺，需火调候'),
 '丑': (['火'], '冬末寒土，需火暖局'),
}

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

# ---------- 生肖 三合 / 六合 / 六冲 / 六害（姓名学生肖法的完整骨架，用生肖名） ----------
# 三合（四组）：猴鼠龙 / 猪兔羊 / 虎马狗 / 蛇鸡牛
# 六合：鼠牛 虎猪 兔狗 龙鸡 蛇猴 马羊
# 六冲：鼠马 牛羊 虎猴 兔鸡 龙狗 蛇猪
# 六害：鼠羊 牛马 虎蛇 兔龙 猴猪 鸡狗
SANHE = [('猴','鼠','龙'), ('猪','兔','羊'), ('虎','马','狗'), ('蛇','鸡','牛')]
LIUHE = [('鼠','牛'), ('虎','猪'), ('兔','狗'), ('龙','鸡'), ('蛇','猴'), ('马','羊')]
LIUCHONG = [('鼠','马'), ('牛','羊'), ('虎','猴'), ('兔','鸡'), ('龙','狗'), ('蛇','猪')]
LIUHAI = [('鼠','羊'), ('牛','马'), ('虎','蛇'), ('兔','龙'), ('猴','猪'), ('鸡','狗')]
# 生肖 → 代表部首（名字字形判定用，地支字）
ZODIAC_RAD = {'鼠':'子','牛':'丑','虎':'寅','兔':'卯','龙':'辰','蛇':'巳','马':'午','羊':'未','猴':'申','鸡':'酉','狗':'戌','猪':'亥'}
# 常见字形代指（五行/意象部首，补全「三合六合」在名中的呈现），键用生肖名
ZODIAC_EXTRA_RAD = {
 '鼠':['氵','冫'], '兔':['木','艹'], '马':['火','马'], '龙':['雨','云'], '狗':['犬','犭'],
 '猪':['豕','家'], '猴':['侯','袁'], '鸡':['鸟','隹'], '虎':['山','虍'], '牛':['田'],
 '羊':['羊'], '蛇':['虫'],
}
def _zodiac_friends(z):
    """三合+六合 的友好生肖集合。"""
    out = set()
    for g in SANHE:
        if z in g:
            out |= set(g) - {z}
    for a, b in LIUHE:
        if z == a: out.add(b)
        elif z == b: out.add(a)
    return out
def _zodiac_foes(z):
    """六冲+六害 的犯生肖集合。"""
    out = set()
    for a, b in LIUCHONG:
        if z == a: out.add(b)
        elif z == b: out.add(a)
    for a, b in LIUHAI:
        if z == a: out.add(b)
        elif z == b: out.add(a)
    return out
# 预派生：每个生肖「三合六合友好部首」「六冲六害犯部首」
ZODIAC_HE_RAD, ZODIAC_FAN_RAD = {}, {}
for _z in ZODIAC_PREF:
    _he = _zodiac_friends(_z); _fan = _zodiac_foes(_z)
    ZODIAC_HE_RAD[_z] = []
    ZODIAC_FAN_RAD[_z] = []
    for f in _he:
        for r in [ZODIAC_RAD[f]] + ZODIAC_EXTRA_RAD.get(f, []):
            if r not in ZODIAC_HE_RAD[_z]: ZODIAC_HE_RAD[_z].append(r)
    for f in _fan:
        for r in [ZODIAC_RAD[f]] + ZODIAC_EXTRA_RAD.get(f, []):
            if r not in ZODIAC_FAN_RAD[_z]: ZODIAC_FAN_RAD[_z].append(r)

NEG_HOMO = ['baichi','sharen','fengzi','shaizi','aocao','fanren','yangwei','duziteng','shabi','tama','nima','wangba']
# 明显不宜作姓氏的脏字/ insult 字符（轻量校验）
DIRTY_CHARS = set('傻滚操屁屎尿疯贱婊')
# 高频用字（重名近似：含其一则重名概率偏高）
HIGH_FREQ = set('伟芳娜秀英华建国婷浩鑫梓涵轩宇睿欣怡晨子凡一')

# ---------- 负面意象 / 不良组合兜底（运行时零 AI） ----------
# 单字即不宜作名的负面字根（已审核剔除，此处运行时再兜底拦截）
NEG_ROOT = set('死亡病残凶灾煞鬼棺坟丧哭悲愁苦孤寡奴囚哑瞎瘸癫瘟毒淫贱蠢笨愚邪妖魔厉殃劫祸夭衰痴厄凄怼怨嫉哀')
# 名（不含姓）两字相连形成的不吉组合，强降权
BAD_COMBOS = {'离散','悲伤','孤独','病弱','衰亡','凶煞','离丧','愁苦','残破','饥寒','凄凉',
              '绝望','毁灭','消亡','亡故','灾祸','愚昧','痴傻','疯癫','残废','苦涩','悲凉',
              '忧戚','哀怨','怨怼','嫉恨','祸患','夭折','死寂','枯竭','崩坏','凋零','败落'}

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

_ALLUSIONS = None
def allusions():
    """字义典籍出处字典：字 → 出处串（人工精校，真实可考）。"""
    global _ALLUSIONS
    if _ALLUSIONS is None:
        try:
            with open(os.path.join(DATA, 'allusions.json'), encoding='utf-8') as f:
                _ALLUSIONS = json.load(f)
        except Exception:
            _ALLUSIONS = {}
    return _ALLUSIONS

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
    - phrase：名拼音(姓+名 或 仅名，去声调) == 某俗语拼音，识别「林门一脚≈临门一脚」「费彦≈肺炎」这类谐音梗。
    叠字不在此列。"""
    rules = nickname_blacklist()
    if not rules:
        return 0, []
    s = ''.join(given_chars)
    fp = full_py if full_py is not None else given_py
    gp = given_py
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
            rp = to_ascii(r.get('py', ''))
            if rp and (rp == fp or rp == gp):
                pen += r.get('penalty', 35); hits.append(r.get('note', m))
    return pen, hits

def bad_imagery_penalty(given_chars, given_it):
    """负面意象 / 组合扫描：单字负面字根 + 两字负面词组（精确，无子串误杀）。
    返回 (扣分, 命中说明列表)。命中即强降权，确保「挑中的字 / 组合」不会是明显不吉之名。
    注：不扫描字义(m)子串——curated 好字库已人工核验，子串扫描会误伤「慈悲/含辛茹苦/华而不妖/桃之夭夭」等正象。"""
    s = ''.join(given_chars)
    pen, hits = 0, []
    for combo in BAD_COMBOS:
        if combo and combo in s:
            pen += 40; hits.append(combo)
    for c in given_chars:
        if c in NEG_ROOT:
            pen += 35; hits.append(c)
    return pen, hits

# 地支藏干（本气 / 中气 / 余气）—— 用于日主旺衰量化打分
_ZANG = {
 '子': [('癸','水')],
 '丑': [('己','土'),('癸','水'),('辛','金')],
 '寅': [('甲','木'),('丙','火'),('戊','土')],
 '卯': [('乙','木')],
 '辰': [('戊','土'),('乙','木'),('癸','水')],
 '巳': [('丙','火'),('戊','土'),('庚','金')],
 '午': [('丁','火'),('己','土')],
 '未': [('己','土'),('丁','火'),('乙','木')],
 '申': [('庚','金'),('壬','水'),('戊','土')],
 '酉': [('辛','金')],
 '戌': [('戊','土'),('辛','金'),('丁','火')],
 '亥': [('壬','水'),('甲','木')],
}
def _ten_god(dm, e):
    """以日主五行 dm 为参照，元素 e 的十神类别：self 比劫 / support 印枭 / output 食伤 / wealth 财 / control 官杀。"""
    if e == dm:             return 'self'
    if SHENG.get(e) == dm:  return 'support'   # 生我
    if SHENG.get(dm) == e:  return 'output'    # 我生
    if KE.get(dm) == e:     return 'wealth'    # 我克
    if KE.get(e) == dm:     return 'control'   # 克我
    return 'other'

def analyze_birth(year, month, day, hour):
    """现场推算八字，并据日主旺衰法给出喜用神（扶抑用神）。
    返回：gz(四柱)、counts(五行计数)、need(喜用元素，用于选字偏置)、zodiac(生肖)，
    以及展示用 day_master/day_master_wx/strong/use_gods。"""
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

    dm_wx = GAN_WX[gz[2][0]]          # 日干五行 = 日主
    # —— 日主旺衰量化：十神加权（自党 vs 异党），月令本气加权 ——
    self_w, other_w = 0.0, 0.0
    for i, pillar in enumerate(gz):
        tg = _ten_god(dm_wx, GAN_WX[pillar[0]])
        if tg in ('self', 'support'): self_w += 1.0
        else:                          other_w += 1.0
        for j, (zc, zw) in enumerate(_ZANG[pillar[1]]):
            w = [1.0, 0.5, 0.25][j]          # 本气/中气/余气
            if i == 1 and j == 0: w *= 1.4   # 月令加权
            if _ten_god(dm_wx, zw) in ('self', 'support'): self_w += w
            else:                                                other_w += w
    diff = self_w - other_w
    strong = '旺' if diff > 0.3 else ('弱' if diff < -0.3 else '中和')

    # —— 扶抑用神：身弱喜生扶（比劫+印），身旺喜克泄耗（食伤+财+官杀），中和宜平和为贵 ——
    if strong == '旺':
        use = [SHENG.get(dm_wx), KE.get(dm_wx)]        # 我生（食伤）、我克（财）
        ctrl = next((k for k in ELES if KE.get(k) == dm_wx), None)  # 克我（官杀）
        if ctrl: use.append(ctrl)
        need = [e for e in use if e]
    elif strong == '弱':
        support_elem = next((k for k in ELES if SHENG.get(k) == dm_wx), None)  # 生我（印）
        need = [dm_wx] + ([support_elem] if support_elem else [])
    else:  # 中和：不宜偏补，喜用神置空，由 score_wuxing 走「五行均衡」评分
        need = []

    zodiac = lunar.getYearShengXiao()
    month_zhi = gz[1][1]                       # 月柱地支（月令）
    dh, dh_why = DIAO_HOU.get(month_zhi, ([], ''))
    return {
        'gz': gz, 'counts': counts, 'need': need, 'zodiac': zodiac,
        'zodiac_he': ''.join(sorted(_zodiac_friends(zodiac))), 'zodiac_fan': ''.join(sorted(_zodiac_foes(zodiac))),
        'day_master': gz[2][0], 'day_master_wx': dm_wx, 'strong': strong,
        'use_gods': need, 'diao_hou': dh, 'diao_hou_why': dh_why,
    }

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
def score_wuxing(wx_list, need, has_birth, s_wx=None, diao_hou=None):
    seq = (list(s_wx) if s_wx else []) + list(wx_list)
    if not has_birth:
        # 未提供生辰时，看全名五行「相生相克」是否调和（真实玄学逻辑，逐名不同）
        if len(seq) < 2:
            return 70
        s = 66
        for a, b in zip(seq, seq[1:]):
            if SHENG.get(a) == b:
                s += 4
            elif KE.get(a) == b:
                s -= 16
            elif a == b:
                s -= 6
            else:
                s -= 2
        return max(46, min(100, s))
    seq = (list(s_wx) if s_wx else []) + list(wx_list)
    total = len(seq)
    if not need and not diao_hou:
        # 中和且无调候：五行分布越均衡越好，越偏枯越减分（不偏补为贵）
        c = {}
        for w in seq:
            c[w] = c.get(w, 0) + 1
        max_share = (max(c.values()) / total) if total else 1
        return max(46, min(96, round(88 - 42 * max_share)))
    sup = set(need or []) | set(diao_hou or [])   # 旺衰喜用 ∪ 调候，合并为「宜补」集合
    matched = sum(1 for w in seq if w in sup)
    ratio = matched / total if total else 0
    s = 44 + 52 * ratio                      # 全补→96，半补→70，无补→44（平滑）
    if sup and all(any(w == e for w in seq) for e in sup):
        s = min(96, s + 4)                    # 宜补元素逐一被覆盖，再嘉 4
    return max(44, min(96, round(s)))

def score_zodiac(radicals, zodiac):
    """生肖相宜（传统生肖法：部首喜忌 + 三合六合强吉 + 六冲六害强凶）。
    未提供生辰（zodiac 为 None）时返回 None：该维度不评分、不参与总分加权。"""
    pref = ZODIAC_PREF.get(zodiac)
    if not pref:
        return None
    he = ZODIAC_HE_RAD.get(zodiac, [])
    fan = ZODIAC_FAN_RAD.get(zodiac, [])
    s = 56
    for r in radicals:
        if r in he:
            s += 18          # 三合/六合：强吉（比普通部首喜忌更宜）
        elif r in pref['xi']:
            s += 14          # 普通部首喜忌
        if r in fan:
            s -= 26          # 六冲/六害：强凶
        elif r in pref['ji']:
            s -= 20          # 普通部首忌
    return max(36, min(96, s))

def _final_brightness(final):
    """声韵响亮度（开口呼/后鼻音增响，闭口呼略减）。final 为完整韵母，如 'ang'/'i'/'er'。"""
    f = (final or '').lower()
    if not f:
        return 0
    open_ = f[0] in 'aoe'            # 开口呼(a/o/e 开头)：张口最响
    nasal_ng = f.endswith('ng')      # 后鼻音：余韵悠长
    close = f[0] in 'iuüv' and not nasal_ng   # 齐/合/撮口呼（闭口）：偏柔
    score = 0
    if open_:
        score += 4
    if nasal_ng:
        score += 2
    if close:
        score -= 2
    return score

def _apply_tone_sandhi(tones):
    """上声变调：两个上声(3)相连时，前一个实际读作阳平(2)。

    这是普通话真实语音规律——「李雨」实际读 lí yǔ，而非字典调 lǐ yǔ。
    平仄判断必须基于**实际读音**：按字典调会把「仄仄」误判，实际是「平仄」。
    「一/不」的变调在人名中极罕见，暂不处理。
    """
    t = list(tones)
    for i in range(len(t) - 1):
        if t[i] == 3 and t[i + 1] == 3:
            t[i] = 2
    return t

def score_pronounce(tones, initials, finals):
    """音调韵律评分（增强版）：平仄回环 + 三连声硬惩 + 尾字调 + 声韵响亮度 + 双声叠韵。
    签名与 [42,96] 返回区间保持兼容，总分合成（dims['pronounce']）无需改动。"""
    real = [t for t in tones if t != 0]
    n = len(real)
    s = 60
    # ① 全同调惩罚：双名同调(拗) / 三连声(最拗) 硬惩
    if real and len(set(real)) == 1:
        s -= (22 if n >= 3 else 14)
    # ② 平仄回环：首尾同平仄、中间异调 → 最优；相邻平仄切换 → 加分
    pz = [t in (1, 2) for t in real]
    if n >= 3 and pz[0] == pz[-1] and pz[0] != pz[n // 2]:
        s += 12
    s += sum(6 for i in range(1, n) if pz[i] != pz[i-1])
    # ③ 尾字调：平声余韵、去声收束、上声略纤曲
    s += {1: 4, 2: 4, 4: 2, 3: -3}.get(real[-1] if real else 0, 0)
    # ④ 声韵响亮度（用 finals）：开口呼/后鼻音增响，闭口呼略减
    if finals:
        br = sum(_final_brightness(f) for f in finals) / len(finals)
        s += round(br * 0.9)
    # ⑤ 双声/叠韵：任意同声母/同韵母（含非相邻）轻惩（汪文伟 w/w/w、顾叔武 u/u/u）
    ini = [x for x in initials if x and x != 'NULL']
    fin = [x for x in finals if x]
    for i in range(len(ini)):
        for j in range(i + 1, len(ini)):
            if ini[i] == ini[j]:
                s -= 7
    for i in range(len(fin)):
        for j in range(i + 1, len(fin)):
            if fin[i] == fin[j]:
                s -= 5
    return max(42, min(96, s))

def score_homophone(full_py):
    for neg in NEG_HOMO:
        if neg in full_py:
            return 20
    return 100

TAG_MEANING = {'智慧':90,'才华':88,'健康':86,'安宁':89,'光明':87,'品德':88,'勇敢':85,
                '温婉':87,'灵秀':86,'仁愛':88,'喜悦':84,'自由':85,'俊逸':86,'坚韧':85}
# 意象族：用于判断两字意象是「雷同」「同族有层次」还是「跨族互补」
TAG_GROUP = {
    '光明': '境', '安宁': '境', '自由': '境',
    '品德': '德', '仁愛': '德', '勇敢': '德', '坚韧': '德',
    '智慧': '才', '才华': '才', '灵秀': '才', '俊逸': '才',
    '喜悦': '情', '温婉': '情',
    '健康': '体',
}
def score_coherence(given_it):
    """两字组合语义协调度：奖励互补、惩罚雷同/性别气韵冲突。返回 -12~+8 的调整量（叠加进字义维度）。

    三档判定（原来只有「雷同 -8 / 互补 +4」两档，区分度不足）：
      - 主意象雷同（瑶+琪 皆俊逸）      → -8  意境重复
      - 同族不同意象（光明+安宁 皆「境」）→ +6  画面统一且有层次（最优）
      - 跨族互补（智慧+温婉）            → +4  意境丰富
    """
    if len(given_it) < 2:
        return 0
    t0, t1 = given_it[0].get('t', []), given_it[1].get('t', [])
    p0, p1 = (t0[0] if t0 else ''), (t1[0] if t1 else '')
    g0, g1 = given_it[0].get('g', 'U'), given_it[1].get('g', 'U')
    adj = 0
    if p0 and p1:
        if p0 == p1:
            adj -= 8          # 主标签雷同（如 瑶+琪 皆俊逸）→ 意境重复
        elif TAG_GROUP.get(p0) and TAG_GROUP.get(p0) == TAG_GROUP.get(p1):
            adj += 6          # 同族不同意象（光明+安宁）→ 画面统一且有层次
        else:
            adj += 4          # 跨族互补 → 意境更丰富
    if g0 not in ('U', '') and g1 not in ('U', '') and g0 != g1:
        adj -= 6             # 性别气韵冲突（男字+女字混搭）
    return max(-12, min(8, adj))

def score_meaning(given_it, chosen):
    vals = []
    for gi in (given_it or []):
        ts = gi.get('t', [])
        v = round(sum(TAG_MEANING.get(t, 80) for t in ts) / len(ts)) if ts else 78
        v += min(4, max(0, len(ts) - 1))   # 意象丰富度：多一枚意象多一分层次（0~4）
        vals.append(v)
    base = round(sum(vals) / len(vals)) if vals else 80
    if chosen:
        union = set().union(*[gi.get('t', []) for gi in given_it]) if given_it else set()
        hit = 1 if (union & set(chosen)) else 0
        base += 10 * hit
    coh = score_coherence(given_it)
    return max(45, min(97, base + coh))

def score_stroke(total):
    if total <= 26:
        return 100
    return max(0, 100 - (total - 26) * 3)

# 刚柔度：字义层面的「刚/柔」连续谱（+1 极刚 … -1 极柔），供气韵维度细粒度评分
TAG_TEMPER = {
    '勇敢': 0.8, '坚韧': 0.7, '俊逸': 0.35, '光明': 0.25, '自由': 0.2,
    '智慧': 0.1, '才华': 0.1, '健康': 0.0, '品德': 0.0, '仁愛': -0.15,
    '安宁': -0.35, '喜悦': -0.35, '灵秀': -0.55, '温婉': -0.8,
}
GENDER_TEMPER = {'M': 0.6, 'U': 0.0, 'F': -0.6}

def _char_temper(g, tags):
    """单字刚柔度：性别气韵为主(0.6)、字义标签为辅(0.4)，合成 -1 ~ +1 连续值。"""
    base = GENDER_TEMPER.get(g, 0.0)
    t = (sum(TAG_TEMPER.get(x, 0.0) for x in tags) / len(tags)) if tags else 0.0
    return 0.6 * base + 0.4 * t

def score_gender(genders, req, given_it=None):
    """气韵契合（性别维度）：名中每字气韵与所求性别的贴合度。

    旧实现只按 M/F/U 三值查表，区分度极低（实测 sd=0~2.5，形同虚设）：
    好字池近半是中性字，导致「不限性别」时该维度恒为 84、完全不产生区分。

    新实现（given_it 可用时）按**连续刚柔度**评分：
    - 每字由「性别气韵(M/F/U) + 字义标签」合成 -1(极柔) ~ +1(极刚) 的连续值；
    - 男孩/女孩各有目标区间（略偏刚/略偏柔），走高斯型曲线，越贴合越高分；
    - 「刚柔相济」优于「一味刚硬」，故极端值反不如中段；
    - 一字极刚一字极柔视为气韵杂乱，按 spread 额外扣分。
    given_it 不可用时回退旧的三值查表（保持兼容）。
    """
    if not genders:
        return 100
    if given_it and len(given_it) == len(genders):
        temps = [_char_temper(given_it[i].get('g', 'U'), given_it[i].get('t', []))
                 for i in range(len(genders))]
        avg = sum(temps) / len(temps)
        target = {'M': 0.25, 'F': -0.25, 'U': 0.0}.get(req, 0.0)
        spread = max(temps) - min(temps)
        s = 96 - 55 * (avg - target) ** 2 - 8 * spread
        return max(40, min(97, round(s)))
    # —— 回退：旧三值查表 ——
    n = len(genders)
    if req == 'M':
        fit = {'M': 90, 'U': 84, 'F': 0}
    elif req == 'F':
        fit = {'F': 90, 'U': 84, 'M': 0}
    else:                               # req == 'U'（不限）
        if 'M' in genders and 'F' in genders:
            return 55                    # 气韵杂乱，直接降分
        fit = {'U': 90, 'M': 84, 'F': 84}
    s = sum(fit.get(g, 84) for g in genders) / n
    # 气韵（意境）：清一色同性别略欠含蓄，含一枚中性字更见刚柔相济之韵 → 小幅加成，封顶 100
    if req in ('M', 'F') and 'U' in genders and genders.count('U') < n:
        s = min(100, s + 8)
    return round(s)

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

# 五格传统角色：人格主运（一生核心）、总格后运（中晚年）、地格前运（青年/家庭）、天格祖运、外格副运（社交）
GRID_ROLE = {'天格': '祖运', '人格': '主运', '地格': '前运', '总格': '后运', '外格': '副运'}
def grid_fortune(n):
    """把五格数理还原成传统吉凶标签（依据 GRID_SCORE 分值档位）。"""
    s = _grid_num(n)
    if s >= 95:
        return '大吉'
    if s >= 75:
        return '吉'
    if s >= 55:
        return '半吉'
    return '凶'
def grid_fortune_map(grids):
    """{格名: (数值, 角色, 吉凶)} —— 供前端展示。"""
    return {k: (v, GRID_ROLE.get(k, ''), grid_fortune(v)) for k, v in (grids or {}).items()}

# ---------- 三才配置（天格/人格/地格 五行生克，五格派的另一半，定根基吉凶） ----------
# 数理尾数 → 五行：1,2 木；3,4 火；5,6 土；7,8 金；9,0 水
_GRID_WX = {1:'木',2:'木',3:'火',4:'火',5:'土',6:'土',7:'金',8:'金',9:'水',0:'水'}
SHENG = {'木':'火','火':'土','土':'金','金':'水','水':'木'}   # a 生 b
KE = {'木':'土','土':'水','水':'火','火':'金','金':'木'}       # a 克 b
def grid_wx(n):
    if n is None or n <= 0:
        return '土'
    return _GRID_WX[n % 10]
def _rel(a, b):
    """a 对 b 的作用：'生'(a生b, 利b) / '克'(a克b, 损b) / '比' / None(泄或克出，中性)。"""
    if a == b:
        return '比'
    if SHENG.get(a) == b:
        return '生'
    if KE.get(a) == b:
        return '克'
    return None
def sancai(grids):
    """三才配置：天格/人格/地格 五行生克 → (五行三元组, 等级, 文案)。人格为主运、地格为根基。
    判定（以人格为中心）：天克人/人克地/地克人 任一即凶；天生人且人生地(顺生)为大吉；
    至少一重相生为吉；仅比和/泄为半吉。"""
    if not grids or '人格' not in grids or '天格' not in grids or '地格' not in grids:
        return None
    tw, rw, dw = grid_wx(grids['天格']), grid_wx(grids['人格']), grid_wx(grids['地格'])
    rt, rd, rb = _rel(tw, rw), _rel(dw, rw), _rel(rw, dw)   # 天→人 / 地→人 / 人→地
    kes, sans = [], []
    if rt == '克': kes.append('天格克人格')
    elif rt == '生': sans.append('天格生人格')
    if rd == '克': kes.append('地格克人格')
    elif rd == '生': sans.append('地格生人格')
    if rb == '克': kes.append('人格克地格')
    elif rb == '生': sans.append('人格生地格')
    if kes:
        # 通关化解：A 克 B 时，用 A 所生五行字介入，使 A→通→B 顺生，化解相战
        tong = []
        if rt == '克': tong.append(SHENG.get(tw))
        if rd == '克': tong.append(SHENG.get(dw))
        if rb == '克': tong.append(SHENG.get(rw))
        tong = [t for t in dict.fromkeys(tong) if t]
        tip = '、'.join(kes) + '，三才有克，根基稍滞' + ('；可增' + '、'.join(tong) + '字通关，化相战之滞' if tong else '')
        grade = '凶'
    elif rt == '生' and rb == '生':
        grade, tip = '大吉', '、'.join(sans) + '，三才顺生，根基稳固'
    elif sans:
        grade, tip = '吉', '、'.join(sans) + '，三才相生，根基得养'
    else:
        grade, tip = '半吉', '三才比和，气运平顺'
    return {'wx': (tw, rw, dw), 'grade': grade, 'text': tip, 'x': tw + '·' + rw + '·' + dw}
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

# ---------- 差异化细项文案（多套模板池 + 跨候选去重随机） ----------
DIM_ORDER = ['wuxing', 'zodiac', 'pronounce', 'meaning', 'stroke', 'gender', 'dup', 'net', 'nick', 'imagery']
DIM_LABEL = {'wuxing': '五行调和', 'zodiac': '生肖相宜', 'pronounce': '音律朗朗',
             'meaning': '字义寄意', 'stroke': '数理格局', 'gender': '气韵契合',
             'dup': '重名（近似）', 'net': '撞梗（本地）', 'nick': '昵称/梗（本地）',
             'imagery': '意象吉凶'}
DIM_APPROX = {'dup': True, 'net': True, 'nick': True, 'imagery': False}

def _gd_word(o):
    g = o.get('req_gender')
    return '男孩' if g == 'M' else ('女孩' if g == 'F' else '孩子')

def _pingze(tones):
    m = {1: '平', 2: '平', 3: '仄', 4: '仄', 0: '·'}
    return ''.join(m.get(t, '·') for t in (tones or []))

# —— 各细项模板池（分支 → 多套表达）——
WX_TPLS = {
 'all': [
  "「{given}」各字五行皆补命中所缺之{need_str}，五行相生，根基稳厚，一生多得帮扶。",
  "此名五行齐补所缺之{need_str}，干支相扶，气脉贯通，自小根基便厚。",
  "名中诸字皆应命局所缺之{need_str}，五行流转得宜，主后天助益绵长。",
  "「{given}」五行全数补入{need_str}，命局得济，如苗得雨，长势可期。",
  "字字应缺，{need_str}尽补其中，五行相济无冲，主身心安泰、运途少滞。",
  "所缺之{need_str}皆由此名补益，干支和合，气运自内而外通畅。",
  "「{given}」与命局所缺{need_str}一一相应，五行得全，主禀赋厚实、承托有力。",
  "补入{need_str}之后，五行归位，生克得序，幼年得护、长成得助。",
  "名中五行恰填{need_str}之空，如器得柄，行事有凭、立身有靠。",
  "诸字五行同补{need_str}，命局由缺转盈，主福泽暗藏、贵人来扶。",
  "「{given}」补满{need_str}，五行周流不息，主性情圆融、际遇难塞。",
  "所缺{need_str}尽收于名，气与命合，主一生少波折、多得顺势之助。",
 ],
 'some': [
  "其中「{fill}」恰补所缺之{need_str}，与八字相扶；余字悄然调和，气运平顺。",
  "「{fill}」补命中之缺（{need_str}），其余刚柔相济，整体不失平衡。",
  "名中「{fill}」应所缺之{need_str}，余字辅之，五行虽有偏亦能自圆。",
  "以「{fill}」补{need_str}之不足，旁字调和其间，气运不至于偏枯。",
  "「{fill}」一肩补起{need_str}之缺，余字守中，命局得半济之益。",
  "所缺{need_str}由「{fill}」引补，其余随势相承，主运途渐入顺境。",
  "名借「{fill}」填{need_str}之漏，余字润之，五行虽有亏亦能自养。",
  "「{fill}」入局补{need_str}，旁字不夺其功，气脉相续渐稳。",
  "以「{fill}」接{need_str}之气，余字环护，主早年得荫、中年得力。",
  "缺者{need_str}由「{fill}」补其大半，余字暗合，命局不至偏废。",
  "「{fill}」担起{need_str}之补，余字如辅弼，整体仍见调和之象。",
  "借「{fill}」补{need_str}之一隅，名中气象随之转圜，运有可期。",
 ],
 'none': [
  "此名五行以{wx}搭配，中和温润，不偏不倚，自有从容之象。",
  "名之五行属{wx}，彼此制衡得法，主性情中正、处世稳健。",
  "五行{wx}相配，不亢不卑，气场平和，少有大起大落。",
  "「{given}」五行作{wx}之局，清浊相济，平顺无虞。",
  "名中五行归{wx}，虽不补所缺，却自成一格，主心性淡定、随遇而安。",
  "五行{wx}相生相涵，命局虽未得补，亦无冲克，安稳可守。",
  "「{given}」五行属{wx}，刚柔互见，主为人有度、行事有节。",
  "名之五行{wx}调和得所，纵不济命，亦能护持日常顺遂。",
  "五行{wx}并陈，气韵不争，主一生少是非、多得清静。",
  "「{given}」五行作{wx}，无旺无衰，主性平、运稳、人和。",
  "名以{wx}为局，不偏不倚，纵命局有缺，名亦不添其扰。",
  "五行{wx}相安，主外缘平顺、内里安定，是可久守之名。",
 ],
 'nobirth': [
  "「{given}」五行属{wx}，刚柔相映（未提供生辰，仅作常规搭配参考）。",
  "此名五行归{wx}，搭配有致（未填生辰，暂不以八字衡其补益）。",
  "名中五行属{wx}，相生相成（生辰空缺，仅观常理之调和）。",
  "五行{wx}并济，意象周正（未提供生辰，补益之说从略）。",
  "「{given}」五行作{wx}之局，清通可喜（未填生辰，补益待考）。",
  "名之五行属{wx}，彼此涵容（生辰未录，不计八字所缺）。",
  "五行{wx}相配得宜，气象从容（未提供生辰，仅按常理参详）。",
  "「{given}」五行归{wx}，温润不突（无生辰，暂作泛论）。",
  "名中五行{wx}互济，主性平气和（未填生辰，补益一说存疑）。",
  "五行{wx}成局，疏密有度（生辰空缺，不以命理深究）。",
  "「{given}」五行属{wx}，刚柔可赏（未提供生辰，仅观其形）。",
  "名之五行{wx}相和，意象无碍（无生辰，补益之论从略）。",
 ],
}
ZX_WITH = [
 "生肖{zodiac}与名字部首气韵相合，寓意得天地庇佑，安然顺遂。",
 "名之形音暗合{zodiac}之喜，主得祖荫护持，行止自在无忧。",
 "与{zodiac}相宜，用字避其忌、就其喜，祥瑞自蕴其中。",
 "生肖{zodiac}见此名如鱼得水，喜用得济，气运更为圆融。",
 "名与{zodiac}三合相生，喜用得地，主早年得护、中年得运。",
 "此名就{zodiac}之所喜、避其所忌，主行事少阻、贵人暗扶。",
 "生肖{zodiac}遇此名气韵相得，主外缘和顺、内里安稳。",
 "形音皆契{zodiac}之宜，用字无冲，主一生多得顺势之助。",
 "与{zodiac}相合无犯，名中藏喜，主运途平和、少生波折。",
 "名承{zodiac}之瑞，喜用俱全，主禀赋清嘉、承托有力。",
 "生肖{zodiac}于此名中各得其所，主性情温厚、际遇稳当。",
 "此名与{zodiac}相宜相生，主福泽内蕴、行藏有度。",
]
ZX_HE = [
 "名中字形暗合{zodiac}之三合六合，贵人生扶、根基得托，主一生多遇顺势之助。",
 "「{given}」结{zodiac}三合之局，气脉相生无犯，主外缘和顺、内里安稳。",
 "与{zodiac}三合相生，喜用得地，主早年得护、中年得运，行藏自有分寸。",
 "名承{zodiac}三合之瑞，用字无冲，主运途平和、少生波折，贵人暗扶。",
 "生肖{zodiac}于此名中各得其所，三合相济，主性情温厚、际遇稳当。",
]
ZX_WITHOUT = [
 "属相之宜留待添上生辰后再细参，此名意象本就周正安稳。",
 "未填生辰，生肖喜忌暂不参评；名之格局已自稳当。",
 "生肖相宜一项待生辰补入方验，眼前此名意象无碍。",
 "属相之合须俟生辰，今且观其字意，已见端凝安稳之象。",
 "生辰未录，生肖喜忌无从细论；「{given}」形意本自周正。",
 "属相之合须俟八字，今先赏「{given}」之雅，安稳无虞。",
 "未填生辰，不便妄断生肖宜忌；「{given}」意象已见从容。",
 "生肖相宜且待生辰，眼前「{given}」字正意明，足堪待用。",
 "生辰空阙，属相一节从略；「{given}」自有端凝之态。",
 "待补生辰再参属相，今「{given}」气象已和，无可指摘。",
 "生肖喜忌须凭生辰，今且看「{given}」格局，稳当可喜。",
 "属相之论留待来日，此刻「{given}」形神俱正，无妨使用。",
]
PR_TPLS = [
 "全名{pz_desc}（{pz}），念来起伏有致、清亮悦耳，{clear}。",
 "声调{pz}错落，唇齿间朗朗成调，{clear}，落落大方。",
 "「{given}」读若{pz}，平仄相协，越念越觉妥帖，{clear}。",
 "声口{pz_desc}，不拗不滞，{clear}，令人过耳能记。",
 "全名{pz}成调，起承转合自然，{clear}，呼之有余韵。",
 "「{given}」声律{pz}，清浊相济，念来不涩不飘，{clear}。",
 "声调作{pz}之局，疏密得宜，{clear}，听感温润。",
 "名口{pz_desc}，吐字如珠，{clear}，久呼不腻。",
 "「{given}」音流{pz}，缓急有节，{clear}，自见从容。",
 "全名{pz}相承，无拗口之虞，{clear}，声韵清朗。",
 "声律{pz_desc}，与字义相生，{clear}，愈读愈雅。",
 "「{given}」以{pz}成吟，不疾不徐，{clear}，余味悠长。",
]
PR_TPLS_FLAT = [   # 同调/三连声（缺起伏）专属文案池
 "全名{pz_desc}（{pz}），三字如一，念来稍欠起伏，{clear}，不妨易一字调之。",
 "声调作{pz}之局，缺错落之致，呼之少抑扬，{clear}，宜参平仄。",
 "「{given}」读若{pz}，声调相重，听感偏平，{clear}，或可换字增韵。",
 "声口{pz_desc}（{pz}），三声相叠，略显平板，{clear}，可调以谐音。",
]
MN_HAS = [
 "{mean_txt}。意境相映，寄意深远，足见长辈拳拳之心。{extra}",
 "字义上，{mean_txt}；组在一处，情味悠长，长辈期许尽付笔端。{extra}",
 "{mean_txt}——各字自成一境，连读更见温厚，是长辈用心之选。{extra}",
 "观其字义：{mean_txt}。意脉相通，含蓄而有分量。{extra}",
]
MN_NONE = [
 "用字雅正，寄意自见；长辈之情，尽在其中。",
 "选字端庄，意涵自明，不必赘言已见期许。",
]
ST_TPLS = [
 "依姓名学五格推算，此名总格为 {zg}，天/人/地/外诸格谐和相济，主一生顺遂安稳。",
 "五格剖象，总格 {zg}，三才配置得宜，主根基牢固、行事少阻。{gd}习书亦流畅美观。",
 "总格 {zg}，数理上属安稳之格，主性情沉稳、晚景平宁；笔意舒展，写得顺手。",
 "姓名学五格以总格 {zg} 为要，诸格相生，主平步稳进；{gd}用之，形声俱宜。",
 "总格 {zg}，天格清、人格稳、地格实，三才无冲，主一生少颠簸。",
 "五格之中总格 {zg} 为枢，诸格环护，主外缘和顺、内里安稳；{gd}书写亦舒。",
 "总格 {zg} 属吉数之列，主聪慧自显、机遇暗藏，{gd}临帖更见风神。",
 "以总格 {zg} 论，名中气数充盈，主早慧、中稳、晚丰，运途少滞。",
 "总格 {zg}，数理相生无破，主性情坚柔并济，处世有方。",
 "五格推得总格 {zg}，主根基厚实、承托有力，{gd}用之形神俱足。",
 "总格 {zg} 居于中和之位，不偏不亢，主一生平顺、少有大落。",
 "姓名学以总格 {zg} 为归，诸格相扶，主行事有恒、终见其成。",
]
GD_TPLS = [
 "字形气韵契合{gd}，温润而有筋骨，愈叫愈觉妥帖。",
 "整体气韵偏宜{gd}，柔刚得中，呼之有余韵。",
 "字里行间见{gd}之风，不媚不僵，自有清雅。",
 "气韵与{gd}相得，疏密合度，念来心声相印。",
 "名中气象契合{gd}，清通而不轻浮，久看愈见其厚。",
 "整体风神宜{gd}，动静有度，书写念读皆顺。",
 "字韵含{gd}之致，外秀内敦，呼之如见其人。",
 "气韵与{gd}相生，疏朗有致，不争不迫。",
 "名之格调近{gd}，雅正而亲，观之可亲、呼之可感。",
 "字形意态合{gd}，刚处见柔、柔处见骨，耐人寻味。",
 "气韵落于{gd}一脉，清雅含章，愈品愈觉妥帖。",
 "整体气象宜{gd}，不躁不滞，形声相映成趣。",
]
DUP_COMMON = [
 "「{hit}」属较常见用字，重名概率略高；若求独特可换更冷僻雅字。（本地近似估算，真实重名率需接入户籍数据）",
 "用字「{hit}」多见，撞名可能稍大；偏好特别可酌换生僻字。（本地近似，非户籍统计）",
 "「{hit}」是高频字，同辈重名风险偏高；想更出挑建议替换。（本地近似估算）",
 "名含常见字「{hit}」，重名概率不低；若看重独特感可另择他字。（本地近似，非户籍统计）",
 "「{hit}」使用面广，同名几率偏高；欲避俗可考虑更冷门雅字。（本地近似估算）",
 "字「{hit}」颇为通行，撞名不难遇见；讲究独特不妨另选。（本地近似，非户籍统计）",
 "「{hit}」属大众常用字，重名概率偏高；求异可换生僻字。（本地近似估算）",
 "名中「{hit}」常见，同窗同辈易撞；偏好少见的宜斟酌替换。（本地近似，非户籍统计）",
 "「{hit}」流传甚广，重名风险不低；若求独可挑更生僻者。（本地近似估算）",
 "用字「{hit}」高频，重名几率偏大；讲究个性建议另择。（本地近似，非户籍统计）",
 "「{hit}」是熟字，同名相遇概率高；欲出挑可换雅僻字。（本地近似估算）",
 "名含「{hit}」这一常见字，重名概率偏高；看重独特感宜替换。（本地近似，非户籍统计）",
]
DUP_UNIQUE = [
 "用字相对独特，重名概率较低，不易与他人撞名。（本地近似估算，真实重名率需接入户籍数据）",
 "所选用字少见，重名风险小，叫得出便记得住。（本地近似，非户籍统计）",
 "名中字较冷门，街头巷尾撞名机会不大；求绝对独则可再挑更生僻者。（本地近似估算）",
 "用字偏雅僻，重名几率低，落笔不易与同窗混淆。（本地近似，非户籍统计）",
 "所选字不落俗套，重名概率小，呼之自有辨识。（本地近似估算）",
 "名中字颇生僻，撞名难得一见；偏好独特正相宜。（本地近似，非户籍统计）",
 "用字稀少，重名风险低，书写念读皆不易与他者混。（本地近似估算）",
 "字取冷门一路，重名几率不高，落笔清奇可辨。（本地近似，非户籍统计）",
 "名之用字偏独，同辈撞名概率小；讲究个性者正合。（本地近似估算）",
 "所择字不常见于名，重名概率低，呼来清晰可辨。（本地近似，非户籍统计）",
 "用字清冷少见，重名风险小，不与人轻易相混。（本地近似估算）",
 "名中字取径偏僻，重名几率低，独处而不孤。（本地近似，非户籍统计）",
]
NET_TPLS = [
 "检出潜在不良谐音，建议再斟酌；网络撞梗/负面人物检测需联网检索，待后续接入。",
 "读音上疑有近音歧义，宜复核；联网查梗能力后续补上。",
 "声旁或近他义，易生联想，建议复核；联网检索待接入。",
 "读音似有歧义空间，宜审慎；负面人物/网络梗检测需联网。",
 "音近之虞不可不察，建议再念几遍；联网核梗能力后续上线。",
 "隐有近音干扰，宜复核；本地规则有限，联网核查更稳妥。",
]
NICK_TPLS = [
 "本地规则提示：此名易联想「{hit}」等昵称或网络梗，是否采用您可斟酌。（静态黑名单，可手动维护）",
 "谐音黑名单提示：或易被叫成「{hit}」一类昵称，取舍在您。（规则可维护）",
 "本地规则检出：此名或惹「{hit}」等戏称，是否介意由您定。（黑名单可维护）",
 "谐音提示：易与「{hit}」相混作昵称，采否请自决。（静态规则）",
 "规则命中：此名易生「{hit}」之类外号，您可斟酌。（可手动维护）",
 "本地黑名单提示：或被人唤作「{hit}」，取舍随您。（规则可更新）",
]

POOL_SIZE = {'wuxing': 12, 'zodiac': 12, 'pronounce': 12, 'meaning': 4,
             'stroke': 12, 'gender': 12, 'dup': 12, 'net': 6, 'nick': 6, 'imagery': 6}

def _ex_wuxing(o, meta, mode, idx):
    wx = o['given_wx']; need = meta.get('need') or []
    fill = [w for w in wx if w in need]
    fill_c = ''.join(c for c, w in zip(o['given_chars'], wx) if w in need)
    if meta.get('has_birth'):
        br = 'all' if len(fill) == len(wx) else ('some' if fill else 'none')
    else:
        br = 'nobirth'
    return WX_TPLS[br][idx % len(WX_TPLS[br])].format(
        given=o['given'], fill=fill_c, need_str='/'.join(need), wx='/'.join(wx))

def _ex_zodiac(o, meta, mode, idx):
    if meta.get('has_birth'):
        if o.get('dims', {}).get('zodiac_he_hit'):
            return ZX_HE[idx % len(ZX_HE)].format(zodiac=meta.get('zodiac') or '?', given=o.get('given', ''))
        return ZX_WITH[idx % len(ZX_WITH)].format(zodiac=meta.get('zodiac') or '?')
    return ZX_WITHOUT[idx % len(ZX_WITHOUT)].format(given=o['given'])

def _ex_pronounce(o, meta, mode, idx):
    tones = o.get('tones', [])
    pz = _pingze(tones)
    varies = len(set(t for t in tones if t)) > 1
    pz_desc = '平仄交错' if varies else '声调平和'
    clear = '细究并无不良谐音' if o.get('homophone_score', 100) > 20 else '读音已附谐音提示'
    # 同调/三连声（缺起伏）走专属文案池，其余走常规池
    if not varies:
        return PR_TPLS_FLAT[idx % len(PR_TPLS_FLAT)].format(given=o['given'], pz=pz, pz_desc=pz_desc, clear=clear)
    return PR_TPLS[idx % len(PR_TPLS)].format(given=o['given'], pz=pz, pz_desc=pz_desc, clear=clear)

def _ex_meaning(o, meta, mode, idx):
    parts = [(c, m) for c, m in zip(o['given_chars'], o['given_mean']) if m]
    alu = ''
    if o.get('allusions'):
        alu = '其字各有典出：' + '；'.join('「%s」%s' % (a['c'], a['src']) for a in o['allusions'])
    if parts:
        mean_txt = '；'.join(f"「{c}」{m}" for c, m in parts)
        extra = "父母二姓皆镌于此名之中，血脉亲情一目了然。" if mode == 'B' else ""
        return MN_HAS[idx % len(MN_HAS)].format(mean_txt=mean_txt, extra=extra) + alu
    return MN_NONE[idx % len(MN_NONE)].format() + alu

def _ex_stroke(o, meta, mode, idx):
    zg = o.get('grids', {}).get('总格', '?')
    return ST_TPLS[idx % len(ST_TPLS)].format(zg=zg, gd=_gd_word(o))

def _ex_gender(o, meta, mode, idx):
    return GD_TPLS[idx % len(GD_TPLS)].format(gd=_gd_word(o))

def _ex_dup(o, meta, mode, idx):
    hit = ''.join(c for c in o['given_chars'] if c in HIGH_FREQ)
    if hit:
        return DUP_COMMON[idx % len(DUP_COMMON)].format(hit=hit)
    return DUP_UNIQUE[idx % len(DUP_UNIQUE)].format()

def _ex_net(o, meta, mode, idx):
    return NET_TPLS[idx % len(NET_TPLS)].format()

def _ex_nick(o, meta, mode, idx):
    hit = (o.get('nickname_hits') or [''])[0]
    return NICK_TPLS[idx % len(NICK_TPLS)].format(hit=hit)

IMAGERY_TPLS = [
 "静态规则提示：此名组合易读出「{hit}」一类负面意象，建议斟酌换字。（可手动维护黑名单）",
 "意象核查提示：名中或含「{hit}」之不吉联想，取舍在您。（本地规则，非 AI）",
 "本地规则检出：此名组合偏近「{hit}」意涵，是否采用请自决。（黑名单可维护）",
 "负面意象提示：易与「{hit}」相系，您可斟酌。（静态规则）",
 "规则命中：此名意象偏「{hit}」，宜复核；本地可维护。（非联网）",
 "意象告警：此名或惹「{hit}」之联想，采否由您。（规则可更新）",
]

def _ex_imagery(o, meta, mode, idx):
    hit = (o.get('bad_imagery_hits') or [''])[0]
    return IMAGERY_TPLS[idx % len(IMAGERY_TPLS)].format(hit=hit)

DIM_FUNCS = {'wuxing': _ex_wuxing, 'zodiac': _ex_zodiac, 'pronounce': _ex_pronounce,
             'meaning': _ex_meaning, 'stroke': _ex_stroke, 'gender': _ex_gender,
             'dup': _ex_dup, 'net': _ex_net, 'nick': _ex_nick, 'imagery': _ex_imagery}

def _key_included(k, o, meta):
    if k == 'net':
        return o.get('homophone_score', 100) <= 20
    if k == 'nick':
        return bool(o.get('nickname_hits'))
    if k == 'imagery':
        return bool(o.get('bad_imagery_hits'))
    return True

def _assign_explain_variants(names, meta, mode):
    """对每个细项，将模板下标在包含该项的候选间洗牌轮转，压低跨候选重复率。"""
    inc = {k: [] for k in DIM_FUNCS}
    for i, o in enumerate(names):
        for k in DIM_FUNCS:
            if _key_included(k, o, meta):
                inc[k].append(i)
    assigned = [dict() for _ in names]
    for k, idxs in inc.items():
        pool = list(range(POOL_SIZE[k]))
        random.shuffle(pool)
        for j, ci in enumerate(idxs):
            assigned[ci][k] = pool[j % len(pool)]
    return assigned

def render_explain(o, meta, mode, vidx):
    out = []
    for k in DIM_ORDER:
        if k not in vidx:
            continue
        out.append({'key': k, 'label': DIM_LABEL[k],
                    'text': DIM_FUNCS[k](o, meta, mode, vidx[k]),
                    'approx': DIM_APPROX.get(k, False)})
    return out

def _build_name(surname, given_chars, given_info, given_it, gender, birth, need, zodiac,
                weights, s_py, s_tones, s_ini, mode, mother_echo_radical, chosen_tags=None):
    """由一组「名」字符构造完整名字对象（generate 与 analyze 共用）。"""
    wx_list = [gi['wx'] for gi in given_info]
    radicals = [gi['radical'] for gi in given_info]
    tones_base = s_tones + [gi['tone'] for gi in given_info]   # 字典调（拼音标注用）
    tones = _apply_tone_sandhi(tones_base)                      # 实际读音（平仄/音律评分用）
    initials = s_ini + [gi['initial'] for gi in given_info]
    given_finals = [gi.get('final', '') for gi in given_info]
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
    # 五格数理按传统用「康熙笔画」(stroke_kx，构建期烘进字库)，而非简体画数
    s_strokes = [(ch.get(c, {}).get('stroke_kx') or ch.get(c, {}).get('stroke', 0)) for c in surname] if ch else []
    s_wx = [ch.get(c, {}).get('wx', '土') for c in surname] if ch else []
    s_finals = [ch.get(c, {}).get('final', '') for c in surname] if ch else []
    finals = s_finals + given_finals
    all_strokes = s_strokes + [(gi.get('stroke_kx') or gi['stroke']) for gi in given_info]
    grids, grid_score = five_grids(all_strokes)

    hph = score_homophone(full_py)            # 谐音（不良读音）并入「音律」，由音律老师统管
    dims = {
        'wuxing': score_wuxing(wx_list, need, birth is not None, s_wx, (birth or {}).get('diao_hou')),
        'zodiac': score_zodiac(radicals, zodiac),
        'zodiac_he_hit': bool(zodiac and any(r in ZODIAC_HE_RAD.get(zodiac, []) for r in radicals)),
        'pronounce': round(0.55*score_pronounce(tones, initials, finals) + 0.45*hph),
        'meaning': max(45, min(97, score_meaning(given_it, chosen_tags) + echo_bonus)),
        'stroke': grid_score,
        'gender': score_gender(g_gender, gender, given_it),
    }
    active = {k: w for k, w in weights.items() if dims.get(k) is not None}
    total = sum(dims[k] * active[k] for k in active) / sum(active.values()) + echo_bonus * 0.05
    # —— 静态昵称/梗黑名单降权（不耗 AI）——
    given_py = to_ascii(''.join(gi['py'].split(',')[0] for gi in given_info))
    np_pen, np_hits = nickname_penalty(given_chars, given_py, full_py)
    total = total - np_pen
    # —— 负面意象 / 组合兜底降权（不耗 AI）——
    bi_pen, bi_hits = bad_imagery_penalty(given_chars, given_it)
    total = total - bi_pen
    name = surname + ''.join(given_chars)
    o = {
        'name': name, 'surname': surname, 'given': ''.join(given_chars),
        'py': s_py.split() + [gi['py'].split(',')[0] for gi in given_info],
        'py_str': s_py + ' ' + ' '.join(gi['py'].split(',')[0] for gi in given_info),
        'given_chars': given_chars, 'given_wx': wx_list, 'given_mean': g_mean,
        'given_stroke': g_stroke, 'tags': sorted(set(g_tags)), 'grids': grids,
        'grid_fortune': grid_fortune_map(grids),
        'sancai': sancai(grids),
        'req_gender': gender, 'dims': dims, 'total': round(total, 1),
        'tones': tones,
        'pz': _pingze(tones),
        'homophone_score': hph,
        'nickname_penalty': np_pen, 'nickname_hits': np_hits,
        'bad_imagery_penalty': bi_pen, 'bad_imagery_hits': bi_hits,
    }
    o['tone_note'] = _tone_phrase(o)
    # 字义典籍出处：收集名中每个有出处的字
    al = allusions()
    o['allusions'] = [{'c': c, 'src': al[c]} for c in given_chars if c in al]
    if o['allusions']:
        o['allusion_note'] = '　'.join('「%s」出%s' % (a['c'], a['src'].split('「')[0].rstrip('·')) for a in o['allusions'])
    else:
        o['allusion_note'] = ''
    o['dup_info'] = ('unique' if not any(c in HIGH_FREQ for c in given_chars) else 'common')
    return o

def _diverse_top(ranked, size):
    """分层轮换采样：按「(性别气韵 g, 主意象族)」分桶后轮流取，保证候选多样性。

    原实现直接取 base 排序的前 N 个。问题在于 base 同分者极多（无标签时仅 2~3 种
    分值），等于每次都选中同一批「同性别 + 喜用五行」的字 → 候选在评分前就已同质化，
    各维度方差趋零（实测五行 sd=0.00、气韵恒定、总分极差仅 2.5 分），维度权重再高也
    产生不了区分。分层后候选在气韵、意象、五行上都有覆盖，维度才真正起作用。
    """
    if len(ranked) <= size:
        return list(ranked)
    buckets = {}
    for x in ranked:
        it = x[1]
        gkey = it.get('g', 'U')
        ts = it.get('t') or []
        tkey = TAG_GROUP.get(ts[0], 'x') if ts else 'x'
        buckets.setdefault((gkey, tkey), []).append(x)
    keys = sorted(buckets, key=lambda k: -len(buckets[k]))
    out, i, seen = [], 0, set()
    while len(out) < size:
        added = False
        for k in keys:
            b = buckets[k]
            if i < len(b) and id(b[i]) not in seen:
                seen.add(id(b[i]))
                out.append(b[i])
                added = True
                if len(out) >= size:
                    break
        if not added:
            break
        i += 1
    return out

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
    # 方向2：把用户所选标签扩展为「原标签 + 近义组 + 别名归并」，扩大有效池、贴合直觉
    query_tags = _expand_tags(tags)
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
        if query_tags and not (set(it['t']) & query_tags):
            continue
        info = ch.get(c)
        if not info:
            continue
        pool.append((c, it, info))

    # 方向3：若因寓意筛选导致池为空，自动松弛退回「忽略寓意」的全量好字（仍按性别/避讳），
    # 绝不返回错误掉入 mock 占位名。
    relaxed = False
    relax_reason = None
    if tags and not pool:
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
            info = ch.get(c)
            if not info:
                continue
            pool.append((c, it, info))
        if pool:
            relaxed = True
            relax_reason = '您所选寓意可匹配的字较少，已自动放宽到相近寓意与通用好字。'

    if not pool:
        return [], {'error': '当前筛选（性别/避讳）下可选字过少，请调整姓氏或避讳字。'}

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
        if query_tags and (set(it['t']) & query_tags):
            s += 20
        if gender in ('M', 'F') and it['g'] == gender:
            s += 10
        if has_birth and info['wx'] in need:
            s += 12
        return s
    ranked = sorted(pool, key=lambda x: base(x[1], x[2]), reverse=True)
    top = _diverse_top(ranked, 40)          # 分层采样替代「取前 40」，候选不再同质
    M = len(top)
    # 气韵多样化：男/女名候选字池里保留若干中性(U)字，使最终名也能出现「刚柔相济」组合，
    # 避免因为清一色同性别字导致气韵维度恒定（用户反馈：男孩气韵不应一直 100%）。
    if gender in ('M', 'F'):
        u_pool = [x for x in ranked if x[1]['g'] == 'U']
        for x in u_pool[:12]:
            if id(x) not in {id(t) for t in top}:
                top.append(x)
        M = len(top)

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
    bmeta = birth or {}
    meta = {'has_birth': has_birth, 'need': need, 'zodiac': zodiac,
            'gz': bmeta.get('gz'), 'day_master': bmeta.get('day_master'),
            'day_master_wx': bmeta.get('day_master_wx'), 'strong': bmeta.get('strong'),
            'use_gods': bmeta.get('use_gods'), 'counts': bmeta.get('counts'),
            'diao_hou': bmeta.get('diao_hou'), 'diao_hou_why': bmeta.get('diao_hou_why'),
            'zodiac_he': bmeta.get('zodiac_he'), 'zodiac_fan': bmeta.get('zodiac_fan'),
            'pool_size': len(pool), 'surname': surname, 'mode': mode,
            'name_len': name_len, 'relaxed': relaxed, 'relax_reason': relax_reason}
    out = _curate_diverse(names, topn)
    if out:
        assigned = _assign_explain_variants(out, meta, mode)
        for i, o in enumerate(out):
            o['explain'] = render_explain(o, meta, mode, assigned[i])
        out[0]['rank_reason'] = build_rank_reason(out[0], out)
    return out, meta

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

DIM_LABELS_CN = {'wuxing':'五行','zodiac':'生肖','pronounce':'音律','meaning':'字义','stroke':'数理','gender':'气韵'}
def _tone_phrase(o):
    """把平仄韵律判断量化成一句推荐理由补充语（基于 tones/pz，不依赖 AI）。"""
    tones = o.get('tones', [])
    real = [t for t in tones if t]
    if len(real) < 2:
        return ''
    pz = o.get('pz', '') or _pingze(tones)
    pron = o.get('dims', {}).get('pronounce')
    if len(set(real)) == 1:
        base = f"声调全同（{pz}），读来稍欠起伏"
        if pron is not None and pron < 70:
            base += f"，音律仅 {pron}"
        return base + "，若求朗朗上口可换字增韵"
    mid = real[len(real) // 2]
    head_ping = real[0] in (1, 2) and real[-1] in (1, 2) and mid not in (1, 2)
    head_ze = real[0] not in (1, 2) and real[-1] not in (1, 2) and mid in (1, 2)
    if head_ping:
        return f"平仄回环（{pz}），首尾呼应，读来朗朗上口"
    if head_ze:
        return f"仄平相协（{pz}），起伏分明，呼之有余韵"
    return f"声调错落（{pz}），念来不涩不滞"
def build_rank_reason(top, names):
    """基于候选群像，数据驱动地说明榜首为何排第一（优势维度 + 唯一可优化点 + 平仄韵律）。"""
    if not names:
        return ''
    keys = [k for k in ['wuxing','zodiac','pronounce','meaning','stroke','gender'] if top['dims'].get(k) is not None]
    n = len(names)
    avgs = {k: round(sum(o['dims'][k] for o in names) / n, 1) for k in keys}
    td = top['dims']
    diff_sorted = sorted(keys, key=lambda k: td[k] - avgs[k], reverse=True)
    strong = [k for k in diff_sorted if td[k] - avgs[k] >= 3][:2]
    weak = [k for k in sorted(keys, key=lambda k: td[k] - avgs[k]) if td[k] - avgs[k] <= -3][:1]
    head = f"综合分 {top['total']} 居首（共 {n} 个候选）。"
    if strong:
        s = "、".join(f"{DIM_LABELS_CN[k]}突出（{td[k]}，高于候选均值 {avgs[k]}）" for k in strong)
        tail = ""
        if weak:
            k = weak[0]
            tail = f"；唯一可优化项是{DIM_LABELS_CN[k]}（{td[k]}，低于均值 {avgs[k]}）"
        base = head + "优势在于：" + s + tail + "。"
    else:
        base = head + "各维度均处中上水平，是综合表现最均衡的一个。" + (
            f"；{DIM_LABELS_CN[weak[0]]}（{td[weak[0]]}）略低于候选均值 {avgs[weak[0]]}。" if weak else "")
    tp = _tone_phrase(top)
    if tp:
        base += " " + tp + "。"
    return base

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
    bmeta = birth or {}
    meta = {'has_birth': has_birth, 'need': need, 'zodiac': zodiac,
            'gz': bmeta.get('gz'), 'day_master': bmeta.get('day_master'),
            'day_master_wx': bmeta.get('day_master_wx'), 'strong': bmeta.get('strong'),
            'use_gods': bmeta.get('use_gods'), 'counts': bmeta.get('counts'),
            'pool_size': len(given), 'surname': raw, 'mode': None,
            'name_len': len(given), 'analyzed': True}
    o['explain'] = render_explain(o, meta, None,
        {k: random.randrange(POOL_SIZE[k]) for k in DIM_FUNCS if _key_included(k, o, meta)})
    return [o], meta

# ---------- 能力5：自由期许 → 标签映射（AI 优先，失败回退关键词） ----------
def map_free_text_to_tags(free_text):
    ft = (free_text or '').strip()
    if not ft:
        return []
    # 本地词典优先（零 AI）：覆盖「睿/温柔/诗/自然/音乐/艺术」等直觉词，命中即返回不调 AI
    local = []
    for kw, tag in _FREE_TEXT_DICT.items():
        if kw in ft and tag not in local:
            local.append(tag)
    if local:
        return local
    # 未命中再走 AI 语义映射（仅此时可能产生 1 次 AI 调用）；再失败回退词表精确包含
    picks = ai.map_free_text(ft, TAGS_VOCAB)
    if picks:
        return picks
    return [t for t in TAGS_VOCAB if t in ft]

# ---------- 能力1：整盘 AI 积极解读（AI 优先，失败返回 None） ----------
def ai_review_for_name(name_obj, meta):
    return ai.ai_review(name_obj['name'], name_obj['req_gender'],
                        meta.get('zodiac'), meta.get('need'), name_obj.get('dims'))

TAGS_VOCAB = ['智慧','才华','健康','安宁','光明','品德','勇敢','温婉','灵秀','仁愛','喜悦','自由','俊逸','坚韧']

# ---------- 标签近义组 / 别名归并（方向2：增厚 + 贴合直觉） ----------
# 用户选某标签时，一并纳入近义标签（OR 查询，有效池翻倍）。
TAG_EXPAND = {
    '智慧': ['才华', '灵秀'],
    '才华': ['智慧', '灵秀'],
    '灵秀': ['智慧', '才华'],
    '温婉': ['安宁', '仁愛'],
    '安宁': ['温婉', '仁愛', '喜悦'],
    '仁愛': ['温婉', '安宁'],
    '喜悦': ['安宁', '光明'],
    '光明': ['喜悦', '俊逸'],
    '俊逸': ['光明', '自由'],
    '自由': ['俊逸', '灵秀'],
    '品德': ['仁愛', '坚韧'],
    '勇敢': ['坚韧', '健康'],
    '坚韧': ['勇敢', '品德'],
    '健康': ['勇敢', '安宁'],
}
# 用户直觉词 → 词表标签（方向4 桥接：不在 TAGS_VOCAB 的选词归并到词表标签）
TAG_ALIASES = {
    '睿': '智慧', '聪明': '智慧', '聪慧': '智慧', '伶俐': '智慧', '智': '智慧',
    '才': '才华', '文': '才华', '诗': '才华', '书': '才华', '艺': '才华',
    '温柔': '温婉', '柔美': '温婉', '文静': '温婉', '婉': '温婉',
    '自然': '灵秀', '山水': '灵秀', '风景': '灵秀', '秀丽': '灵秀',
    '音乐': '才华', '艺术': '才华', '画': '才华',
    '快乐': '喜悦', '开心': '喜悦', '幸福': '喜悦', '欢乐': '喜悦',
    '阳光': '光明', '明亮': '光明', '希望': '光明',
    '帅': '俊逸', '潇洒': '俊逸', '飘逸': '俊逸',
    '随性': '自由', '洒脱': '自由',
    '善良': '品德', '德': '品德',
    '勇': '勇敢', '刚': '勇敢',
    '顽强': '坚韧', '毅力': '坚韧',
    '康': '健康', '安': '安宁',
}

def _expand_tags(tags):
    """把用户所选标签扩展为「原标签 + 近义组 + 别名归并」的查询集合。"""
    if not tags:
        return set()
    out = set()
    for t in tags:
        t = TAG_ALIASES.get(t, t)
        out.add(t)
        out.update(TAG_EXPAND.get(t, []))
    return out

# 自由期许 → 标签 本地关键词词典（零 AI，覆盖直觉词；命中即返回，不调 AI）
_FREE_TEXT_DICT = {
    '睿': '智慧', '聪明': '智慧', '聪慧': '智慧', '智': '智慧',
    '才': '才华', '文': '才华', '诗': '才华', '书': '才华', '艺': '才华',
    '温柔': '温婉', '柔美': '温婉', '文静': '温婉', '婉': '温婉',
    '自然': '灵秀', '山水': '灵秀', '风景': '灵秀', '秀丽': '灵秀',
    '快乐': '喜悦', '开心': '喜悦', '幸福': '喜悦', '欢乐': '喜悦',
    '阳光': '光明', '明亮': '光明', '希望': '光明',
    '帅': '俊逸', '潇洒': '俊逸', '飘逸': '俊逸',
    '随性': '自由', '洒脱': '自由',
    '善良': '品德', '德': '品德',
    '勇': '勇敢', '刚': '勇敢',
    '顽强': '坚韧', '毅力': '坚韧',
    '康': '健康', '安': '安宁',
}
