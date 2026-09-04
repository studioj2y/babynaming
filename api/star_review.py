import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from ai import star_review

# Vercel Serverless Function：POST /api/star_review
# 以「星师」口吻生成某名字的解读（无 key/失败返回 None，前端回退模板）。
app = FastAPI()


@app.post("/api/star_review")
async def star_review_ep(req: Request):
    body = await req.json()
    name = body.get("name") or ""
    gender = body.get("gender") or "U"
    zodiac = body.get("zodiac") or None
    need = body.get("need") or None
    dims = body.get("dims") or {}
    bazi = body.get("bazi") or None
    primary = body.get("primary") or None
    if not name:
        return JSONResponse({"error": "缺少名字"}, status_code=400)
    try:
        text = star_review(name, gender, zodiac, need, dims, bazi, primary)
    except Exception as e:
        return JSONResponse({"error": "星师详解生成失败: " + str(e)}, status_code=400)
    if not text:
        return JSONResponse({"review": None})
    return JSONResponse({"review": text})
