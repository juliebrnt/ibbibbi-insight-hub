"""'What to add': the exact files that make the hub work, whether each is there, up to date, and what to download next."""
from __future__ import annotations

from datetime import date, timedelta

from .. import db

STALE_DAYS = 35

# key, name, what it shows, table, platform filter, guide key, essential
ITEMS = [
    ("orders", "Shopify orders", "Home and Sales: what sells, average order, repeat customers", "orders", None, "shopify", True),
    ("ig_posts", "Instagram posts", "Social: which posts, formats and topics work", "social_posts", "Instagram", "instagram", True),
    ("ig_daily", "Instagram account figures", "Social: reach, profile visits, new followers and link clicks day by day",
     "social_daily", "Instagram", "instagram_daily", True),
    ("reviews", "Judge.me reviews", "Feedback: what customers love and complain about", "feedback_review", None, "judgeme", True),
    ("products", "Shopify products", "Sales: sales by product type, fabric and colour", "products", None, "shopify_products", False),
    ("survey", "Customer survey", "Feedback: how likely people are to recommend you, and why", "feedback_survey", None, "forms", False),
]
FIRST_TIME = {
    "orders": "Download the last 12 months or more and upload it.",
    "ig_posts": "Download as far back as Meta allows and upload it.",
    "ig_daily": "Download as far back as Meta allows and upload all six files together.",
    "reviews": "Download all your reviews and upload them.",
    "products": "Download all products and upload the file.",
    "survey": "Download all the answers and upload them, or use the built-in form in Collect.",
}
DAILY = [("views", "Visualizaciones (Views)"), ("reach", "Alcance (Reach)"), ("interactions", "Interacciones (Interactions)"),
         ("profile_visits", "Visitas (Profile visits)"), ("follows", "Seguidores (Follows)"), ("link_clicks", "Clics en el enlace (Link clicks)")]


def _range(table: str, ws: str, platform: str | None) -> tuple[date | None, date | None]:
    if table.startswith("feedback_"):
        r = db.rows("SELECT min(date) a, max(date) b, count(*) n FROM feedback WHERE ws = ? AND kind = ?", [ws, table.split("_", 1)[1]])[0]
    elif table == "products":
        n = db.one("SELECT count(*) FROM products WHERE ws = ?", [ws])
        return (date.today(), date.today()) if n else (None, None)
    else:
        sql = f"SELECT min(date) a, max(date) b, count(*) n FROM {table} WHERE ws = ?" + (" AND platform = ?" if platform else "")
        r = db.rows(sql, [ws, platform] if platform else [ws])[0]
    return (r["a"], r["b"]) if r["n"] else (None, None)


def checklist(ws: str, today: date | None = None) -> list[dict]:
    today = today or date.today()
    out = []
    for key, name, shows, table, platform, guide, essential in ITEMS:
        a, b = _range(table, ws, platform)
        item = {"key": key, "name": name, "shows": shows, "guide": guide, "essential": essential}
        if a is None:
            item.update(status="missing", detail="Not added yet.", todo=FIRST_TIME[key])
        elif key == "products":
            item.update(status="ok", detail="Added.", todo="Upload it again when you add new products.")
        else:
            stale = (today - b).days > STALE_DAYS
            item.update(status="old" if stale else "ok", detail=f"Covers {a:%-d %b %Y} to {b:%-d %b %Y}.",
                        todo=f"Next time, download from {(b + timedelta(days=1)):%-d %b %Y} to today." + (
                            " It is more than a month old." if stale else ""))
        if key == "ig_daily" and a is not None:
            have = {r["metric"] for r in db.rows("SELECT DISTINCT metric FROM social_daily WHERE ws = ? AND platform = 'Instagram'", [ws])}
            missing = [label for m, label in DAILY if m not in have]
            if missing:
                item.update(status="partial", todo=f"Still to add: {', '.join(missing)}. " + item["todo"])
        out.append(item)
    return out


def next_step(items: list[dict]) -> dict | None:
    for it in items:
        if it["status"] in ("missing", "partial", "old") and it["essential"]:
            return {"title": f"Add next: {it['name']}.", "todo": it["todo"]}
    return None
