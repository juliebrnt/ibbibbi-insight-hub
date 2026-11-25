"""Upload pipeline: read, profile, classify, privacy check, map, validate, import, undo."""
from __future__ import annotations

import json
import pickle
import re
import uuid
from datetime import datetime

import pandas as pd

from .. import db
from ..analytics import text as tx
from ..config import STAGING_DIR, UPLOAD_DIR
from ..privacy import pii
from . import transform as tf
from .classify import classify, fingerprint, source_label, text_stats
from .parsing import date_rate, date_series, number_rate, number_series
from .readers import RawTable, ReadError, read_file
from .registry import TYPES

AUTO_ACCEPT = 0.6
FIELD_KIND = {t.key: {f.name: f.kind for f in t.fields} for t in TYPES.values()}


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


# --------------------------------------------------------------------------------------
# Profiling
# --------------------------------------------------------------------------------------
def profile(df: pd.DataFrame) -> list[dict]:
    out = []
    for c in df.columns:
        s = df[c]
        n = len(s)
        nonnull = s.dropna()
        nonnull = nonnull[nonnull.astype(str).str.strip() != ""]
        info = {"column": c, "null_rate": round(1 - len(nonnull) / n, 3) if n else 1.0, "unique": int(nonnull.astype(str).nunique()),
                "examples": [str(v)[:60] for v in nonnull.astype(str).drop_duplicates().head(3)]}
        if date_rate(nonnull) >= 0.8:
            d = date_series(nonnull)
            info.update(type="date", min=str(d.min().date()) if d.notna().any() else None, max=str(d.max().date()) if d.notna().any() else None)
        elif number_rate(nonnull) >= 0.8:
            x = number_series(nonnull)
            info.update(type="number", min=float(x.min()) if x.notna().any() else None, max=float(x.max()) if x.notna().any() else None,
                        mean=round(float(x.mean()), 2) if x.notna().any() else None)
        else:
            avg = nonnull.astype(str).str.len().mean() if len(nonnull) else 0
            if avg >= 20:
                info.update(type="text", avg_length=round(float(avg), 1),
                            language=_dominant_language(nonnull.astype(str).head(40).tolist()))
            else:
                info.update(type="category")
        out.append(info)
    return out


def _dominant_language(texts: list[str]) -> str:
    counts: dict[str, int] = {}
    for t in texts:
        lang = tx.detect_language(t)
        counts[lang] = counts.get(lang, 0) + 1
    return max(counts, key=counts.get) if counts else "unknown"


def preview(df: pd.DataFrame, n: int = 6) -> list[dict]:
    head = df.head(n).astype(object)
    return [{k: (None if v is None or (isinstance(v, float) and pd.isna(v)) else (v.isoformat() if hasattr(v, "isoformat") else str(v)[:80]))
             for k, v in r.items()} for r in head.to_dict(orient="records")]


# --------------------------------------------------------------------------------------
# Stage (read + analyse, nothing stored in canonical tables yet)
# --------------------------------------------------------------------------------------
def stage(file_name: str, data: bytes, ws: str) -> dict:
    upload_id = new_id("up")
    (UPLOAD_DIR / f"{upload_id}_{re.sub(r'[^A-Za-z0-9._-]', '_', file_name)}").write_bytes(data)
    try:
        tables = read_file(file_name, data)
    except ReadError as e:
        return {"upload_id": upload_id, "file_name": file_name, "error": str(e), "tables": []}
    except Exception:  # noqa: BLE001
        return {"upload_id": upload_id, "file_name": file_name, "tables": [],
                "error": "Something in this file confused us. Try saving it as CSV or Excel and upload again."}
    tables = [t for t in tables if t.kind_hint == "image" or len(t.df)]
    if not tables:
        return {"upload_id": upload_id, "file_name": file_name, "tables": [],
                "error": "This file is empty. Try exporting it again, and check you picked a date range that has data."}
    staged = []
    for i, rt in enumerate(tables):
        staged.append(analyse_table(rt, i))
    with open(STAGING_DIR / f"{upload_id}.pkl", "wb") as f:
        pickle.dump({"tables": tables, "ws": ws, "file_name": file_name}, f)
    return {"upload_id": upload_id, "file_name": file_name, "tables": staged}


