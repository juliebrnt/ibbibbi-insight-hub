"""Social content analytics: formats, pillars, timing, consistency, mission alignment, comments."""
from __future__ import annotations

from datetime import timedelta
from statistics import mean, pstdev

from .. import db
from .common import Period, div, has, pct_change, subtitle
from .text import PILLAR_LABELS

MIN_POSTS = 4
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
ER = "(coalesce(likes,0)+coalesce(comments,0)+coalesce(saves,0)+coalesce(shares,0))/nullif(reach,0)"


def consistency(ws: str, a, b, platform: str = "Instagram") -> dict:
    """0-100 score from posts per week, regularity and longest gap."""
    posts = db.rows("SELECT date FROM social_posts WHERE ws = ? AND platform = ? AND date BETWEEN ? AND ? ORDER BY date",
                    [ws, platform, a, b])
    weeks = max(1, ((b - a).days + 1) // 7)
    if not posts:
        return {"score": 0, "per_week": 0, "longest_gap": (b - a).days, "regularity": 0, "posts": 0, "avg_gap": None, "weeks_active": 0, "weeks": weeks}
    dates = [r["date"] for r in posts]
    counts = [0] * weeks
    for d in dates:
        i = min(weeks - 1, (d - a).days // 7)
        counts[i] += 1
    gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)] + [(dates[0] - a).days, (b - dates[-1]).days]
    longest = max(gaps)
    per_week = len(dates) / weeks
    cv = pstdev(counts) / mean(counts) if mean(counts) else 3
    regularity = max(0.0, 1 - cv / 1.5)
    cadence = min(1.0, per_week / 3)
    gap_score = max(0.0, 1 - max(0, longest - 4) / 24)
    score = round(100 * (0.4 * cadence + 0.35 * regularity + 0.25 * gap_score))
    between = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
    avg_gap = round(sum(between) / len(between), 1) if between else None
    weeks_active = round(sum(1 for c in counts if c) / weeks, 3)
    return {"score": score, "per_week": round(per_week, 1), "longest_gap": longest, "regularity": round(regularity, 2), "posts": len(dates),
            "avg_gap": avg_gap, "weeks_active": weeks_active, "weeks": weeks}


