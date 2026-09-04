from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import os
from core import generate, analyze_birth, analyze_given_name, map_free_text_to_tags, ai_review_for_name, TAGS_VOCAB
from ai import star_review as star_review_ai

HERE = os.path.dirname(os.path.abspath(__file__))
app = FastAPI()

# 仅本地 uvicorn 用的示例兜底：core 计算异常（缺依赖/无网络等）时，
# 返回一份示例名卡，方便本地 8011 也能走通「揭晓→候选名单」全流程做前端验证。
# Vercel 生产环境不部署 app.py（由 api/*.py 处理），此兜底完全不影响线上。
SAMPLE_GENERATE = {"names":[
  {"name":"星澜","total":92,"dims":{"wuxing":88,"zodiac":90,"pronounce":85,"meaning":86,"stroke":80,"gender":88},
   "rank_reason":"五行相生、音形俱佳，综合评分最高。",
   "explain":[{"label":"五行","text":"水木相生，根基安稳。"},{"label":"音律","text":"平仄相协，读来清亮。"}]},
  {"name":"昭明","total":89,"dims":{"wuxing":85,"zodiac":87,"pronounce":90,"meaning":88,"stroke":82,"gender":86},
   "rank_reason":"字义光明，意象开阔。",
   "explain":[{"label":"字义","text":"昭如日月，明德惟馨。"},{"label":"数理","text":"五格诸数安稳。"}]},
  {"name":"清晏","total":87,"dims":{"wuxing":90,"zodiac":84,"pronounce":83,"meaning":88,"stroke":79,"gender":85},
   "rank_reason":"五行补水，气韵清和。",
   "explain":[{"label":"五行","text":"水旺而润，气脉通畅。"},{"label":"意境","text":"海晏河清，太平之象。"}]},
], "meta":{"source":"local-mock"}}
SAMPLE_ANALYZE = {"names":[
  {"name":"示例名","total":84,"dims":{"wuxing":82,"zodiac":80,"pronounce":88,"meaning":85,"stroke":78,"gender":82},
   "rank_reason":"本地示例数据，仅供前端流程预览。",
   "explain":[{"label":"音律","text":"读音清亮成调。"},{"label":"字义","text":"字义可取。"}]},
], "meta":{"source":"local-mock"}}

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
    try:
        names, meta = generate(father, mother, mode, name_len, gender, birth, tags, avoid, weights=weights)
        return JSONResponse({"names": names, "meta": meta, "tags_used": sorted(set(tags))})
    except Exception as e:
        # 本地兜底：core 计算失败也返回示例名卡，保证前端流程可预览
        return JSONResponse({**SAMPLE_GENERATE, "meta": {"source": "local-mock", "error": str(e)}})

@app.post("/api/analyze")
async def analyze(req: Request):
    """能力 B：直接分析用户提供的候选名字，输出与生成结果同格式。"""
    body = await req.json()
    name = (body.get("name") or "").strip()
    gender = body.get("gender") or "U"
    birth = _birth_from(body)
    try:
        names, meta = analyze_given_name(name, gender, birth)
        return JSONResponse({"names": names, "meta": meta})
    except Exception as e:
        return JSONResponse({**SAMPLE_ANALYZE, "meta": {"source": "local-mock", "error": str(e)}})

@app.post("/api/bazi")
async def bazi(req: Request):
    """根据年/月/日/时现场推算八字、日主、旺衰、喜用神、生肖、五行计数（生辰弹窗用）。"""
    body = await req.json()
    b = body.get("birth") or {}
    try:
        year = int(b.get("year")); month = int(b.get("month"))
        day = int(b.get("day"));  hour = int(b.get("hour", 12))
    except (TypeError, ValueError):
        return JSONResponse({"error": "生辰参数缺失或非法"}, status_code=400)
    try:
        result = analyze_birth(year, month, day, hour)
    except Exception as e:
        return JSONResponse({"error": "八字推算失败: " + str(e)}, status_code=400)
    return JSONResponse(result)

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

@app.post("/api/star_review")
async def star_review(req: Request):
    """星师详解：以「星师」口吻为某名字生成解读（无 key/失败返回空，前端回退模板）。"""
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
        text = star_review_ai(name, gender, zodiac, need, dims, bazi, primary)
    except Exception as e:
        return JSONResponse({"error": "星师详解生成失败: " + str(e)}, status_code=400)
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
        return FileResponse(abs_fp, headers={"Cache-Control": "no-store, max-age=0"})
    idx = os.path.join(HERE, full_path, "index.html")
    if os.path.isfile(idx):
        return FileResponse(idx, headers={"Cache-Control": "no-store, max-age=0"})
    return JSONResponse({"error": "not found"}, status_code=404)
