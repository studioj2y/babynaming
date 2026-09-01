import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from core import TAGS_VOCAB

# Vercel Serverless Function：GET /api/tags
app = FastAPI()


@app.get("/api/tags")
def tags():
    return JSONResponse({"tags": TAGS_VOCAB})
