"""خادم SiiMatchMind AI (FastAPI) — محوّل رفيع فوق api.dispatch.

التشغيل من مجلد backend:
    uvicorn main:app --host 127.0.0.1 --port 8000
(ملاحظة: هذا الملف لم يُشغَّل في بيئة الإنشاء لعدم توفر FastAPI هناك؛ المنطق نفسه مُختبَر عبر server_lite.py.)
"""
import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import api
import autorefresh

app = FastAPI(title="SiiMatchMind AI", description="تحليل وتوقع نتائج مباريات كرة القدم", version=api.VERSION)
FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
MAX_BODY = 64 * 1024


@app.api_route("/api/{path:path}", methods=["GET", "POST", "DELETE"])
async def gateway(path: str, request: Request):
    body = None
    if request.method == "POST":
        raw = await request.body()
        if len(raw) > MAX_BODY:
            return JSONResponse({"error": {"code": "too_large", "params": {}}}, status_code=413)
        if raw:
            try:
                body = json.loads(raw.decode("utf-8"))
            except ValueError:
                return JSONResponse({"error": {"code": "invalid_body", "params": {}}}, status_code=400)
    hdrs = dict(request.headers)
    hdrs["x-smm-peer"] = request.client.host if request.client else ""
    status, obj = api.dispatch(request.method, "/api/" + path, dict(request.query_params), hdrs, body)
    return JSONResponse(obj, status_code=status, headers={"Cache-Control": "no-store"})


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Frame-Options"] = "DENY"
    return resp


@app.on_event("startup")
def _startup():
    autorefresh.start()


@app.get("/{page}.html")
def legal(page: str):
    if page not in ("privacy", "terms"):
        return JSONResponse({"error": {"code": "not_found", "params": {}}}, status_code=404) if not (FRONTEND / f"{page}.html").is_file() else FileResponse(FRONTEND / f"{page}.html")
    html = (FRONTEND / f"{page}.html").read_text(encoding="utf-8")
    return HTMLResponse(html.replace("CONTACT_EMAIL", __import__("os").environ.get("SMM_CONTACT_EMAIL", "CONTACT_EMAIL")))


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/", StaticFiles(directory=FRONTEND), name="frontend")
