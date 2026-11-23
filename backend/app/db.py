"""DuckDB access layer. One local file, one shared connection guarded by a lock."""
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any

import duckdb
import pandas as pd

from .config import DB_PATH

_lock = threading.RLock()
_con: duckdb.DuckDBPyConnection | None = None

# Canonical tables. Every row carries its workspace and provenance.
PROV = "ws VARCHAR, dataset_id VARCHAR, row_num INTEGER, _key VARCHAR"
SCHEMA = {
    "orders": f"""{PROV}, order_id VARCHAR, ts TIMESTAMP, date DATE, customer_id VARCHAR, subtotal DOUBLE, total DOUBLE,
        discount_code VARCHAR, discount DOUBLE, shipping DOUBLE, channel VARCHAR, is_gift BOOLEAN, city VARCHAR,
        country VARCHAR, currency VARCHAR""",
    "order_items": f"""{PROV}, order_id VARCHAR, date DATE, customer_id VARCHAR, product VARCHAR, sku VARCHAR, quantity DOUBLE,
        price DOUBLE, fabric VARCHAR, line VARCHAR, colour VARCHAR""",
    "products": f"""{PROV}, product VARCHAR, sku VARCHAR, price DOUBLE, type VARCHAR, fabric VARCHAR, line VARCHAR,
        colour VARCHAR, inventory DOUBLE""",
    "customers": f"""{PROV}, customer_id VARCHAR, city VARCHAR, country VARCHAR, language VARCHAR, orders_count DOUBLE,
        total_spent DOUBLE, accepts_marketing BOOLEAN""",
    "feedback": f"""{PROV}, date DATE, kind VARCHAR, source VARCHAR, text VARCHAR, title VARCHAR, rating DOUBLE, nps DOUBLE,
        product VARCHAR, fabric VARCHAR, line VARCHAR, language VARCHAR, customer_id VARCHAR, heard_from VARCHAR,
        consent_quote BOOLEAN, sentiment VARCHAR, sentiment_score DOUBLE, themes VARCHAR, distress BOOLEAN,
        platform VARCHAR, external_id VARCHAR, reply_status VARCHAR, reply_text VARCHAR, replied_at TIMESTAMP""",
    "social_posts": f"""{PROV}, post_id VARCHAR, platform VARCHAR, ts TIMESTAMP, date DATE, format VARCHAR, caption VARCHAR,
        pillar VARCHAR, reach DOUBLE, views DOUBLE, likes DOUBLE, comments DOUBLE, saves DOUBLE, shares DOUBLE,
        follows DOUBLE, hashtags INTEGER, caption_length INTEGER""",
    "social_comments": f"""{PROV}, platform VARCHAR, post_id VARCHAR, date DATE, text VARCHAR, author_id VARCHAR,
        language VARCHAR, sentiment VARCHAR, category VARCHAR, replied BOOLEAN, likes DOUBLE, distress BOOLEAN""",
    "web_sessions": f"""{PROV}, date DATE, source VARCHAR, medium VARCHAR, landing_page VARCHAR, device VARCHAR,
        sessions DOUBLE, users DOUBLE, conversions DOUBLE, revenue DOUBLE""",
    "email_campaigns": f"""{PROV}, date DATE, campaign VARCHAR, recipients DOUBLE, opens DOUBLE, clicks DOUBLE,
        orders DOUBLE, revenue DOUBLE""",
}
CANONICAL_TABLES = list(SCHEMA)

META = {
    "datasets": """id VARCHAR PRIMARY KEY, ws VARCHAR, file_name VARCHAR, sheet VARCHAR, table_type VARCHAR, source_label VARCHAR,
        confidence DOUBLE, fingerprint VARCHAR, rows_in INTEGER, rows_imported INTEGER, rows_skipped INTEGER,
        rows_fixed INTEGER, date_min DATE, date_max DATE, quality DOUBLE, created_at TIMESTAMP, mapping JSON,
        report JSON, flexible BOOLEAN, flex_config JSON, status VARCHAR""",
    "recipes": "fingerprint VARCHAR PRIMARY KEY, table_type VARCHAR, mapping JSON, privacy JSON, label VARCHAR, created_at TIMESTAMP",
    "goals": """id VARCHAR PRIMARY KEY, ws VARCHAR, title VARCHAR, metric VARCHAR, target DOUBLE, baseline DOUBLE,
        due DATE, created_at TIMESTAMP""",
    "decisions": """id VARCHAR PRIMARY KEY, ws VARCHAR, title VARCHAR, hypothesis VARCHAR, metric VARCHAR, baseline DOUBLE,
        baseline_start DATE, baseline_end DATE, review_date DATE, owner VARCHAR, status VARCHAR, insight_id VARCHAR,
        linked_goal VARCHAR, result_value DOUBLE, learning VARCHAR, reviewed_at TIMESTAMP, created_at TIMESTAMP,
        kind VARCHAR""",
    "settings": "key VARCHAR PRIMARY KEY, value JSON",
}


def con() -> duckdb.DuckDBPyConnection:
    global _con
    if _con is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _con = duckdb.connect(str(DB_PATH))
        init_schema(_con)
    return _con


MIGRATIONS = [("feedback", "platform VARCHAR"), ("feedback", "external_id VARCHAR"), ("feedback", "reply_status VARCHAR"),
              ("feedback", "reply_text VARCHAR"), ("feedback", "replied_at TIMESTAMP")]


def init_schema(c: duckdb.DuckDBPyConnection) -> None:
    for name, cols in {**SCHEMA, **META}.items():
        c.execute(f"CREATE TABLE IF NOT EXISTS {name} ({cols})")
    for table, col in MIGRATIONS:
        c.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col}")


@contextmanager
def locked():
    with _lock:
        yield con()


def q(sql: str, params: list | tuple | None = None) -> pd.DataFrame:
    with _lock:
        return con().execute(sql, params or []).df()


def rows(sql: str, params: list | tuple | None = None) -> list[dict[str, Any]]:
    df = q(sql, params)
    return records(df)


def one(sql: str, params: list | tuple | None = None) -> Any:
    with _lock:
        r = con().execute(sql, params or []).fetchone()
    return r[0] if r else None


def execute(sql: str, params: list | tuple | None = None) -> None:
    with _lock:
        con().execute(sql, params or [])


def records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame to JSON-safe records (dates as ISO strings, NaN as None)."""
    if df.empty:
        return []
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            s = out[col]
            midnight = s.dropna().dt.normalize().eq(s.dropna()).all()
            out[col] = pd.Series([None if pd.isna(v) else (v.date() if midnight else v.to_pydatetime()) for v in s], index=s.index, dtype=object)
    out = out.astype(object).where(pd.notna(out), None)
    return out.to_dict(orient="records")


def get_setting(key: str, default: Any = None) -> Any:
    import json

    v = one("SELECT value FROM settings WHERE key = ?", [key])
    return json.loads(v) if v is not None else default


def set_setting(key: str, value: Any) -> None:
    import json

    execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", [key, json.dumps(value)])


def reset_all() -> None:
    """Delete everything (one-click delete)."""
    with _lock:
        c = con()
        for name in list(SCHEMA) + list(META):
            c.execute(f"DROP TABLE IF EXISTS {name}")
        for (t,) in c.execute("SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'flex_%'").fetchall():
            c.execute(f'DROP TABLE IF EXISTS "{t}"')
        init_schema(c)
