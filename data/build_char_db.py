import csv, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(HERE, "gsc.csv")
out = os.path.join(HERE, "chars.json")

chars = {}
with open(src, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        word = (row.get("word") or "").strip()
        if not word:
            continue
        try:
            stroke = int(row["stroke_count"])
        except (ValueError, TypeError):
            stroke = 0
        tone_raw = row.get("tone") or ""
        try:
            tone = int(tone_raw) if tone_raw not in ("", "NULL") else 0
        except ValueError:
            tone = 0
        chars[word] = {
            "py": row.get("pinyin") or "",
            "tone": tone,
            "radical": (row.get("radical") or "").strip(),
            "stroke": stroke,
            "wx": (row.get("wuxing") or "").strip(),
            "initial": (row.get("pinyin_initial") or "").strip(),
            "final": (row.get("pinyin_final") or "").strip(),
        }

with open(out, "w", encoding="utf-8") as f:
    json.dump(chars, f, ensure_ascii=False)

print("chars loaded:", len(chars))
missing_wx = sum(1 for v in chars.values() if not v["wx"])
print("chars without wuxing:", missing_wx)
