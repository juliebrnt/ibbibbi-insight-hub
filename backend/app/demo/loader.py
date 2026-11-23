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
    plan.seed_demo_plan(ws)
    return {"ok": True, "files": results}
