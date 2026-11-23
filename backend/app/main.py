"""FastAPI entry point: API, optional password gate and the built frontend."""
from __future__ import annotations

import hashlib
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .api.routes import router
from .config import APP_PASSWORD, FRONTEND_DIST

log = logging.getLogger("insight_hub")
app = FastAPI(title="iBBIBBI Insight Hub", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(GZipMiddleware, minimum_size=1000)
TOKEN = hashlib.sha256(("ihub" + APP_PASSWORD).encode()).hexdigest() if APP_PASSWORD else None


@app.middleware("http")
async def gate(request: Request, call_next):
    path = request.url.path
    if TOKEN and path.startswith("/api") and path not in ("/api/login", "/api/collect/submit") and request.cookies.get("ihub") != TOKEN:
        return JSONResponse({"error": "Please sign in.", "login": True}, status_code=401)
    return await call_next(request)


@app.exception_handler(Exception)
async def friendly(_request: Request, exc: Exception):
    log.exception("Unhandled error")
    return JSONResponse({"error": "Something went wrong on our side. Your data is safe; please try again."}, status_code=500)


class Login(BaseModel):
    password: str


@app.post("/api/login")
def login(body: Login):
    if not TOKEN:
        return {"ok": True}
    if hashlib.sha256(("ihub" + body.password).encode()).hexdigest() != TOKEN:
        return JSONResponse({"error": "That password is not right."}, status_code=401)
    resp = JSONResponse({"ok": True})
    resp.set_cookie("ihub", TOKEN, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)
    return resp


app.include_router(router)

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        f = FRONTEND_DIST / full_path
        if full_path and f.is_file() and FRONTEND_DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(FRONTEND_DIST / "index.html")