def analyse_table(rt: RawTable, index: int) -> dict:
    df = rt.df
    if rt.kind_hint == "image":
        return {"index": index, "name": rt.name, "kind": "image", "rows": 0, "columns": [], "candidates": [],
                "message": "Screenshot received. With AI analysis on we can read the numbers from it; otherwise it is stored for reference."}
    cands = classify(df, rt.file_name, rt.kind_hint)
    fp = fingerprint(list(df.columns))
    recipe = db.rows("SELECT * FROM recipes WHERE fingerprint = ?", [fp])
    top = cands[0]
    chosen_type, mapping = top.table_type, top.mapping
    if recipe:
        chosen_type = recipe[0]["table_type"]
        mapping = json.loads(recipe[0]["mapping"]) if isinstance(recipe[0]["mapping"], str) else recipe[0]["mapping"]
    flexible = not recipe and top.confidence < AUTO_ACCEPT
    privacy = pii.detect(df, mapping)
    if recipe and recipe[0].get("privacy"):
        saved = json.loads(recipe[0]["privacy"]) if isinstance(recipe[0]["privacy"], str) else recipe[0]["privacy"]
        saved_map = {p["column"]: p["action"] for p in saved}
        for p in privacy:
            if p["column"] in saved_map:
                p["action"] = saved_map[p["column"]]
                p["explain"] = pii.EXPLAIN[p["action"]]
    return {
        "index": index, "name": rt.name, "sheet": rt.sheet, "kind": "table", "rows": int(len(df)), "columns": list(df.columns),
        "fingerprint": fp, "recipe": bool(recipe), "flexible_suggested": flexible,
        "table_type": None if flexible else chosen_type,
        "label": source_label(chosen_type, rt.file_name, df) if not flexible else "Something new",
        "confidence": 1.0 if recipe else top.confidence,
        "mapping": mapping if not flexible else {},
        "candidates": [{"table_type": c.table_type, "label": c.label, "confidence": c.confidence, "mapping": c.mapping,
                        "missing_required": c.missing_required} for c in cands[:4]],
        "fields": {k: [{"name": f.name, "label": f.label, "kind": f.kind, "required": f.required} for f in t.fields] for k, t in TYPES.items()},
        "profile": profile(df), "preview": preview(df), "privacy": privacy, "notes": rt.notes,
        "delimiter": df.attrs.get("delimiter"), "header_row": df.attrs.get("header_row", 0) + 1,
    }


def _load_staged(upload_id: str) -> dict:
    path = STAGING_DIR / f"{upload_id}.pkl"
    if not path.exists():
        raise ReadError("This upload has expired. Please drop the file again.")
    with open(path, "rb") as f:
        return pickle.load(f)


# --------------------------------------------------------------------------------------
# Import
# --------------------------------------------------------------------------------------
def confirm(upload_id: str, index: int, table_type: str | None, mapping: dict | None, privacy: list[dict] | None,
            mode: str = "new_only", save_recipe: bool = True, flexible: bool = False, ws: str | None = None) -> dict:
    st = _load_staged(upload_id)
    rt: RawTable = st["tables"][index]
    ws = ws or st["ws"]
    df = rt.df
    first_row = int(df.attrs.get("first_data_row", 2))
    if privacy is None:
        privacy = pii.detect(df, mapping or {})
    clean = pii.apply(df, privacy)
    dataset_id = new_id("ds")
    if flexible or not table_type:
        return import_flexible(dataset_id, rt, clean, ws, privacy)
    t = TYPES[table_type]
    mapping = {k: v for k, v in (mapping or {}).items() if v and v.get("column") in clean.columns}
    missing = [f.label for f in t.fields if f.required and f.name not in mapping]
    if missing:
        return {"ok": False, "error": f"Please tell us which column holds: {', '.join(missing)}."}
    report = tf.Report()
    label = source_label(table_type, rt.file_name, df)
    try:
        frames = tf.transform(table_type, clean, mapping, report, first_row, label)
    except ValueError as e:
        return {"ok": False, "error": f"We could not import this as {t.label.lower()}: {e}."}
    total_imported = 0
    dmin, dmax = None, None
    with db.locked() as c:
        for table, frame in frames.items():
            frame = frame.drop_duplicates("_key")
            before = len(frame)
            existing = set(r[0] for r in c.execute(f"SELECT _key FROM {table} WHERE ws = ?", [ws]).fetchall())
            if mode == "replace" and existing:
                keys = [k for k in frame["_key"] if k in existing]
                if keys:
                    c.execute(f"DELETE FROM {table} WHERE ws = ? AND _key IN (SELECT unnest(?))", [ws, keys])
            elif existing:
                frame = frame[~frame["_key"].isin(existing)]
            dup = before - len(frame)
            if table in ("orders", "feedback", "social_posts", "web_sessions", "email_campaigns", "social_comments"):
                report.duplicates += dup
            frame = frame.assign(ws=ws, dataset_id=dataset_id)
            cols = [x.split()[0] for x in db.SCHEMA[table].replace("\n", " ").split(",")]
            cols = [x.strip() for x in cols]
            for x in cols:
                if x not in frame.columns:
                    frame[x] = None
            frame = frame[cols]
            if len(frame):
                c.register("_incoming", frame)
                c.execute(f"INSERT INTO {table} SELECT * FROM _incoming")
                c.unregister("_incoming")
            if table not in ("order_items",):
                total_imported += len(frame)
            if "date" in frame.columns and frame["date"].notna().any():
                ds = pd.to_datetime(frame["date"])
                dmin = min(filter(None, [dmin, ds.min().date()]))
                dmax = max(filter(None, [dmax, ds.max().date()]))
        enrich(c, ws)
    report.imported = total_imported
    if report.duplicates:
        report.notes.append(f"Skipped {report.duplicates:,} rows you had already imported, so nothing is counted twice.")
    quality = quality_score(report)
    db.execute("INSERT INTO datasets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        dataset_id, ws, rt.file_name, rt.sheet, table_type, label, 1.0, fingerprint(list(df.columns)), report.rows_in, report.imported,
        report.skipped, report.fixed, dmin, dmax, quality, datetime.now(), json.dumps(mapping), json.dumps(report.__dict__), False, None,
        "active"])
    if save_recipe:
        db.execute("INSERT OR REPLACE INTO recipes VALUES (?,?,?,?,?,?)", [fingerprint(list(df.columns)), table_type, json.dumps(mapping),
                                                                            json.dumps(privacy), label, datetime.now()])
    return {"ok": True, "dataset_id": dataset_id, "label": label, "table_type": table_type, "report": report.__dict__, "quality": quality}


