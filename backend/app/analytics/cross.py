"""Cross-source analysis: does mission content bring visitors and buyers?

Always labelled as correlation, never causation, and only shown with 8+ weeks of overlap.
"""
from __future__ import annotations

import pandas as pd

from .. import db

MIN_WEEKS = 8


def weekly_frame(ws: str) -> pd.DataFrame:
    posts = db.q("""SELECT date_trunc('week', date)::DATE AS week, sum(CASE WHEN pillar = 'mission' THEN 1 ELSE 0 END) mission_posts,
        count(*) posts FROM social_posts WHERE ws = ? AND platform = 'Instagram' GROUP BY 1""", [ws])
    web = db.q("""SELECT date_trunc('week', date)::DATE AS week, sum(CASE WHEN source ILIKE '%instagram%' THEN sessions ELSE 0 END) ig_visits,
        sum(sessions) visits FROM web_sessions WHERE ws = ? GROUP BY 1""", [ws])
    orders = db.q("SELECT date_trunc('week', date)::DATE AS week, count(*) orders FROM orders WHERE ws = ? GROUP BY 1", [ws])
    frames = [f.set_index("week") for f in (posts, web, orders) if not f.empty]
    if len(frames) < 2:
        return pd.DataFrame()
    df = pd.concat(frames, axis=1).sort_index()
    df = df.iloc[1:-1]  # drop partial first and last weeks
    return df.fillna(0)


def mission_effect(ws: str) -> dict:
    df = weekly_frame(ws)
    needed = {"mission_posts", "ig_visits", "orders"}
    if df.empty or not needed.issubset(df.columns):
        return {"enough": False, "reason": "Needs Instagram posts, website visits and orders covering the same weeks."}
    df = df[(df["posts"] > 0) | (df["ig_visits"] > 0)]
    if len(df) < MIN_WEEKS:
        return {"enough": False, "reason": f"Needs at least {MIN_WEEKS} weeks of overlapping data (we have {len(df)})."}
    out = {"enough": True, "weeks": int(len(df))}
    for lag in (0, 1):
        out[f"visits_lag{lag}"] = round(float(df["mission_posts"].corr(df["ig_visits"].shift(-lag))), 2)
        out[f"orders_lag{lag}"] = round(float(df["mission_posts"].corr(df["orders"].shift(-lag))), 2)
    with_m = df[df["mission_posts"] > 0]
    without = df[df["mission_posts"] == 0]
    out["ig_visits_with"] = round(float(with_m["ig_visits"].mean()), 1) if len(with_m) else None
    out["ig_visits_without"] = round(float(without["ig_visits"].mean()), 1) if len(without) else None
    out["orders_with"] = round(float(with_m["orders"].mean()), 1) if len(with_m) else None
    out["orders_without"] = round(float(without["orders"].mean()), 1) if len(without) else None
    out["series"] = [{"week": i.isoformat() if hasattr(i, "isoformat") else str(i), "mission_posts": int(r["mission_posts"]),
                      "ig_visits": float(r["ig_visits"]), "orders": float(r["orders"])} for i, r in df.tail(52).iterrows()]
    return out
