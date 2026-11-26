"""Decision analyses that join sources together: does Instagram sell, what to do with each product,
which customer groups to look after, and how to plan for the busy months.

Every function returns one plain answer (title), one table or chart (rows) and one next step (todo).
Patterns are described as patterns, never as proof, and nothing is predicted as a single exact number.
"""
from __future__ import annotations

from datetime import date, timedelta
from statistics import mean

import pandas as pd

from .. import db
from .text import PILLAR_LABELS, THEMES

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def _pct(a, b):
    return None if not b else round((a / b - 1) * 100)


# --------------------------------------------------------------------------------------
# 1. Does Instagram sell?
# --------------------------------------------------------------------------------------
def instagram_sales(ws: str, end: date) -> dict | None:
    posts = db.q("SELECT date, format, pillar FROM social_posts WHERE ws = ? AND platform = 'Instagram' AND date BETWEEN ? AND ?",
                 [ws, end - timedelta(days=364), end])
    orders = db.q("SELECT date, count(*) n FROM orders WHERE ws = ? AND date BETWEEN ? AND ? GROUP BY 1", [ws, end - timedelta(days=364), end])
    if len(posts) < 12 or orders.empty:
        return None
    posts["date"] = pd.to_datetime(posts["date"]).dt.date
    orders["date"] = pd.to_datetime(orders["date"]).dt.date
    start = max(min(posts["date"]), min(orders["date"]))
    days = pd.date_range(start, end).date
    raw = pd.Series(0.0, index=pd.Index(days))
    for r in orders.itertuples():
        if r.date in raw.index:
            raw[r.date] = r.n
    # each day compared with its own month, so busy seasons do not count as a post effect
    level = raw.rolling(29, center=True, min_periods=7).mean().replace(0, pd.NA).bfill().ffill()
    per_day = (raw / level).astype(float).to_dict()
    avg_orders = float(raw.mean())
    post_days = set(posts["date"])
    quiet = [d for d in days if not ({d, d - timedelta(days=1), d - timedelta(days=2)} & post_days)]
    if len(quiet) < 20:
        quiet = [d for d in days if d not in post_days and d - timedelta(days=1) not in post_days]
    base = mean(per_day[d] for d in quiet) if quiet else None
    if not base:
        return None

    def lift(sub: pd.DataFrame, label: str, kind: str) -> dict | None:
        if len(sub) < 8:
            return None
        after = {d for p in sub["date"] for d in (p, p + timedelta(days=1)) if d in per_day}
        v = mean(per_day[d] for d in after)
        return {"label": label, "kind": kind, "posts": len(sub), "orders_per_day": round(v / base * avg_orders, 1), "lift": _pct(v, base)}

    rows = [r for f, sub in posts.groupby("format") if f and (r := lift(sub, str(f), "format"))]
    rows += [r for pl, sub in posts.groupby("pillar") if pl and (r := lift(sub, PILLAR_LABELS.get(pl, pl), "topic"))]
    if not rows:
        return None
    rows.sort(key=lambda r: -(r["lift"] or 0))

    visits = None
    v = db.q("SELECT date, value FROM social_daily WHERE ws = ? AND platform = 'Instagram' AND metric = 'profile_visits' AND date BETWEEN ? AND ?",
             [ws, start, end])
    if len(v) >= 28:
        v["date"] = pd.to_datetime(v["date"]).dt.date
        med = v["value"].median()
        hi = [per_day.get(d, 0) for d in v[v["value"] > med]["date"] if d in per_day]
        lo = [per_day.get(d, 0) for d in v[v["value"] <= med]["date"] if d in per_day]
        if hi and lo and mean(lo):
            visits = {"lift": _pct(mean(hi), mean(lo)), "days": len(v)}

    formats = [r for r in rows if r["kind"] == "format"]
    best = formats[0] if formats else rows[0]
    weak = [r["label"] for r in formats if (r["lift"] or 0) <= 0]
    if (best["lift"] or 0) >= 5:
        title = f"Orders are {best['lift']}% higher in the two days after a {best['label'].lower()} post"
        todo = (f"Post more {best['label'].lower()} posts that show a product in use, and point to the shop in the caption and Stories."
                + (f" {', '.join(weak)} posts bring no extra orders: use them for community, not selling." if weak else ""))
    else:
        title = "No type of post clearly brings extra orders yet"
        todo = "Try one clear product post a week with a link in Stories for a month, then check this card again."
    return {"title": title, "rows": rows, "baseline": round(avg_orders, 1), "visits": visits, "todo": todo,
            "subtitle": f"{start:%-d %b %Y} to {end:%-d %b %Y} · Instagram posts and Shopify orders",
            "note": "Orders on the day of a post and the day after, compared with quiet days in the same weeks, so busy seasons do not count. "
                    "This is a pattern, not proof: sales, events and the season also move orders."}