def quality_score(r: tf.Report) -> float:
    if not r.rows_in:
        return 0.0
    return round(max(0.0, 1 - r.skipped / max(r.rows_in, 1) - 0.002 * len(r.issues)), 2)


def enrich(c, ws: str) -> None:
    """Fill product attributes from the product catalogue when it is available."""
    c.execute("""UPDATE order_items SET fabric = coalesce(p.fabric, order_items.fabric), line = coalesce(p.line, order_items.line),
                 colour = coalesce(p.colour, order_items.colour)
                 FROM products p WHERE p.ws = order_items.ws AND p.sku = order_items.sku AND order_items.ws = ?""", [ws])
    c.execute("""UPDATE feedback SET line = coalesce(p.line, feedback.line), fabric = coalesce(p.fabric, feedback.fabric)
                 FROM products p WHERE p.ws = feedback.ws AND p.product = feedback.product AND feedback.ws = ?""", [ws])


def safe_col(name: str, used: set) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", tf.norm(name)).strip("_") or "col"
    if base[0].isdigit():
        base = "c_" + base
    n, out = 1, base
    while out in used:
        n += 1
        out = f"{base}_{n}"
    used.add(out)
    return out


def import_flexible(dataset_id: str, rt: RawTable, df: pd.DataFrame, ws: str, privacy: list[dict]) -> dict:
    prof = profile(df)
    used: set = set()
    cols, typed = [], pd.DataFrame(index=df.index)
    for p in prof:
        name = safe_col(p["column"], used)
        if p["type"] == "date":
            typed[name] = date_series(df[p["column"]])
        elif p["type"] == "number":
            typed[name] = number_series(df[p["column"]])
        else:
            typed[name] = df[p["column"]].astype(object).where(df[p["column"]].notna(), None).map(lambda v: None if v is None else str(v))
        cols.append({"column": name, "label": p["column"], "type": p["type"]})
    typed["row_num"] = df.index + int(df.attrs.get("first_data_row", 2))
    table = f"flex_{dataset_id}"
    with db.locked() as c:
        c.register("_incoming", typed)
        c.execute(f'CREATE TABLE "{table}" AS SELECT * FROM _incoming')
        c.unregister("_incoming")
    date_cols = [x for x in cols if x["type"] == "date"]
    num_cols = [x for x in cols if x["type"] == "number"]
    text_cols = [x for x in cols if x["type"] in ("text", "category")]
    suggestion = {"date": date_cols[0]["column"] if date_cols else None, "value": num_cols[-1]["column"] if num_cols else None}
    config = {"table": table, "columns": cols, "suggestion": suggestion, "trend": None, "text_column": None,
              "title": re.sub(r"[_-]+", " ", rt.file_name.rsplit(".", 1)[0]).strip().capitalize()}
    dmin = dmax = None
    if date_cols:
        d = typed[date_cols[0]["column"]].dropna()
        if len(d):
            dmin, dmax = d.min().date(), d.max().date()
    db.execute("INSERT INTO datasets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        dataset_id, ws, rt.file_name, rt.sheet, "flexible", "Your own data", 0.0, fingerprint(list(df.columns)), len(df), len(df), 0, 0,
        dmin, dmax, 1.0, datetime.now(), json.dumps({}), json.dumps({"notes": ["Stored as a flexible dataset."], "issues": []}), True,
        json.dumps(config), "active"])
    # show it straight away: a monthly trend of the main number, and long text as feedback
    auto_trend = None
    if suggestion["date"] and suggestion["value"]:
        vl = next(c["label"] for c in cols if c["column"] == suggestion["value"])
        auto_trend = {"date": suggestion["date"], "value": suggestion["value"], "label": config["title"], "value_label": vl}
    long_text = [c for c in text_cols if text_stats(typed[c["column"]].dropna().astype(str)) >= 25]
    if auto_trend or long_text:
        config = configure_flexible(dataset_id, auto_trend, long_text[0]["column"] if long_text else None)["config"]
    return {"ok": True, "dataset_id": dataset_id, "label": "Your own data", "table_type": "flexible", "flexible": True,
            "config": config, "profile": prof, "text_columns": text_cols,
            "report": {"rows_in": len(df), "imported": len(df), "skipped": 0, "fixed": 0, "duplicates": 0,
                       "notes": ["We did not recognise this as a standard export, so it is saved as your own dataset."], "issues": []}}


