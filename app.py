from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import os
from core import generate, analyze_birth, analyze_given_name, map_free_text_to_tags, ai_review_for_name, TAGS_VOCAB

HERE = os.path.dirname(os.path.abspath(__file__))
app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def index():
    with open(os.path.join(HERE, "index.html"), encoding="utf-8") as f:
        # no-store：强制浏览器每次都重新拉取最新 HTML，避免旧 JS（残留离屏节点等）被缓存
        return HTMLResponse(f.read(), headers={"Cache-Control": "no-store, max-age=0"})

@app.get("/api/tags")
def tags():
    return {"tags": TAGS_VOCAB}

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

@app.post("/api/analyze")
async def analyze(req: Request):
    """能力 B：直接分析用户提供的候选名字，输出与生成结果同格式。"""
    body = await req.json()
    name = (body.get("name") or "").strip()
    gender = body.get("gender") or "U"
    birth = _birth_from(body)
    names, meta = analyze_given_name(name, gender, birth)
    return JSONResponse({"names": names, "meta": meta})

@app.post("/api/ai_review")
async def ai_review(req: Request):
    """能力1：对某个名字做整盘 AI 积极解读（无 key/失败返回空，前端回退模板）。"""
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

# ---------- 本地开发静态兜底（仅本地生效，Vercel 不部署 app.py） ----------
# Vercel 生产环境由「根静态文件 + api/*.py 函数」处理；此路由仅用于本地 `uvicorn app:app`
# 同时托管 /v2/ 场景前端与 /characters/ 立绘，方便本地调试 2.0，不影响 v1 的 / 与 /api/*。
@app.get("/{full_path:path}")
def serve_static(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse({"error": "not found"}, status_code=404)
    fp = os.path.join(HERE, full_path)
    abs_fp = os.path.abspath(fp)
    if os.path.isfile(fp) and os.path.commonpath([HERE, abs_fp]) == HERE:
        return FileResponse(abs_fp)
    idx = os.path.join(HERE, full_path, "index.html")
    if os.path.isfile(idx):
        return FileResponse(idx)
    return JSONResponse({"error": "not found"}, status_code=404)
