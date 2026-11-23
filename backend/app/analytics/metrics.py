"""Named metrics used by goals, decisions, experiments and cross-source analysis."""
from __future__ import annotations

import json
from datetime import date, timedelta

from .. import db
from .social import ER, consistency

METRICS = {
    "revenue": {"label": "Revenue", "unit": "eur", "higher_is_better": True},
    "orders": {"label": "Orders", "unit": "count", "higher_is_better": True},
    "aov": {"label": "Average order value", "unit": "eur", "higher_is_better": True},
    "repeat_rate": {"label": "Repeat purchase rate", "unit": "pct", "higher_is_better": True},
    "avg_rating": {"label": "Average review rating", "unit": "stars", "higher_is_better": True},
    "nps": {"label": "NPS", "unit": "score", "higher_is_better": True},
    "positive_share": {"label": "Share of positive feedback", "unit": "pct", "higher_is_better": True},
    "ig_saves": {"label": "Instagram saves per post", "unit": "count", "higher_is_better": True},
    "ig_er": {"label": "Instagram engagement rate", "unit": "pct", "higher_is_better": True},
    "posts_per_week": {"label": "Posts per week", "unit": "count", "higher_is_better": True},
    "consistency": {"label": "Weeks with at least one post", "unit": "pct", "higher_is_better": True},
    "negative_share": {"label": "Share of negative feedback", "unit": "pct", "higher_is_better": False},
    "sessions": {"label": "Website visits", "unit": "count", "higher_is_better": True},
    "conversion": {"label": "Website conversion rate", "unit": "pct", "higher_is_better": True},
    "comments_answered": {"label": "Comment questions answered", "unit": "pct", "higher_is_better": True},
}


def value(ws: str, metric: str, a: date, b: date) -> float | None:
    if metric == "revenue":
        return db.one("SELECT sum(total) FROM orders WHERE ws = ? AND date BETWEEN ? AND ?", [ws, a, b])
    if metric == "orders":
        return db.one("SELECT count(*) FROM orders WHERE ws = ? AND date BETWEEN ? AND ?", [ws, a, b]) or None
    if metric == "aov":
        return db.one("SELECT avg(total) FROM orders WHERE ws = ? AND date BETWEEN ? AND ?", [ws, a, b])
    if metric == "repeat_rate":
        # share of customers active in the window who have ordered before or ordered again in it
        return db.one("""WITH f AS (SELECT customer_id, min(date) AS first_d, count(*) n FROM orders WHERE ws = ? AND date <= ? GROUP BY 1)
            SELECT avg(CASE WHEN f.n >= 2 THEN 1 ELSE 0 END) FROM f WHERE f.customer_id IN
            (SELECT customer_id FROM orders WHERE ws = ? AND date BETWEEN ? AND ?)""", [ws, b, ws, a, b])
    if metric == "avg_rating":
        return db.one("SELECT avg(rating) FROM feedback WHERE ws = ? AND rating IS NOT NULL AND date BETWEEN ? AND ?", [ws, a, b])
    if metric == "nps":
        r = db.rows("""SELECT count(*) n, avg(CASE WHEN nps >= 9 THEN 1 ELSE 0 END) - avg(CASE WHEN nps <= 6 THEN 1 ELSE 0 END) s
            FROM feedback WHERE ws = ? AND nps IS NOT NULL AND date BETWEEN ? AND ?""", [ws, a, b])[0]
        return round(r["s"] * 100) if r["n"] >= 10 else None
    if metric == "positive_share":
        return db.one("SELECT avg(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) FROM feedback WHERE ws = ? AND date BETWEEN ? AND ?",
                      [ws, a, b])
    if metric == "ig_saves":
        return db.one("SELECT avg(saves) FROM social_posts WHERE ws = ? AND platform = 'Instagram' AND date BETWEEN ? AND ?", [ws, a, b])
    if metric == "ig_er":
        return db.one(f"SELECT avg({ER}) FROM social_posts WHERE ws = ? AND platform = 'Instagram' AND date BETWEEN ? AND ?", [ws, a, b])
    if metric == "posts_per_week":
        n = db.one("SELECT count(*) FROM social_posts WHERE ws = ? AND platform = 'Instagram' AND date BETWEEN ? AND ?", [ws, a, b])
        return round(n / max(1, ((b - a).days + 1) / 7), 2)
    if metric == "consistency":
        return consistency(ws, a, b)["weeks_active"]
    if metric == "negative_share":
        return db.one("SELECT avg(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) FROM feedback WHERE ws = ? AND date BETWEEN ? AND ?",
                      [ws, a, b])
    if metric == "sessions":
        return db.one("SELECT sum(sessions) FROM web_sessions WHERE ws = ? AND date BETWEEN ? AND ?", [ws, a, b])
    if metric == "conversion":
        return db.one("SELECT sum(conversions)/nullif(sum(sessions),0) FROM web_sessions WHERE ws = ? AND date BETWEEN ? AND ?", [ws, a, b])
    if metric == "comments_answered":
        return db.one("""SELECT avg(CASE WHEN replied THEN 1 ELSE 0 END) FROM social_comments WHERE ws = ? AND date BETWEEN ? AND ?
            AND category IN ('partnership','request','sizing','question')""", [ws, a, b])
    if metric.startswith("flex:"):
        ds_id = metric.split(":", 1)[1]
        cfg = db.one("SELECT flex_config FROM datasets WHERE id = ?", [ds_id])
        if not cfg:
            return None
        cfg = json.loads(cfg)
        t = cfg.get("trend")
        if not t:
            return None
        return db.one(f'SELECT sum("{t["value"]}") FROM "{cfg["table"]}" WHERE CAST("{t["date"]}" AS DATE) BETWEEN ? AND ?', [a, b])
    raise KeyError(metric)


def window_value(ws: str, metric: str, end: date, days: int = 28) -> float | None:
    return value(ws, metric, end - timedelta(days=days - 1), end)


def fmt(metric: str, v) -> str:
    if v is None:
        return "n/a"
    unit = METRICS.get(metric, {}).get("unit", "count")
    if unit == "eur":
        return f"€{v:,.0f}"
    if unit == "pct":
        return f"{v * 100:.1f}%"
    if unit == "stars":
        return f"{v:.2f}"
    if unit == "score":
        return f"{v:.0f}"
    return f"{v:,.1f}" if v % 1 else f"{v:,.0f}"
