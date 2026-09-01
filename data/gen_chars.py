# -*- coding: utf-8 -*-
"""用 agnes-ai 一次性批量扩充 good_chars.json（构建期，运行时零 AI 成本）。"""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import ai, core

DATA = HERE
GOOD = os.path.join(DATA, "good_chars.json")

ch = core.chars()
existing = json.load(open(GOOD, encoding="utf-8"))
seen = {it["c"] for it in existing}

TAGS = ['智慧','才华','健康','安宁','光明','品德','勇敢','温婉','灵秀','仁愛','喜悦','自由','俊逸','坚韧']
batches = [TAGS[:7], TAGS[7:]]

def parse_json(text):
    t = (text or "").strip()
    if t.startswith("```"):
        t = t[3:]
    if t.endswith("```"):
        t = t[:-3]
    t = t.strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    for a, b in (("{", "}"), ("[", "]")):
        s = t.find(a); e = t.rfind(b)
        if s >= 0 and e > s:
            try:
                return json.loads(t[s:e + 1])
            except Exception:
                pass
    return None

new_items = []
for bi, batch in enumerate(batches):
    system = ("你是中文命名用字专家。请基于给定的寓意标签，为宝宝取名推荐合适的简体中文单字。"
              "必须只输出一个 JSON 对象，结构为：{\"标签\": [{\"c\":\"单汉字\",\"m\":\"字义(12字内,积极美好)\",\"g\":\"M或F或U\"}]}，"
              "g 表示性别倾向：M男、F女、U中性。每个标签务必给出 10 到 14 个不重复的单字，男女中性尽量均衡。"
              "字义积极美好，不要任何额外说明文字，只输出 JSON 本身。")
    user = ("标签列表（请严格照抄这些标签作为 JSON 的键）：" + "、".join(batch) +
            "\n每个标签下给出 10-14 个不重复单字。请按上述结构返回。")
    ok = False
    for attempt in range(2):
        try:
            resp = ai._call(system, user, maxtok=2600, timeout=90)
            data = parse_json(resp)
            if not isinstance(data, dict):
                raise ValueError("not dict: " + resp[:120])
            for tag, lst in data.items():
                if tag not in batch or not isinstance(lst, list):
                    continue
                for it in lst:
                    c = (it.get("c") or "").strip()
                    if len(c) != 1 or not ('\u4e00' <= c <= '\u9fff'):
                        continue
                    if c in seen:
                        continue
                    if not ch.get(c):
                        continue
                    m = (it.get("m") or "").strip()[:24]
                    g = it.get("g")
                    if g not in ("M", "F", "U"):
                        g = "U"
                    new_items.append({"c": c, "m": m, "t": [tag], "g": g})
                    seen.add(c)
            ok = True
            break
        except Exception as ex:
            print(f"  batch{bi} attempt{attempt} err: {ex}", flush=True)
            time.sleep(10)
    print(f"batch{bi} {'done' if ok else 'FAILED'} 累计新增 {len(new_items)}", flush=True)
    time.sleep(5)

merged = existing + new_items
json.dump(merged, open(GOOD, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"TOTAL={len(merged)} NEW={len(new_items)}", flush=True)
