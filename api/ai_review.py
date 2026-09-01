import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from core import ai_review_for_name

# Vercel Serverless Function：POST /api/ai_review
# 能力1：对某个名字做整盘 AI 积极解读（无 key/失败返回 None，前端回退模板）。
app = FastAPI()


@app.post("/api/ai_review")
async def ai_review(req: Request):
    body = await req.json()
    name = body.get("name") or ""
    gender = body.get("gender") or "U"
    zodiac = body.get("zodiac") or None
    need = body.get("need") or None
    dims = body.get("dims") or {}
    try:
        text = ai_review_for_name(
            {"name": name, "req_gender": gender, "dims": dims},
            {"zodiac": zodiac, "need": need},
        )
    except Exception:
        text = None
    if not text:
        return JSONResponse({"review": None})
    return JSONResponse({"review": text})
