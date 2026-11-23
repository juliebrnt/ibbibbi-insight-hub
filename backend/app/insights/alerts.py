"""Alerts: meaningful changes only, each with its size, comparison period, calculation, source and next step.

Both periods are always the same number of full days, ending on the latest day with data, so a
complete period is never compared with an incomplete one. Each check has a minimum sample and a
minimum change, so small wobbles do not raise alerts.
"""
from __future__ import annotations

from datetime import date

from .. import db
from ..analytics import metrics
from ..analytics.common import Period

# metric, minimum relative change (%), or absolute points for shares, minimum sample, source, why, next step
CHECKS = [
    ("revenue", 15, None, "orders", "Shopify orders", "Revenue is the clearest signal of how the business is doing.",
     {"down": "Open Sales to see which products and channels fell, and check whether the same period last year was also quieter.",
      "up": "Find out what drove it (a campaign, a season, a post) and note it in the Plan so you can repeat it."}),
    ("orders", 15, None, "orders", "Shopify orders", "Fewer or more orders usually come before changes in revenue.",
     {"down": "Check website visits and conversion: is it fewer visitors or fewer of them buying?",
      "up": "Make sure stock and delivery times keep up."}),
    ("aov", 12, None, "orders", "Shopify orders", "Average order value shows whether people buy more per visit.",
     {"down": "Check discount code use and whether bundles or gift sets sold less.", "up": "See which products are being bought together."}),
    ("negative_share", None, 8, "feedback", "Reviews, surveys and messages", "A rise in complaints often comes before a fall in repeat purchases.",
     {"up": "Read the newest negative feedback on the Feedback page and reply to it; look for one shared cause.",
      "down": "Note what changed so the improvement holds."}),
    ("avg_rating", 6, None, "ratings", "Product reviews", "Ratings are visible to every new visitor.",
     {"down": "Read the lowest reviews from this period and reply to each one.", "up": "Ask happy customers for a review while it lasts."}),
    ("ig_er", 15, None, "posts", "Instagram posts", "Engagement decides how many people Instagram shows your posts to.",
     {"down": "Compare the formats and topics you posted this period with the last one on the Social page.",
      "up": "Repeat the format and topic of your best post this period."}),
    ("conversion", 15, None, "sessions", "Google Analytics", "Conversion shows whether the shop turns visitors into buyers.",
     {"down": "Test checkout on a phone and check for out-of-stock bestsellers.", "up": "Check which landing page improved and send more visitors there."}),
    ("sessions", 20, None, "sessions", "Google Analytics", "Website visits are the top of your sales funnel.",
     {"down": "Check which source fell (Instagram, Google, email) on the Sales page, Website tab.",
      "up": "See which source grew and whether those visitors buy."}),
]
MIN_SAMPLE = {"orders": 30, "feedback": 20, "ratings": 15, "posts": 4, "sessions": 1000}


def _sample(ws: str, kind: str, a: date, b: date) -> int:
    sql = {"orders": "SELECT count(*) FROM orders WHERE ws = ? AND date BETWEEN ? AND ?",
           "feedback": "SELECT count(*) FROM feedback WHERE ws = ? AND date BETWEEN ? AND ?",
           "ratings": "SELECT count(*) FROM feedback WHERE ws = ? AND rating IS NOT NULL AND date BETWEEN ? AND ?",
           "posts": "SELECT count(*) FROM social_posts WHERE ws = ? AND platform = 'Instagram' AND date BETWEEN ? AND ?",
           "sessions": "SELECT coalesce(sum(sessions), 0) FROM web_sessions WHERE ws = ? AND date BETWEEN ? AND ?"}[kind]
    return int(db.one(sql, [ws, a, b]) or 0)


def _d(x: date) -> str:
    return f"{x:%-d %b %Y}"


