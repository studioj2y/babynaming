# -*- coding: utf-8 -*-
"""
星命观测局 · AI 能力接入层（能力 1、5）。

仅在此文件调用大模型，且全部优雅降级：任何异常都返回 None，
由调用方回退到本地模板 / 关键词映射，绝不卡住取名流程。

- 能力1：名字整体积极解读（ai_review）
- 能力5：用户自由期许 → 字库标签映射（map_free_text）

能力 2(重名率)/3(网络撞梗)/4(方言) 依赖外部数据源，不在本文件，
由 core.py 做本地近似并在前端标注「需接入数据源」。
"""
import os, json, ssl, urllib.request
import certifi

BASE_URL = "https://apihub.agnes-ai.com/v1/chat/completions"
MODEL = "agnes-2.5-flash"

# Key：只从环境变量读取（Vercel 后台配置 / 本地 export），不再内置默认值，
# 避免密钥随代码入库。未配置时 _call 会抛异常、由上层优雅降级为「暂无解读」。
API_KEY = os.environ.get("AGNES_API_KEY", "")


def _call(system_prompt, user_content, maxtok=500, timeout=60):
    body = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": maxtok,
        "temperature": 0.75,
    }, ensure_ascii=False).encode("utf-8")
    ctx = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(
        BASE_URL, data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + API_KEY},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"]


def _truncate(text, max_chars):
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    cut = max_chars
    for i in range(max_chars, max(0, max_chars - 40), -1):
        if text[i - 1] in "。！？\n":
            cut = i
            break
    return text[:cut].rstrip("，、；： ") + "…"


# ---------- 能力1：名字整体积极解读 ----------
def ai_review(name, gender, zodiac, need, dims):
    """返回一段约 120 字、积极美好的中文整体解读；失败返回 None。"""
    gd = {'M': '男孩', 'F': '女孩', 'U': '宝宝'}.get(gender, '宝宝')
    need_s = '/'.join(need) if need else '均衡'
    dim_s = '、'.join(f"{k}{v}" for k, v in (dims or {}).items() if v is not None)
    system = (
        "你是「星命观测局」的命名解读师，气质温润、有文化韵味。\n"
        "请用温暖、积极、鼓励的中文，为家长刚为宝宝择定的名字做一段整体解读。"
        "从五行、生肖、音律、字义、意境等角度自然串联，多说好话与美好期许，"
        "不宿命、不吓人。使用纯中文，不要任何 markdown 格式。"
        "总字数控制在 130 字以内。"
    )
    user = (
        f"名字：{name}\n性别：{gd}\n生肖：{zodiac or '未提供'}\n"
        f"宜补五行：{need_s}\n各维度参考评分：{dim_s}\n"
        f"请据此写一段积极美好的整体解读。"
    )
    try:
        return _truncate(_call(system, user, maxtok=400), 160)
    except Exception:
        return None


# ---------- 能力5：自由期许 → 字库标签映射 ----------
def map_free_text(free_text, vocab):
    """把用户自由描述映射为 vocab 中的 1-4 个标签；失败返回 None（调用方回退关键词）。"""
    if not free_text or not vocab:
        return None
    system = (
        "你是命名助手。用户用日常语言描述对宝宝的期许。\n"
        "请从给定的标签列表中挑选最相关的 1 到 4 个标签。\n"
        "只输出选中的标签，用顿号分隔，不要任何其他文字、标点或解释。"
    )
    user = f"可选标签：{'、'.join(vocab)}\n用户期许：{free_text}"
    try:
        out = _call(system, user, maxtok=80, timeout=40)
        picks = [t.strip() for t in out.replace('，', '、').replace(',', '、').split('、') if t.strip() in vocab]
        return picks[:4] if picks else None
    except Exception:
        return None


# ---------- 能力（星师详解）：AI 以「星师」口吻生成名字解读 ----------
def star_review(name, gender, zodiac, need, dims, bazi, primary):
    """以「星师」古朴温润、带玄学意境的口吻，生成约 150 字名字解读；失败返回 None。"""
    gd = {'M': '男孩', 'F': '女孩', 'U': '宝宝'}.get(gender, '宝宝')
    need_s = '/'.join(need) if need else '均衡'
    dim_s = '、'.join(f"{k}{v}" for k, v in (dims or {}).items() if v is not None)
    prim = primary or '综合'
    bazi_s = ''
    if bazi and isinstance(bazi, dict):
        gz = bazi.get('gz') or ''
        dm = (bazi.get('day_master') or '') + (bazi.get('day_master_wx') or '')
        strong = bazi.get('strong') or ''
        useg = '、'.join(bazi.get('use_gods') or []) or ''
        zod = bazi.get('zodiac') or ''
        if gz or dm:
            bazi_s = f"八字：{gz}；日主：{dm}；旺衰：{strong}；喜用：{useg}；生肖：{zod}"
    system = (
        "你是「星命观测局」的星师，一位德高望重的命名宗匠。\n"
        "你语调古朴温润、带玄学意境与诗性，善用比喻，从容不迫，如与友人对坐夜话。\n"
        "请为这个名字写一段约 150 字的解读，自然融入五行、生肖、音律、字义、意境与命局喜用，\n"
        "不宿命、不吓人，多作美好期许。使用纯中文，不要任何 markdown 格式、不要标题。\n"
        f"今日主理侧重为「{prim}」，可稍加呼应。"
    )
    user = (
        f"名字：{name}\n性别：{gd}\n生肖：{zodiac or '未提供'}\n"
        f"宜补五行：{need_s}\n各维度评分：{dim_s}\n{bazi_s}\n"
        f"请星师以此名做一段解读。"
    )
    try:
        return _truncate(_call(system, user, maxtok=500), 200)
    except Exception:
        return None