def configure_flexible(dataset_id: str, trend: dict | None = None, text_column: str | None = None, title: str | None = None) -> dict:
    ds = db.rows("SELECT * FROM datasets WHERE id = ?", [dataset_id])
    if not ds:
        raise ReadError("Dataset not found.")
    config = json.loads(ds[0]["flex_config"])
    if title:
        config["title"] = title
    if trend:
        config["trend"] = trend
    added = 0
    if text_column:
        config["text_column"] = text_column
        table = config["table"]
        date_col = (config.get("trend") or {}).get("date") or config["suggestion"].get("date")
        src = db.q(f'SELECT row_num, "{text_column}" AS text' + (f', "{date_col}" AS date' if date_col else "") + f' FROM "{table}"')
        src = src[src["text"].notna() & (src["text"].astype(str).str.len() > 2)]
        fb = pd.DataFrame({"date": pd.to_datetime(src["date"]).dt.date if date_col else None, "kind": "message",
                           "source": config["title"], "text": src["text"], "title": None, "rating": float("nan"), "nps": float("nan"),
                           "product": None, "language": None, "customer_id": None, "heard_from": None, "consent_quote": False,
                           "row_num": src["row_num"]})
        fb = tf._enrich_feedback(fb)
        fb["_key"] = [tf.key_of(dataset_id, r) for r in fb["row_num"]]
        fb["ws"], fb["dataset_id"] = ds[0]["ws"], dataset_id
        cols = [x.strip().split()[0] for x in db.SCHEMA["feedback"].replace("\n", " ").split(",")]
        for x in cols:
            if x not in fb.columns:
                fb[x] = None
        with db.locked() as c:
            c.execute("DELETE FROM feedback WHERE dataset_id = ?", [dataset_id])
            c.register("_incoming", fb[cols])
            c.execute("INSERT INTO feedback SELECT * FROM _incoming")
            c.unregister("_incoming")
        added = len(fb)
    db.execute("UPDATE datasets SET flex_config = ? WHERE id = ?", [json.dumps(config), dataset_id])
    return {"ok": True, "config": config, "feedback_added": added}


def undo(dataset_id: str) -> dict:
    ds = db.rows("SELECT * FROM datasets WHERE id = ?", [dataset_id])
    if not ds:
        return {"ok": False, "error": "Already removed."}
    with db.locked() as c:
        for t in db.CANONICAL_TABLES:
            c.execute(f"DELETE FROM {t} WHERE dataset_id = ?", [dataset_id])
        c.execute(f'DROP TABLE IF EXISTS "flex_{dataset_id}"')
        c.execute("DELETE FROM datasets WHERE id = ?", [dataset_id])
    return {"ok": True, "file_name": ds[0]["file_name"]}


def auto_import(file_name: str, data: bytes, ws: str) -> list[dict]:
    """Stage and import using the best guess (used by demo loading and tests)."""
    st = stage(file_name, data, ws)
    out = []
    for t in st["tables"]:
        if t["kind"] != "table":
            continue
        res = confirm(st["upload_id"], t["index"], t["table_type"], t["mapping"], t["privacy"], flexible=t["flexible_suggested"], ws=ws)
        out.append({"name": t["name"], **res})
    return out
