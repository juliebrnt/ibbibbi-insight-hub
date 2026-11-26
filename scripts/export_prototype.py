"""Build a self-contained, shareable prototype of the app with demo data.

1. Loads the demo data into a throwaway database (including the market-stall file as a trend).
2. Records every screen's data for 'Full potential' (all demo files) and 'Today' (only the sources iBBIBBI has now).
3. Builds the frontend in prototype mode and packs JS, CSS and fonts into one page.

Output: prototype/index.html (+ prototype-data.json) for a Claude artifact, and docs/index.html for GitHub Pages
Usage: make prototype
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "prototype"
os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "prototype.duckdb")
os.environ["ANTHROPIC_API_KEY"] = ""
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.ai.ask import SUGGESTED  # noqa: E402
from app.main import app  # noqa: E402


def record() -> dict:
    c = TestClient(app)
    assert c.post("/api/demo/load").json()["ok"]  # Full potential, including the market-stall trend
    assert c.post("/api/demo/load_today").json()["ok"]  # Today
    snap: dict = {}

    def get(path: str):
        r = c.get(f"/api{path}")
        r.raise_for_status()
        snap[path] = r.json()

    for ws in ("demo", "mine"):
        get(f"/status?ws={ws}")
        for page in ("home", "feedback", "social", "sales", "briefing"):
            for rng in ("28d", "90d", "365d", "all"):
                get(f"/{page}?ws={ws}&range={rng}")
        for page in ("plan", "datasets", "settings", "integrations"):
            get(f"/{page}?ws={ws}")
        get(f"/voice?ws={ws}&limit=400")
        for rng in ("28d", "90d", "365d", "all"):
            for plat in ("Instagram", "TikTok"):
                get(f"/social?ws={ws}&range={rng}&platform={plat}")
        for rng in ("28d", "90d", "365d", "all"):
            get(f"/alerts?ws={ws}&range={rng}")
    get("/ask/suggestions")
    get("/reviews/examples")
    snap["__refreshed"] = c.post("/api/refresh", json={"ws": "demo"}).json()["refreshed_at"]
    c.post("/api/refresh", json={"ws": "mine"})
    for ws in ("demo", "mine"):  # pick up the refresh time
        for rng in ("28d", "90d", "365d", "all"):
            get(f"/home?ws={ws}&range={rng}")
        get(f"/integrations?ws={ws}")
        get(f"/status?ws={ws}")
    snap["__suggested"] = SUGGESTED[:4]
    snap["__answers"] = {q: c.post("/api/ask", json={"question": q, "ws": "demo"}).json() for q in SUGGESTED}
    snap["__answers_mine"] = {q: c.post("/api/ask", json={"question": q, "ws": "mine"}).json() for q in SUGGESTED}
    snap["__qr"] = "data:image/svg+xml;charset=utf-8," + c.get("/api/collect/qr?url=https://your-shop.example/feedback").text.replace("#", "%23")
    return snap


def build(snap: dict) -> str:
    env = {**os.environ, "VITE_STATIC": "1"}
    subprocess.run(["npm", "run", "build"], cwd=ROOT / "frontend", env=env, check=True)
    dist = ROOT / "frontend" / "dist-prototype"
    html = (dist / "index.html").read_text()
    css = "".join((dist / "assets" / p).read_text() for p in os.listdir(dist / "assets") if p.endswith(".css"))
    js = "".join((dist / "assets" / p).read_text() for p in os.listdir(dist / "assets") if p.endswith(".js"))
    js = js.replace("</script", "<\\/script")
    favicon = (ROOT / "frontend" / "public" / "favicon.svg").read_text()
    logo = "data:image/svg+xml;charset=utf-8," + re.sub(r"<!--.*?-->", "", favicon).replace("#", "%23").replace("\n", "")
    js = js.replace('"/favicon.svg"', json.dumps(logo))
    assert "<div id=\"root\">" in html
    return (
        '<meta charset="utf-8">\n<title>iBBIBBI Insight Hub</title>\n'
        '<meta name="description" content="Prototype of the iBBIBBI Insight Hub with demo data.">\n'
        f"<style>{css}</style>\n"
        '<div id="root"></div>\n'
        f"<script>window.__PROTOTYPE__ = {json.dumps(snap, ensure_ascii=False, default=str).replace('</', '<\\/')};</script>\n"
        f'<script type="module">{js}</script>\n'
    )


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    snap = record()
    (OUT / "prototype-data.json").write_text(json.dumps(snap, ensure_ascii=False, default=str))
    page = build(json.loads((OUT / "prototype-data.json").read_text()))
    (OUT / "index.html").write_text(page)  # body-only version for a Claude artifact
    # Full standalone page for GitHub Pages (served from docs/)
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    head = ('<!doctype html>\n<html lang="en-GB">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '<meta name="theme-color" content="#FBF8F4">\n')
    body = page.replace('<meta charset="utf-8">\n', "", 1)
    title_end = body.index("</style>") + len("</style>\n")
    (docs / "index.html").write_text(head + body[:title_end] + "</head>\n<body>\n" + body[title_end:] + "</body>\n</html>\n")
    (docs / ".nojekyll").write_text("")
    print(f"Prototype written to {OUT} ({len(page) / 1e6:.1f} MB page, {(OUT / 'prototype-data.json').stat().st_size / 1e6:.1f} MB data)")
