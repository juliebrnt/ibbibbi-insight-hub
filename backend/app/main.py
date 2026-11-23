"""FastAPI entry point: API, optional password gate and the built frontend."""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from collections import defaultdict

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .api.routes import router
from .config import APP_PASSWORD, FRONTEND_DIST, SESSION_SECRET

log = logging.getLogger("insight_hub")
app = FastAPI(title="Insight Hub", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(GZipMiddleware, minimum_size=1000)
# Session cookie: an HMAC of a server secret, so the cookie never reveals anything about the password.
SESSION = hmac.new(SESSION_SECRET.encode(), b"insight-hub-session-v1", hashlib.sha256).hexdigest() if APP_PASSWORD else None
PUBLIC = {"/api/login", "/api/logout", "/api/session", "/api/collect/submit"}
_attempts: dict[str, list[float]] = defaultdict(list)


def _https(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"


@app.middleware("http")
async def gate(request: Request, call_next):
    path = request.url.path
    if SESSION and path.startswith("/api") and path not in PUBLIC and not hmac.compare_digest(request.cookies.get("ihub", ""), SESSION):
        return JSONResponse({"error": "Please sign in.", "login": True}, status_code=401)
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
    if _https(request):
        resp.headers["Strict-Transport-Security"] = "max-age=31536000"
    return resp


@app.exception_handler(Exception)
async def friendly(_request: Request, exc: Exception):
    log.exception("Unhandled error")
    return JSONResponse({"error": "Something went wrong on our side. Your data is safe; please try again."}, status_code=500)


class Login(BaseModel):
    password: str


@app.get("/api/session")
def session(request: Request):
    needed = bool(SESSION)
    return {"login_required": needed, "signed_in": (not needed) or hmac.compare_digest(request.cookies.get("ihub", ""), SESSION or "")}


@app.post("/api/login")
def login(body: Login, request: Request):
    if not SESSION:
        return {"ok": True}
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0].strip()
    now = time.time()
    _attempts[ip] = [t for t in _attempts[ip] if now - t < 900]
    if len(_attempts[ip]) >= 10:
        return JSONResponse({"error": "Too many attempts. Please wait 15 minutes and try again."}, status_code=429)
    if not hmac.compare_digest(body.password.encode(), APP_PASSWORD.encode()):
        _attempts[ip].append(now)
        return JSONResponse({"error": "That password is not right."}, status_code=401)
    _attempts.pop(ip, None)
    resp = JSONResponse({"ok": True})
    resp.set_cookie("ihub", SESSION, httponly=True, samesite="lax", secure=_https(request), max_age=60 * 60 * 24 * 30)
    return resp


@app.post("/api/logout")
def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("ihub")
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
