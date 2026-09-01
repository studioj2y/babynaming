# -*- coding: utf-8 -*-
"""用 agnes-ai 一次性批量扩充 good_chars.json（构建期，运行时零 AI 成本）。

改进：每个标签单独发起一次请求（避免大 JSON 被截断），并用正则抽取完整
{"c","m","g"} 对象，对截断的响应也能尽量利用已生成的片段。
"""
import json, os, sys, re, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import ai, core

DATA = HERE
GOOD = os.path.join(DATA, "good_chars.json")

ch = core.chars()
existing = json.load(open(GOOD, encoding="utf-8"))
seen = {it["c"] for it in existing}

TAGS = ['智慧','才华','健康','安宁','光明','品德','勇敢','温婉','灵秀','仁愛','喜悦','自由','俊逸','坚韧']

OBJ_RE = re.compile(
    r'\{\s*"c"\s*:\s*"([^"]{1})"\s*,\s*"m"\s*:\s*"([^"]*)"\s*,\s*"g"\s*:\s*"(M|F|U)"\s*\}'
)

def parse_objects(text):
    return [(m.group(1), m.group(2)[:24], m.group(3)) for m in OBJ_RE.finditer(text or "")]

new_items = []
for tag in TAGS:
    system = ("你是中文命名用字专家。请基于给定的寓意标签，为宝宝取名推荐合适的简体中文单字。"
              "必须只输出一个 JSON 对象，结构为：{\"标签\": [{\"c\":\"单汉字\",\"m\":\"字义(12字内,积极美好)\",\"g\":\"M或F或U\"}]}，"
              "g 表示性别倾向：M男、F女、U中性。给出 10 到 14 个不重复的单字，男女中性尽量均衡。"
              "字义积极美好，不要任何额外说明文字、不要 markdown 代码块标记，只输出 JSON 本身。")
    user = ("标签（请作为 JSON 的键）：" + tag +
            "\n请按上述结构返回，给出 10-14 个不重复单字。")
    ok = False
    for attempt in range(3):
        try:
            resp = ai._call(system, user, maxtok=700, timeout=60)
            for c, m, g in parse_objects(resp):
                if len(c) != 1 or not ('\u4e00' <= c <= '\u9fff'):
                    continue
                if c in seen:
                    continue
                if not ch.get(c):
                    continue
                new_items.append({"c": c, "m": m, "t": [tag], "g": g})
                seen.add(c)
            ok = True
            break
        except Exception as ex:
            print(f"  {tag} attempt{attempt} err: {ex}", flush=True)
            time.sleep(8)
    print(f"{tag} {'done' if ok else 'FAILED'} 累计新增 {len(new_items)}", flush=True)
    time.sleep(3)

merged = existing + new_items
json.dump(merged, open(GOOD, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"TOTAL={len(merged)} NEW={len(new_items)}", flush=True)