def overview(ws: str, p: Period) -> dict:
    if not has("social_posts", ws):
        return {"empty": True}
    platforms = [r["platform"] for r in db.rows("SELECT platform, count(*) n FROM social_posts WHERE ws = ? GROUP BY 1 ORDER BY n DESC", [ws])]
    plat = "Instagram" if "Instagram" in platforms else platforms[0]
    w = "ws = ? AND platform = ? AND date BETWEEN ? AND ?"
    args = [ws, plat, p.start, p.end]
    src = f"{plat} posts"

    def agg(a, b):
        return db.rows(f"""SELECT count(*) posts, avg({ER}) er, avg(saves) saves, avg(shares) shares, avg(reach) reach,
            avg(CASE WHEN pillar = 'mission' THEN 1 ELSE 0 END) mission_share FROM social_posts WHERE {w}""", [ws, plat, a, b])[0]
    cur, prev = agg(p.start, p.end), agg(p.prev_start, p.prev_end)
    cons, cons_prev = consistency(ws, p.start, p.end, plat), consistency(ws, p.prev_start, p.prev_end, plat)

    # Use at least 6 months for content comparisons so samples are meaningful
    wide_start = min(p.start, p.end - timedelta(days=182))
    wargs = [ws, plat, wide_start, p.end]
    by_format = db.rows(f"""SELECT format, count(*) posts, avg(reach) reach, avg({ER}) er, avg(saves) saves, avg(shares) shares
        FROM social_posts WHERE {w} GROUP BY 1 ORDER BY saves DESC""", wargs)
    by_pillar = db.rows(f"""SELECT pillar, count(*) posts, avg(reach) reach, avg({ER}) er, avg(saves) saves, avg(shares) shares
        FROM social_posts WHERE {w} GROUP BY 1 ORDER BY saves DESC""", wargs)
    for r in by_pillar:
        r["label"] = PILLAR_LABELS.get(r["pillar"], r["pillar"])
    timing = db.rows(f"""SELECT isodow(date) dow, CAST(hour(ts) / 3 AS INT) * 3 hour_block, count(*) posts, avg({ER}) er
        FROM social_posts WHERE {w} GROUP BY 1, 2""", wargs)
    by_day = db.rows(f"""SELECT isodow(date) dow, count(*) posts, avg({ER}) er, avg(reach) reach FROM social_posts WHERE {w} GROUP BY 1 ORDER BY 1""", wargs)
    for r in by_day:
        r["day"] = DAYS[r["dow"] - 1]
    caption = db.rows(f"""SELECT CASE WHEN caption_length < 80 THEN 'Short (under 80)' WHEN caption_length < 160 THEN 'Medium (80 to 160)'
        ELSE 'Long (160+)' END bucket, count(*) posts, avg({ER}) er, avg(saves) saves FROM social_posts WHERE {w} GROUP BY 1""", wargs)
    hashtags = db.rows(f"""SELECT CASE WHEN hashtags = 0 THEN 'None' WHEN hashtags <= 2 THEN '1 to 2' ELSE '3 or more' END bucket,
        count(*) posts, avg({ER}) er, avg(reach) reach FROM social_posts WHERE {w} GROUP BY 1""", wargs)

    year_start = p.end - timedelta(days=364)
    calendar = db.rows("SELECT date, count(*) n FROM social_posts WHERE ws = ? AND platform = ? AND date BETWEEN ? AND ? GROUP BY 1",
                       [ws, plat, year_start, p.end])
    weekly = db.rows("""SELECT date_trunc('week', date)::DATE AS week, count(*) posts, avg(reach) reach FROM social_posts
        WHERE ws = ? AND platform = ? GROUP BY 1 ORDER BY 1""", [ws, plat])
    top_posts = db.rows(f"""SELECT post_id, date, format, pillar, caption, reach, saves, shares, {ER} er FROM social_posts WHERE {w}
        ORDER BY saves DESC LIMIT 5""", args)

    # Titles that state the finding
    fmt = {r["format"]: r for r in by_format}
    format_title = "How each format performs"
    if fmt.get("Reel") and fmt.get("Static image") and fmt["Reel"]["posts"] >= MIN_POSTS and fmt["Static image"]["posts"] >= MIN_POSTS and fmt["Static image"]["saves"]:
        ratio = fmt["Reel"]["saves"] / fmt["Static image"]["saves"]
        format_title = (f"Reels earn {ratio:.1f}x the saves of static posts" if ratio >= 1.2 else
                        "Reels and static posts earn similar saves")
    pil = {r["pillar"]: r for r in by_pillar}
    pillar_title = "Which topics people save and share"
    if pil.get("mission") and len(by_pillar) > 1 and pil["mission"]["posts"] >= MIN_POSTS:
        others = [r for r in by_pillar if r["pillar"] != "mission"]
        o_saves = sum(r["saves"] * r["posts"] for r in others) / max(1, sum(r["posts"] for r in others))
        if pil["mission"]["saves"] and o_saves:
            ratio = pil["mission"]["saves"] / o_saves
            pillar_title = (f"Mission and community posts earn {ratio:.1f}x the saves of other posts" if ratio >= 1.2 else
                            "Mission posts perform about the same as other content")
    best_day = max(by_day, key=lambda r: r["er"] or 0) if by_day else None
    timing_title = f"{best_day['day']} posts get the most engagement" if best_day and best_day["posts"] >= 3 else "When to post"
    cons_title = (f"{cons['per_week']} posts a week, a post in {cons['weeks_active'] * 100:.0f}% of weeks, longest gap {cons['longest_gap']} days")

    # before / after consistency change (first regular stretch)
    change = before_after(ws, plat)
    comments = comment_summary(ws, p)
    tiktok = None
    if "TikTok" in platforms:
        tiktok = db.rows("""SELECT count(*) posts, avg(views) AS views, avg(likes) likes, avg(shares) shares, min(date) AS first_d, max(date) AS last_d
            FROM social_posts WHERE ws = ? AND platform = 'TikTok'""", [ws])[0]

    return {
        "platform": plat, "platforms": platforms,
        "kpis": {
            "posts": {"value": cur["posts"], "prev": prev["posts"], "change": pct_change(cur["posts"], prev["posts"])},
            "er": {"value": cur["er"], "prev": prev["er"]},
            "saves": {"value": cur["saves"], "prev": prev["saves"], "change": pct_change(cur["saves"], prev["saves"])},
            "consistency": {"value": cons["score"], "prev": cons_prev["score"]},
            "per_week": {"value": cons["per_week"], "prev": cons_prev["per_week"]},
            "avg_gap": {"value": cons["avg_gap"], "prev": cons_prev["avg_gap"]},
            "weeks_active": {"value": cons["weeks_active"], "prev": cons_prev["weeks_active"]},
            "mission_share": {"value": cur["mission_share"], "prev": prev["mission_share"]},
        },
        "formats": {"title": format_title, "subtitle": f"Last 6 months or more · {src}", "rows": by_format},
        "pillars": {"title": pillar_title, "subtitle": f"Last 6 months or more · {src}", "rows": by_pillar},
        "timing": {"title": timing_title, "subtitle": f"Average engagement rate · {src}", "rows": timing, "by_day": by_day},
        "caption": {"title": "Caption length and engagement", "subtitle": f"Last 6 months or more · {src}", "rows": caption},
        "hashtags": {"title": "Hashtags and reach", "subtitle": f"Last 6 months or more · {src}", "rows": hashtags},
        "consistency": {"title": cons_title, "subtitle": subtitle(p, src), **cons, "calendar": calendar,
                        "calendar_range": [year_start.isoformat(), p.end.isoformat()], "weekly": weekly, "change": change},
        "mission": {"share": cur["mission_share"], "title": f"{(cur['mission_share'] or 0) * 100:.0f}% of posts in this period are mission-led"},
        "top_posts": top_posts, "comments": comments, "tiktok": tiktok,
    }