def build(ws: str, p: Period) -> dict:
    period_text = f"{_d(p.start)} to {_d(p.end)} compared with {_d(p.prev_start)} to {_d(p.prev_end)} (both {p.days} full days)"
    alerts, checked = [], []
    for key, min_pct, min_pts, sample_kind, source, why, steps in CHECKS:
        n_cur, n_prev = _sample(ws, sample_kind, p.start, p.end), _sample(ws, sample_kind, p.prev_start, p.prev_end)
        if min(n_cur, n_prev) < MIN_SAMPLE[sample_kind]:
            continue
        cur, prev = metrics.value(ws, key, p.start, p.end), metrics.value(ws, key, p.prev_start, p.prev_end)
        if cur is None or prev is None:
            continue
        m = metrics.METRICS[key]
        checked.append(m["label"])
        if min_pts is not None:
            change = (cur - prev) * 100
            if abs(change) < min_pts:
                continue
            size = f"{abs(change):.0f} percentage points"
            calc = f"{m['label']} = share of all pieces of feedback marked negative. {metrics.fmt(key, prev)} before, {metrics.fmt(key, cur)} now."
        else:
            if not prev:
                continue
            change = (cur - prev) / abs(prev) * 100
            if abs(change) < min_pct:
                continue
            size = f"{abs(change):.0f}%"
            calc = f"({metrics.fmt(key, cur)} minus {metrics.fmt(key, prev)}) divided by {metrics.fmt(key, prev)}"
        up = change > 0
        good = up == m["higher_is_better"]
        ly = metrics.value(ws, key, p.ly_start, p.ly_end) if _sample(ws, sample_kind, p.ly_start, p.ly_end) >= MIN_SAMPLE[sample_kind] else None
        context = []
        if ly:
            ly_change = (cur - ly) / abs(ly) * 100 if min_pts is None else (cur - ly) * 100
            context.append(f"Same period last year: {metrics.fmt(key, ly)} ({'+' if ly_change >= 0 else ''}{ly_change:.0f}{'%' if min_pts is None else ' points'}).")
        from .. import profile as prof
        months = {p.prev_start.month, p.prev_end.month}
        peaks = months & prof.peak_months(ws)
        if not up and peaks and sample_kind in ("orders", "sessions"):
            names = ", ".join(prof.key_date(ws, m) for m in sorted(peaks))
            context.append(f"The comparison period includes a seasonal peak ({names}), so part of this fall is expected.")
        alerts.append({
            "id": f"alert_{key}", "metric": key, "label": m["label"], "direction": "up" if up else "down",
            "tone": "good" if good else "warning",
            "title": f"{m['label']} {'rose' if up else 'fell'} {size}",
            "what": f"{m['label']} went from {metrics.fmt(key, prev)} to {metrics.fmt(key, cur)}.",
            "size": size, "change": round(change, 1), "current": metrics.fmt(key, cur), "previous": metrics.fmt(key, prev),
            "period": period_text, "calculation": calc, "source": source, "sample": f"{n_cur:,} now, {n_prev:,} before ({sample_kind})",
            "why": why, "next_step": steps["up" if up else "down"], "context": " ".join(context),
            "seasonal": bool(context and "seasonal" in context[-1]),
        })
    # goals that are falling behind schedule
    from . import plan

    for g in plan.list_goals(ws):
        if g.get("progress") is None or not g.get("due"):
            continue
        due = date.fromisoformat(str(g["due"])[:10])
        created = g["created_at"].date() if hasattr(g["created_at"], "date") else date.fromisoformat(str(g["created_at"])[:10])
        span = max((due - created).days, 1)
        elapsed = min(1.0, max(0.0, (p.end - created).days / span))
        if elapsed >= 0.25 and g["progress"] < elapsed - 0.25:
            alerts.append({
                "id": f"alert_goal_{g['id']}", "metric": g["metric"], "label": g["label"], "direction": "down", "tone": "warning",
                "title": f"Goal behind schedule: {g['title']}", "what": f"{g['progress'] * 100:.0f}% of the way, with {elapsed * 100:.0f}% of the time used.",
                "size": f"{(elapsed - g['progress']) * 100:.0f} points behind", "change": None, "current": g["current_display"],
                "previous": g["baseline_display"], "period": f"Goal set {_d(created)}, due {_d(due)}",
                "calculation": f"Progress = (now minus starting point) divided by (target minus starting point): {g['baseline_display']} to {g['current_display']}, target {g['target_display']}.",
                "source": "Plan", "sample": "", "why": "Spotting this early leaves time to change course.", "context": "", "seasonal": False,
                "next_step": "Open Plan, check which recommendations support this goal and add one as a decision."})
    order = {"warning": 0, "good": 1}
    alerts.sort(key=lambda a: (order[a["tone"]], a.get("seasonal", False), -(abs(a["change"]) if a["change"] is not None else 50)))
    return {"alerts": alerts, "period": period_text, "checked": checked,
            "quiet": not alerts and bool(checked)}
