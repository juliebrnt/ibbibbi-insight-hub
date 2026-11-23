"""Plan: goals, decisions, experiments and the learning log that closes the loop."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from .. import db
from ..analytics import metrics
from ..analytics.common import latest_date


def _id(p):
    return f"{p}_{uuid.uuid4().hex[:8]}"


def goal_progress(ws: str, g: dict) -> dict:
    end = latest_date(ws)
    cur = metrics.window_value(ws, g["metric"], end, 90 if g["metric"] in ("nps", "avg_rating", "repeat_rate") else 28)
    base, target = g["baseline"], g["target"]
    progress = None
    if cur is not None and base is not None and target is not None and target != base:
        progress = max(0.0, min(1.0, (cur - base) / (target - base)))
    return {**g, "current": cur, "progress": progress, "current_display": metrics.fmt(g["metric"], cur),
            "target_display": metrics.fmt(g["metric"], target), "baseline_display": metrics.fmt(g["metric"], base),
            "label": metrics.METRICS.get(g["metric"], {}).get("label", g["metric"])}


def list_goals(ws: str) -> list[dict]:
    return [goal_progress(ws, g) for g in db.rows("SELECT * FROM goals WHERE ws = ? ORDER BY created_at", [ws])]


def add_goal(ws: str, title: str, metric: str, target: float, due: str | None) -> dict:
    if db.one("SELECT count(*) FROM goals WHERE ws = ?", [ws]) >= 3:
        raise ValueError("You can focus on up to three goals. Remove one first.")
    end = latest_date(ws)
    base = metrics.window_value(ws, metric, end, 90 if metric in ("nps", "avg_rating", "repeat_rate") else 28)
    gid = _id("g")
    db.execute("INSERT INTO goals VALUES (?,?,?,?,?,?,?,?)", [gid, ws, title, metric, target, base, due, datetime.now()])
    return goal_progress(ws, db.rows("SELECT * FROM goals WHERE id = ?", [gid])[0])


def update_goal(ws: str, gid: str, title: str | None, target: float | None, due: str | None) -> dict:
    g = db.rows("SELECT * FROM goals WHERE id = ? AND ws = ?", [gid, ws])
    if not g:
        raise ValueError("Goal not found")
    g = g[0]
    db.execute("UPDATE goals SET title = ?, target = ?, due = ? WHERE id = ?",
               [title or g["title"], target if target is not None else g["target"], due or g["due"], gid])
    return goal_progress(ws, db.rows("SELECT * FROM goals WHERE id = ?", [gid])[0])


def add_decision(ws: str, title: str, hypothesis: str, metric: str | None, review_date: str | None, owner: str | None,
                 insight_id: str | None = None, linked_goal: str | None = None, kind: str = "decision",
                 created: date | None = None) -> dict:
    end = created or latest_date(ws)
    baseline = None
    if metric:
        try:
            baseline = metrics.window_value(ws, metric, end, 28)
        except KeyError:
            metric = None
    rid = review_date or (end + timedelta(days=28)).isoformat()
    did = _id("d")
    db.execute("INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        did, ws, title, hypothesis, metric, baseline, end - timedelta(days=27), end, rid, owner or "Founders", "active", insight_id,
        linked_goal, None, None, None, datetime.combine(end, datetime.min.time()), kind])
    return decorate(ws, db.rows("SELECT * FROM decisions WHERE id = ?", [did])[0])


def decorate(ws: str, d: dict) -> dict:
    today = latest_date(ws)
    review = date.fromisoformat(str(d["review_date"])[:10]) if d.get("review_date") else None
    d["due"] = bool(review and review <= today and d["status"] == "active")
    d["metric_label"] = metrics.METRICS.get(d["metric"], {}).get("label", d["metric"]) if d.get("metric") else None
    d["baseline_display"] = metrics.fmt(d["metric"], d["baseline"]) if d.get("metric") else None
    if d.get("metric") and d["status"] == "active":
        start = date.fromisoformat(str(d["baseline_end"])[:10]) + timedelta(days=1)
        stop = min(today, review) if review else today
        if (stop - start).days >= 6:
            cur = metrics.value(ws, d["metric"], max(start, stop - timedelta(days=27)), stop)
            d["current"] = cur
            d["current_display"] = metrics.fmt(d["metric"], cur)
            d["change"] = round((cur - d["baseline"]) / abs(d["baseline"]) * 100, 1) if cur is not None and d["baseline"] else None
    if d.get("result_value") is not None and d.get("baseline"):
        d["result_display"] = metrics.fmt(d["metric"], d["result_value"])
        d["change"] = round((d["result_value"] - d["baseline"]) / abs(d["baseline"]) * 100, 1)
    return d


def list_decisions(ws: str) -> list[dict]:
    return [decorate(ws, d) for d in db.rows("SELECT * FROM decisions WHERE ws = ? ORDER BY created_at DESC", [ws])]


def review(ws: str, did: str, learning: str, outcome: str = "kept") -> dict:
    d = db.rows("SELECT * FROM decisions WHERE id = ? AND ws = ?", [did, ws])
    if not d:
        raise ValueError("Decision not found")
    d = d[0]
    result = None
    if d["metric"]:
        review_d = date.fromisoformat(str(d["review_date"])[:10])
        end = min(latest_date(ws), review_d)
        result = metrics.value(ws, d["metric"], end - timedelta(days=27), end)
    db.execute("UPDATE decisions SET result_value = ?, learning = ?, status = ?, reviewed_at = ? WHERE id = ?",
               [result, learning, outcome if outcome in ("kept", "dropped", "adjusted") else "kept", datetime.now(), did])
    return decorate(ws, db.rows("SELECT * FROM decisions WHERE id = ?", [did])[0])


def delete(table: str, ws: str, rid: str) -> None:
    assert table in ("goals", "decisions")
    db.execute(f"DELETE FROM {table} WHERE id = ? AND ws = ?", [rid, ws])


def seed_demo_plan(ws: str = "demo") -> None:
    """A few realistic plan items so the loop can be shown end to end."""
    if db.one("SELECT count(*) FROM decisions WHERE ws = ?", [ws]):
        return
    end = latest_date(ws)
    add_goal(ws, "Raise Instagram saves per post by 20%", "ig_saves", round((metrics.window_value(ws, "ig_saves", end, 90) or 40) * 1.2), f"{end.year + 1}-03-31")
    add_goal(ws, "Keep NPS above 50", "nps", 55, f"{end.year + 1}-06-30")
    add_goal(ws, "Lift repeat purchase rate", "repeat_rate", 0.45, f"{end.year + 1}-06-30")
    # a past decision whose review is due, so the learning loop can be demonstrated
    add_decision(ws, "Post three times a week, every week", "A steady rhythm will grow reach and saves.", "ig_saves",
                 (end - timedelta(days=200)).isoformat(), "Founders", kind="experiment", created=end - timedelta(days=290))
    add_decision(ws, "Add a care-first email 30 days after purchase", "A useful follow-up (care tips, styling) brings people back.",
                 "repeat_rate", (end - timedelta(days=3)).isoformat(), "Founders", created=end - timedelta(days=60))
    first = db.rows("SELECT id FROM decisions WHERE ws = ? AND kind = 'experiment'", [ws])[0]["id"]
    review(ws, first, "Regular posting worked: reach and saves went up. We batch-create posts on Sunday evenings now.", "kept")