def before_after(ws: str, plat: str) -> dict | None:
    weekly = db.rows("""WITH w AS (SELECT date_trunc('week', date)::DATE AS week, count(*) n, avg(reach) reach FROM social_posts
        WHERE ws = ? AND platform = ? GROUP BY 1) SELECT * FROM w ORDER BY week""", [ws, plat])
    if len(weekly) < 16:
        return None
    first = weekly[0]["week"]
    last = weekly[-1]["week"]
    nweeks = (last - first).days // 7 + 1
    counts = {r["week"]: r["n"] for r in weekly}
    series = [counts.get(first + timedelta(days=7 * i), 0) for i in range(nweeks)]
    # find the first week from which 8 consecutive weeks all have posts
    for i in range(0, nweeks - 8):
        if all(series[i:i + 8]) and i >= 8:
            switch = first + timedelta(days=7 * i)
            before = db.rows("""SELECT count(*) posts, avg(reach) reach, avg(saves) saves FROM social_posts WHERE ws = ? AND platform = ?
                AND date < ?""", [ws, plat, switch])[0]
            after = db.rows("""SELECT count(*) posts, avg(reach) reach, avg(saves) saves FROM social_posts WHERE ws = ? AND platform = ?
                AND date >= ?""", [ws, plat, switch])[0]
            wb, wa = i, nweeks - i
            return {"switch_week": switch.isoformat(), "before_per_week": round(before["posts"] / max(wb, 1), 1),
                    "after_per_week": round(after["posts"] / max(wa, 1), 1), "before_reach": before["reach"], "after_reach": after["reach"],
                    "before_saves": before["saves"], "after_saves": after["saves"], "weeks_before": wb, "weeks_after": wa}
    return None


CAT_LABELS = {"partnership": "Partnership enquiry", "request": "Product request", "sizing": "Sizing question", "question": "Question",
              "praise": "Praise", "sensitive": "Needs a personal reply", "other": "Other"}


def comment_summary(ws: str, p: Period) -> dict:
    if not has("social_comments", ws):
        return {"empty": True}
    a = p.end - timedelta(days=max(p.days, 90) - 1)
    cats = db.rows("""SELECT category, count(*) n, avg(CASE WHEN replied THEN 1 ELSE 0 END) replied_share FROM social_comments
        WHERE ws = ? AND date BETWEEN ? AND ? GROUP BY 1 ORDER BY n DESC""", [ws, a, p.end])
    for r in cats:
        r["label"] = CAT_LABELS.get(r["category"], r["category"])
    inbox = db.rows("""SELECT _key id, date, platform, category, text, replied, language FROM social_comments
        WHERE ws = ? AND category IN ('partnership', 'request', 'sizing', 'question', 'sensitive') AND NOT coalesce(replied, false)
        ORDER BY CASE category WHEN 'sensitive' THEN 0 WHEN 'partnership' THEN 1 WHEN 'sizing' THEN 2 WHEN 'request' THEN 3 ELSE 4 END,
        date DESC LIMIT 40""", [ws])
    for r in inbox:
        r["label"] = CAT_LABELS.get(r["category"], r["category"])
    sent = db.rows("""SELECT sentiment, count(*) n FROM social_comments WHERE ws = ? AND date BETWEEN ? AND ? GROUP BY 1""", [ws, a, p.end])
    unanswered = db.one("""SELECT count(*) FROM social_comments WHERE ws = ? AND category IN ('partnership','request','sizing','question')
        AND NOT coalesce(replied, false)""", [ws])
    total = sum(r["n"] for r in cats) or 1
    return {"categories": cats, "inbox": inbox, "sentiment": sent, "unanswered": unanswered,
            "title": f"{unanswered} questions and requests in comments are still waiting for a reply" if unanswered else "Comments are all answered",
            "subtitle": f"Last {max(p.days, 90)} days · Instagram comments ({total} comments)"}


def weekly_series(ws: str) -> list[dict]:
    return db.rows("""SELECT date_trunc('week', date)::DATE AS week, count(*) posts,
        sum(CASE WHEN pillar = 'mission' THEN 1 ELSE 0 END) mission_posts, sum(saves) saves FROM social_posts WHERE ws = ? GROUP BY 1 ORDER BY 1""",
                   [ws])


def er_value(ws, a, b):
    return db.one(f"SELECT avg({ER}) FROM social_posts WHERE ws = ? AND date BETWEEN ? AND ?", [ws, a, b])


__all__ = ["overview", "consistency", "weekly_series", "div"]
