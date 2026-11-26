"""Load the generated demo files into the separate Demo workspace through the normal pipeline."""
from __future__ import annotations

import subprocess
import sys

from .. import db
from ..config import DEMO_DIR, ROOT
from ..ingest import pipeline
from ..insights import plan

# Left out on purpose so it can be uploaded live during a demo.
HELD_BACK = {"mercadillo_ventas.csv"}


def ensure_files() -> None:
    if not DEMO_DIR.exists() or not any(DEMO_DIR.iterdir()):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_demo_data.py")], check=True)


def clear(ws: str = "demo") -> None:
    with db.locked() as c:
        for t in db.CANONICAL_TABLES:
            c.execute(f"DELETE FROM {t} WHERE ws = ?", [ws])
        for (dsid,) in c.execute("SELECT id FROM datasets WHERE ws = ? AND flexible", [ws]).fetchall():
            c.execute(f'DROP TABLE IF EXISTS "flex_{dsid}"')
        for t in ("datasets", "goals", "decisions"):
            c.execute(f"DELETE FROM {t} WHERE ws = ?", [ws])


# 'Today': only the sources iBBIBBI has now (Shopify, Instagram, the feedback form, website reviews).
# TikTok, Google Analytics, Klaviyo, Instagram comments, shop messages and market sales stay in 'Full potential'.
TODAY_FILES = ["products_export.csv", "customers_export.csv", "shopify_orders_export_2025.csv", "pedidos_shopify_2026.csv",
               "judgeme_reviews_export.csv", "instagram_posts_meta_export.csv", "instagram_resumen_meta.zip", "encuesta_nps_y_mensajes.xlsx"]
TODAY_SKIP_SHEETS = {"Mensajes tienda"}  # shop messages are not part of the feedback form


def load_today(ws: str = "mine") -> dict:
    """Fill a workspace with the example files for the sources iBBIBBI has today, through the normal pipeline."""
    from .. import profile
    ensure_files()
    clear(ws)
    profile.save(ws, profile.DEMO)
    results = []
    for name in TODAY_FILES:
        st = pipeline.stage(name, (DEMO_DIR / name).read_bytes(), ws)
        for t in st["tables"]:
            if t["kind"] != "table" or t.get("sheet") in TODAY_SKIP_SHEETS:
                continue
            res = pipeline.confirm(st["upload_id"], t["index"], t["table_type"], t["mapping"], t["privacy"],
                                   flexible=t["flexible_suggested"], ws=ws)
            results.append({"file": t["name"], "ok": res.get("ok"), "type": res.get("table_type")})
    plan.seed_demo_plan(ws)
    return {"ok": all(r["ok"] for r in results), "files": results}


def add_market_trend(ws: str = "demo") -> None:
    """Add the market-stall sheet as the founders would: an unknown file kept as their own dataset, shown as a trend."""
    st = pipeline.stage("mercadillo_ventas.csv", (DEMO_DIR / "mercadillo_ventas.csv").read_bytes(), ws)
    res = pipeline.confirm(st["upload_id"], 0, None, None, st["tables"][0]["privacy"], flexible=True, ws=ws)
    caja = next(c["column"] for c in res["config"]["columns"] if c["label"].startswith("Caja"))
    pipeline.configure_flexible(res["dataset_id"], {"date": res["config"]["suggestion"]["date"], "value": caja,
                                                    "label": "Market stalls", "value_label": "Caja (€)"})


def load(ws: str = "demo") -> dict:
    ensure_files()
    clear(ws)
    results = []
    order = ["products_export.csv"]  # products first so order lines pick up fabric and line
    files = order + sorted(p.name for p in DEMO_DIR.iterdir() if p.name not in order and p.name not in HELD_BACK and not p.name.startswith("."))
    for name in files:
        path = DEMO_DIR / name
        for r in pipeline.auto_import(name, path.read_bytes(), ws):
            results.append({"file": r["name"], "ok": r.get("ok"), "type": r.get("table_type"), "rows": (r.get("report") or {}).get("imported")})
    add_market_trend(ws)
    plan.seed_demo_plan(ws)
    return {"ok": True, "files": results}
