"""Collect every user-facing English string (API output and interface code) and report translation coverage.

Usage: python scripts/harvest_strings.py [--out missing.txt]
Writes the templates that have no Spanish translation yet, most frequent first.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))
os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "harvest.duckdb")
os.environ["ANTHROPIC_API_KEY"] = ""

from shared import i18n_core as i18n  # noqa: E402

SKIP_KEYS = {"text", "caption", "product", "campaign", "file_name", "id", "_key", "post_id", "reply_text", "draft", "sql", "url", "admin_url",
             "docs", "icon", "key", "sheet", "name_raw", "channel", "source_raw", "heard_from", "colour", "theme", "pillar", "format", "group",
             "category", "language", "platform", "kind", "status", "live", "tone", "direction", "metric", "sentiment", "unit", "page", "linked_goal_key"}
LOOKS_ENGLISH = re.compile(r"[A-Za-z]{3,}")
NOT_TEXT = re.compile(r"^(https?://|/|c_|ds_|up_|g_|d_|#|\d{4}-\d{2}-\d{2}|[a-z_]+:[a-z_]+|[a-z0-9_]+$)")


def walk(obj, out: Counter):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k not in SKIP_KEYS:
                walk(v, out)
    elif isinstance(obj, list):
        for v in obj:
            walk(v, out)
    elif isinstance(obj, str) and LOOKS_ENGLISH.search(obj) and not NOT_TEXT.match(obj) and len(obj) < 600:
        out[obj.strip()] += 1


def api_strings() -> Counter:
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    c.post("/api/demo/load")
    for f in sorted((ROOT / "test_pack").rglob("*.*")):  # a second, different business in My data
        if f.suffix in (".md",):
            continue
        st = c.post("/api/upload", files={"files": (f.name, f.read_bytes())}, data={"ws": "mine"}).json()[0]
        for t in st.get("tables", []):
            c.post("/api/import", json={"upload_id": st["upload_id"], "index": t["index"], "table_type": t.get("table_type"), "mapping": t.get("mapping"),
                                        "privacy": t.get("privacy"), "flexible": t.get("flexible_suggested"), "ws": "mine"})
    out: Counter = Counter()
    for ws in ("demo", "mine"):
        for page in ("home", "feedback", "social", "sales", "briefing", "alerts", "insights"):
            for rng in ("28d", "90d", "365d", "all"):
                walk(c.get(f"/api/{page}?ws={ws}&range={rng}").json(), out)
        for page in ("plan", "datasets", "settings", "integrations", "status"):
            walk(c.get(f"/api/{page}?ws={ws}").json(), out)
        walk(c.get(f"/api/social?ws={ws}&platform=TikTok").json(), out)
        walk(c.get(f"/api/voice?ws={ws}&limit=200").json(), out)
        walk(c.post("/api/refresh", json={"ws": ws}).json(), out)
        from app.ai.ask import SUGGESTED
        for q in SUGGESTED + ["nonsense question about the weather"]:
            walk(c.post("/api/ask", json={"question": q, "ws": ws}).json(), out)
    walk(c.get("/api/ask/suggestions").json(), out)
    walk(c.get("/api/reviews/examples").json(), out)
    walk(c.get("/api/metrics").json(), out)
    st = c.post("/api/upload", files={"files": ("empty.csv", b"")}, data={"ws": "mine"}).json()[0]
    walk(st, out)
    return out


JSX_TEXT = re.compile(r">([^<>{}]*[A-Za-z]{2,}[^<>{}]*)<")
ATTR = re.compile(r"""\b(?:placeholder|aria-label|title|label|description|help|hint|what|why|todo|body|message|how|unit|period|source)=?\s*[:=]?\s*["']([^"'\n]{3,})["']""")
STR = re.compile(r'"((?:[A-Z][^"\n]*?[a-z][^"\n]*?))"')


def ui_strings() -> Counter:
    out: Counter = Counter()
    for f in (ROOT / "frontend" / "src").rglob("*.ts*"):
        src = f.read_text(encoding="utf-8")
        for rx in (JSX_TEXT, ATTR, STR):
            for m in rx.finditer(src):
                s = " ".join(m.group(1).split())
                if LOOKS_ENGLISH.search(s) and not re.search(r"[{}=;]|className|\.tsx?$|^[a-z-]+$|^(rgb|var)\(|\b(bg|text|px|py|min|max)-", s):
                    out[s] += 1
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "shared" / "i18n" / "missing.txt"))
    a = ap.parse_args()
    strings = api_strings() + ui_strings()
    templates: Counter = Counter()
    for s, n in strings.items():
        t, _ = i18n.templatize(s)
        templates[t] += n
    exact, patterns = i18n.catalog()

    def covered(t: str) -> bool:
        if t in exact:
            return True
        return any(rx.match(t) for rx, _ in patterns)
    noise = re.compile(r"^[{}0-9\s.,:;%€·()+\-–—/x|]*$|^[a-z_,]+$|^(Instagram|TikTok|Shopify|Klaviyo|Mailchimp|HubSpot|LinkedIn|Etsy|WooCommerce|Trustpilot|"
                       r"Google Analytics( 4)?|Google Search Console|Judge\.me|Amazon Seller Central|Facebook( Page)?|WhatsApp|Email|Reel|Carousel|Video|"
                       r"Insight Hub|iBBIBBI|NPS|SKU|CSV|ZIP|PDF|GA4|URL|OK|Tienda física|Teléfono|Castellano|Català|English|Your business)$")
    data_like = re.compile(r"(\(path: string|&&|\? *$|^limit \?|, label:|Content-Type|^[a-z]+\.[a-z_.]+$|\.com$|\.org$|[¿¡]|habría|pequeña|cuándo|tenéis|algún|Feu-ne|Quina|Would love|Does it fit|BIENVENIDA|OCTUBRE|AMIGA|^Fecha$|^Producto$|^Unidades$|Importe|Piezas|Caja|Tiempo|Comentario|Shop sales with|bambú|algodón|seda|Turbante|Pañuelo|Gorrito|Gorro|Bandana|Pack Regalo|Mercat|Mercadillo|Fira|@example|\.csv|\.xlsx|\.json|\.txt|\.docx|\.zip)")
    templates = Counter({t: n for t, n in templates.items() if not noise.match(t) and not data_like.search(t)})
    missing = [(t, n) for t, n in templates.most_common() if not covered(t)]
    total = len(templates)
    Path(a.out).write_text("\n".join(t for t, _ in missing), encoding="utf-8")
    print(f"{total} distinct strings, {total - len(missing)} translated ({(total - len(missing)) / max(total, 1) * 100:.0f}%), {len(missing)} missing -> {a.out}")