# --------------------------------------------------------------------------------------
# 2. Product decision map
# --------------------------------------------------------------------------------------
ACTION = {
    "grow": ("Grow", "Customers love it and sales are holding up. Keep it in stock and give it more posts."),
    "promote": ("Show it again", "Customers rate it well, but it is growing much slower than the rest of the shop. Feature it again before deciding to drop it."),
    "fix": ("Fix first", "It sells, but rates below your average. Fix what people mention before ordering more."),
    "rethink": ("Rethink", "Lower rating, and it is falling behind the rest of the shop. Consider changing it or replacing it."),
}


def product_map(ws: str, end: date) -> dict | None:
    items = db.q("SELECT product, date, quantity, price FROM order_items WHERE ws = ? AND date BETWEEN ? AND ? AND product IS NOT NULL",
                 [ws, end - timedelta(days=455), end])
    if items.empty:
        return None
    items["date"] = pd.to_datetime(items["date"]).dt.date
    items["model"] = items["product"].astype(str).str.split(" - ").str[0].str.strip()
    items["revenue"] = items["quantity"].fillna(1) * items["price"].fillna(0)
    rev = db.q("SELECT product, rating, themes, sentiment FROM feedback WHERE ws = ? AND kind = 'review' AND rating IS NOT NULL", [ws])
    rev["model"] = rev["product"].astype(str).str.split(" - ").str[0].str.strip()
    avg_all = float(rev["rating"].mean()) if len(rev) else None
    cut = end - timedelta(days=89)
    first = min(items["date"])
    yoy = first <= cut - timedelta(days=365)  # compare with the same 90 days last year, so the season does not count as growth
    prev_a, prev_b = (cut - timedelta(days=365), end - timedelta(days=365)) if yoy else (cut - timedelta(days=90), cut - timedelta(days=1))
    year = items[items["date"] >= end - timedelta(days=364)]
    q = items["quantity"].fillna(1)
    all_recent = q[items["date"] >= cut].sum()
    all_before = q[(items["date"] >= prev_a) & (items["date"] <= prev_b)].sum()
    brand = (all_recent / all_before - 1) if all_before else 0.0
    rows = []
    for model, g in items.groupby("model"):
        recent = g[g["date"] >= cut]["quantity"].fillna(1).sum()
        before = g[(g["date"] >= prev_a) & (g["date"] <= prev_b)]["quantity"].fillna(1).sum()
        if recent + before < 6:
            continue
        trend = _pct(recent, before) if before else None
        # against the brand: a product growing slower than the whole shop is losing ground
        vs_brand = round(((recent / before) / (1 + brand) - 1) * 100) if before else None
        r = rev[rev["model"] == model]
        rating = round(float(r["rating"].mean()), 2) if len(r) >= 5 else None
        neg = r[(r["sentiment"] == "negative") | (r["rating"] <= 3)]["themes"].dropna().str.split(",").explode().str.strip()
        neg = neg[neg != ""]
        issue = THEMES.get(neg.value_counts().index[0], {}).get("label") if len(neg) else None
        good = rating is None or avg_all is None or rating >= avg_all - 0.1
        falling = vs_brand is not None and vs_brand <= -15
        key = ("promote" if falling else "grow") if good else ("rethink" if falling else "fix")
        reason = ACTION[key][1]
        if key == "fix" and issue:
            reason = f"It sells, but rates below your average. {issue} comes up most in reviews: fix that before ordering more."
        rows.append({"product": model, "group": key, "group_label": ACTION[key][0], "units_90d": int(recent), "trend": trend, "vs_brand": vs_brand,
                     "revenue_12m": round(float(year[year["model"] == model]["revenue"].sum()), 2), "rating": rating, "reviews": int(len(r)), "issue": issue, "reason": reason})
    if not rows:
        return None
    rows.sort(key=lambda x: -x["revenue_12m"])
    count = {k: sum(1 for x in rows if x["group"] == k) for k in ACTION}
    title = "What to do with each product"
    summary = f"{count['grow']} to grow, {count['promote']} to show again, {count['fix']} to fix first, {count['rethink']} to rethink"
    first_fix = next((x for x in rows if x["group"] == "fix"), None)
    first_grow = next((x for x in rows if x["group"] == "grow"), None)
    todo = (f"Fix {first_fix['product']} first" + (f" ({first_fix['issue'].lower()})" if first_fix["issue"] else "") + ": it sells, but disappoints some buyers."
            if first_fix else f"Give {first_grow['product']} more stock and more posts." if first_grow else "Feature the products to show again in your next posts.")
    return {"title": title, "summary": summary, "rows": rows, "counts": count, "brand_trend": round(brand * 100), "average_rating": round(avg_all, 2) if avg_all else None, "todo": todo,
            "subtitle": ("Units in the last 90 days against the same 90 days last year" if yoy else "Units in the last 90 days against the 90 days before")
                        + ", and the average review rating · Shopify orders and Judge.me reviews", "compare": "last_year" if yoy else "previous",
            "note": "Products are grouped by model (colours together). A product needs at least 5 reviews for its rating to count."}


