import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from core import analyze_given_name, analyze_birth

# Vercel Serverless Function：POST /api/analyze
app = FastAPI()


def _birth_from(body):
    b = body.get("birth")
    if b and b.get("year"):
        try:
            return analyze_birth(int(b["year"]), int(b["month"]), int(b["day"]), int(b.get("hour", 12)))
        except Exception:
            return None
    return None


@app.post("/api/analyze")
async def analyze(req: Request):
    body = await req.json()
    name = (body.get("name") or "").strip()
    gender = body.get("gender") or "U"
    birth = _birth_from(body)
    names, meta = analyze_given_name(name, gender, birth)
    return JSONResponse({"names": names, "meta": meta})
