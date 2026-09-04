import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from core import analyze_birth

# Vercel Serverless Function：POST /api/bazi
# 给生辰八字弹窗用：根据年/月/日/时计算八字、日主、旺衰、喜用神、生肖、五行计数、缺失五行
app = FastAPI()


@app.post("/api/bazi")
async def bazi(req: Request):
    body = await req.json()
    b = body.get("birth") or {}
    try:
        year = int(b.get("year"))
        month = int(b.get("month"))
        day = int(b.get("day"))
        hour = int(b.get("hour", 12))
    except (TypeError, ValueError):
        return JSONResponse({"error": "生辰参数缺失或非法"}, status_code=400)
    try:
        result = analyze_birth(year, month, day, hour)
    except Exception as e:
        return JSONResponse({"error": "八字推算失败: " + str(e)}, status_code=400)
    return JSONResponse(result)