# --------------------------------------------------------------------------------------
# 3. Customer groups
# --------------------------------------------------------------------------------------
GROUPS = [
    ("loyal", "Loyal", "3 or more orders, bought in the last 6 months",
     "Thank them: early access to new colours, and ask for a review or a photo (only with consent)."),
    ("returning", "Returning", "2 orders, bought in the last 6 months",
     "Help them become regulars: a care tip email and a note when a new colour arrives."),
    ("new", "New", "First order in the last 3 months",
     "Send a warm, care-first email about 30 days after purchase, so a second order feels natural."),
    ("at_risk", "At risk", "Bought more than once, but nothing for 6 to 12 months",
     "Send a short personal note with what is new. Never assume anything about anyone's health."),
    ("one_time", "One-time", "One order, 3 to 12 months ago",
     "Show once, without pressure, what goes well with what they bought."),
    ("quiet", "Gone quiet", "Nothing for over a year",
     "No need to chase them. Include them only in big moments like October."),
]


def segments(ws: str, end: date) -> dict | None:
    c = db.q("""SELECT customer_id, count(*) n, max(date) last_d, sum(total) spend FROM orders
        WHERE ws = ? AND customer_id IS NOT NULL AND date <= ? GROUP BY 1""", [ws, end])
    if len(c) < 30:
        return None
    c["days"] = [(end - d).days for d in pd.to_datetime(c["last_d"]).dt.date]

    def group(r) -> str:
        if r.days > 365:
            return "quiet"
        if r.n >= 2 and r.days > 180:
            return "at_risk"
        if r.n >= 3:
            return "loyal"
        if r.n == 2:
            return "returning"
        return "new" if r.days <= 90 else "one_time"
    c["g"] = [group(r) for r in c.itertuples()]
    total_rev = float(c["spend"].sum()) or 1.0
    rows = []
    for key, label, rule, action in GROUPS:
        g = c[c["g"] == key]
        rows.append({"group": key, "label": label, "rule": rule, "action": action, "customers": int(len(g)),
                     "share": round(len(g) / len(c), 3), "revenue_share": round(float(g["spend"].sum()) / total_rev, 3),
                     "avg_spend": round(float(g["spend"].mean()), 2) if len(g) else None})
    by = {r["group"]: r for r in rows}
    loyal = by["loyal"]
    title = (f"{loyal['share'] * 100:.0f}% of customers are loyal and bring {loyal['revenue_share'] * 100:.0f}% of revenue"
             if loyal["customers"] else "No loyal customers yet: the next step is a second order")
    biggest = max((by["new"], by["at_risk"], by["one_time"]), key=lambda r: r["customers"])
    return {"title": title, "rows": rows, "customers": int(len(c)), "todo_lead": f"This month: {biggest['label']} ({biggest['customers']} people).", "todo": biggest["action"],
            "subtitle": f"{len(c):,} customers up to {end:%-d %b %Y} · Shopify orders (emails turned into anonymous ids)",
            "note": "Each customer is in one group only. Nobody's name is used, and groups are never based on health or personal circumstances."}


