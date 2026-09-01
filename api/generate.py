import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from core import generate, map_free_text_to_tags, analyze_birth

# Vercel Serverless Function：POST /api/generate
app = FastAPI()


def _birth_from(body):
    b = body.get("birth")
    if b and b.get("year"):
        try:
            return analyze_birth(int(b["year"]), int(b["month"]), int(b["day"]), int(b.get("hour", 12)))
        except Exception:
            return None
    return None


@app.post("/api/generate")
async def gen(req: Request):
    body = await req.json()
    father = (body.get("father") or "").strip()
    mother = (body.get("mother") or "").strip()
    mode = body.get("mode") or "F"
    name_len = int(body.get("name_len") or 3)
    gender = body.get("gender") or "U"
    tags = list(body.get("tags") or [])
    # 能力5：自由期许 → 标签（AI 优先，失败回退关键词）
    free_text = (body.get("free_text") or "").strip()
    if free_text:
        tags += map_free_text_to_tags(free_text)
    avoid = [c for c in (body.get("avoid") or "") if c.strip()]
    birth = _birth_from(body)
    weights = body.get("weights")
    names, meta = generate(father, mother, mode, name_len, gender, birth, tags, avoid, weights=weights)
    return JSONResponse({"names": names, "meta": meta, "tags_used": sorted(set(tags))})