# --------------------------------------------------------------------------------------
# 4. Seasonal planning guide
# --------------------------------------------------------------------------------------
def seasonal(ws: str, end: date) -> dict | None:
    m = db.q("SELECT date_trunc('month', date)::DATE m, count(*) n FROM orders WHERE ws = ? AND date <= ? GROUP BY 1 ORDER BY 1", [ws, end])
    if m.empty:
        return None
    m["m"] = pd.to_datetime(m["m"]).dt.date
    this_month = end.replace(day=1)
    full = m[m["m"] < this_month]
    if len(full) < 12:
        return None
    full = full.assign(month=[d.month for d in full["m"]])
    overall = float(full["n"].mean())
    index = {k: float(g["n"].mean()) / overall for k, g in full.groupby("month")}
    base = float(full.tail(12)["n"].mean())
    rows = []
    d = this_month
    for _ in range(12):
        d = (d + timedelta(days=32)).replace(day=1)
        idx = index.get(d.month)
        if idx is None:
            continue
        exp = base * idx
        last = full[full["m"] == d.replace(year=d.year - 1)]["n"]
        rows.append({"month": f"{d:%Y-%m}", "label": f"{MONTHS[d.month - 1]} {d.year}", "index": round(idx, 2),
                     "low": int(round(exp * 0.85)), "high": int(round(exp * 1.15)), "mid": int(round(exp)),
                     "last_year": int(last.iloc[0]) if len(last) else None})
    if not rows:
        return None
    peak = max(index, key=index.get)
    peak_name = MONTHS[peak - 1]
    prep = MONTHS[(peak - 3) % 12]
    top = db.q("""SELECT split_part(product, ' - ', 1) model, sum(coalesce(quantity, 1)) u FROM order_items
        WHERE ws = ? AND month(date) = ? GROUP BY 1 ORDER BY 2 DESC LIMIT 3""", [ws, peak])
    years = full[full["month"] == peak]["m"].nunique() or 1
    sellers = [{"product": r.model, "units": int(round(r.u / years))} for r in top.itertuples()]
    title = f"{peak_name} is usually your busiest month: about {index[peak]:.1f}x a normal month"
    todo = (f"In {prep}, order stock for {peak_name}" + (f", above all {sellers[0]['product']} (about {sellers[0]['units']} sold in a usual {peak_name})" if sellers else "")
            + ", and plan posts and partners ahead.")
    return {"title": title, "rows": rows, "peak": peak_name, "peak_index": round(index[peak], 2), "sellers": sellers, "base": round(base),
            "by_month": [{"month": MONTHS[k - 1], "index": round(v, 2)} for k, v in sorted(index.items())], "todo": todo,
            "subtitle": f"Based on {len(full)} full months of Shopify orders",
            "note": "A planning range, not a promise: each month's usual level compared with an average month, applied to your last 12 months. "
                    "The range is plus or minus 15%."}
