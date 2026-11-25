"""Sales, customers and website analytics."""
from __future__ import annotations

from datetime import timedelta

from .. import db
from .common import Period, bucket_for, div, eur, has, pct_change, subtitle

LINE_LABEL = {"women": "Women's line", "children": "Children's line"}
FABRIC_LABEL = {"bamboo": "Bamboo", "cotton": "Cotton", "silk": "Silk"}
from .. import profile as prof  # noqa: E402


def totals(ws: str, a, b) -> dict:
    r = db.rows("""SELECT count(*) orders, coalesce(sum(total),0) revenue, avg(total) aov, count(DISTINCT customer_id) customers,
                   avg(CASE WHEN is_gift THEN 1 ELSE 0 END) gift_share
                   FROM orders WHERE ws = ? AND date BETWEEN ? AND ?""", [ws, a, b])[0]
    units = db.one("SELECT sum(quantity) FROM order_items WHERE ws = ? AND date BETWEEN ? AND ?", [ws, a, b])
    rep = db.rows("""WITH firsts AS (SELECT customer_id, min(date) AS first_d FROM orders WHERE ws = ? GROUP BY 1)
        SELECT count(DISTINCT CASE WHEN f.first_d < ? THEN o.customer_id END) returning_n,
               count(DISTINCT CASE WHEN f.first_d >= ? THEN o.customer_id END) new_n
        FROM orders o JOIN firsts f USING (customer_id) WHERE o.ws = ? AND o.date BETWEEN ? AND ?""", [ws, a, a, ws, a, b])[0]
    r["units"] = units
    r["returning_customers"] = rep["returning_n"]
    r["new_customers"] = rep["new_n"]
    r["returning_share"] = div(rep["returning_n"], (rep["returning_n"] or 0) + (rep["new_n"] or 0))
    return r


def repeat_rate(ws: str, end=None) -> float | None:
    """Share of customers (to date) with two or more orders."""
    r = db.rows("""SELECT avg(CASE WHEN n >= 2 THEN 1 ELSE 0 END) rr, count(*) customers FROM
        (SELECT customer_id, count(*) n FROM orders WHERE ws = ? AND customer_id IS NOT NULL AND date <= coalesce(?, DATE '2999-01-01') GROUP BY 1)""",
                [ws, end])[0]
    return r["rr"] if r["customers"] else None


def series(ws: str, a, b, bucket: str) -> list[dict]:
    return db.rows(f"""SELECT date_trunc('{bucket}', date)::DATE AS period, count(*) orders, sum(total) revenue
        FROM orders WHERE ws = ? AND date BETWEEN ? AND ? GROUP BY 1 ORDER BY 1""", [ws, a, b])


def overview(ws: str, p: Period) -> dict:
    if not has("orders", ws):
        return {"empty": True}
    cur, prev = totals(ws, p.start, p.end), totals(ws, p.prev_start, p.prev_end)
    ly = totals(ws, p.ly_start, p.ly_end)
    bucket = bucket_for(p)
    cur_series = series(ws, p.start, p.end, bucket)
    ly_series = series(ws, p.ly_start, p.ly_end, bucket)
    spark = series(ws, p.end - timedelta(days=7 * 12 - 1), p.end, "week")
    labels = [r["source_label"] for r in db.rows(
        "SELECT DISTINCT source_label FROM datasets WHERE ws = ? AND table_type = 'orders' AND coalesce(status, 'active') = 'active'", [ws])]
    src = " and ".join(labels) if labels and len(labels) <= 2 else "Your sales data"

    rev_change = pct_change(cur["revenue"], prev["revenue"])
    if rev_change is None:
        rev_title = f"You took {eur(cur['revenue'])} from {cur['orders']} orders"
    else:
        rev_title = f"Revenue {'up' if rev_change >= 0 else 'down'} {abs(rev_change):.0f}% on the previous period"
    if ly["orders"]:
        yoy = pct_change(cur["revenue"], ly["revenue"])
        rev_title += f", {'+' if (yoy or 0) >= 0 else ''}{yoy:.0f}% on last year" if yoy is not None else ""

    channels = db.rows("""SELECT coalesce(channel, 'Unknown') channel, count(*) orders, sum(total) revenue FROM orders
        WHERE ws = ? AND date BETWEEN ? AND ? GROUP BY 1 ORDER BY revenue DESC""", [ws, p.start, p.end])
    codes = db.rows("""SELECT discount_code code, count(*) orders, sum(total) revenue, avg(discount) avg_discount FROM orders
        WHERE ws = ? AND date BETWEEN ? AND ? AND discount_code IS NOT NULL AND discount_code <> '' GROUP BY 1 ORDER BY orders DESC""",
                    [ws, p.start, p.end])
    products = db.rows("""SELECT regexp_replace(product, ' - .*$', '') product, sum(quantity) units, sum(quantity*price) revenue,
        any_value(fabric) fabric, any_value(line) line FROM order_items WHERE ws = ? AND date BETWEEN ? AND ? GROUP BY 1
        ORDER BY revenue DESC LIMIT 12""", [ws, p.start, p.end])
    fabric = db.rows("""SELECT coalesce(fabric, 'other') fabric, sum(quantity) units, sum(quantity*price) revenue FROM order_items
        WHERE ws = ? AND date BETWEEN ? AND ? GROUP BY 1 ORDER BY units DESC""", [ws, p.start, p.end])
    line = db.rows("""SELECT coalesce(line, 'other') line, sum(quantity) units, sum(quantity*price) revenue FROM order_items
        WHERE ws = ? AND date BETWEEN ? AND ? GROUP BY 1 ORDER BY units DESC""", [ws, p.start, p.end])
    colours = db.rows("""SELECT colour, sum(quantity) units FROM order_items WHERE ws = ? AND date BETWEEN ? AND ? AND colour IS NOT NULL
        GROUP BY 1 ORDER BY units DESC LIMIT 10""", [ws, p.start, p.end])
    seasonality = db.rows("""SELECT month(date) m, count(*) / count(DISTINCT year(date)) orders, sum(total) / count(DISTINCT year(date)) revenue
        FROM orders WHERE ws = ? GROUP BY 1 ORDER BY 1""", [ws])
    dist = db.rows("""SELECT CASE WHEN n = 1 THEN 'One order' WHEN n <= 3 THEN '2 to 3 orders' ELSE '4 or more' END grp, count(*) customers
        FROM (SELECT customer_id, count(*) n FROM orders WHERE ws = ? AND customer_id IS NOT NULL GROUP BY 1) GROUP BY 1""", [ws])
    order = {"One order": 0, "2 to 3 orders": 1, "4 or more": 2}
    dist.sort(key=lambda r: order[r["grp"]])

    fab_units = {r["fabric"]: r["units"] or 0 for r in fabric}
    fab_title = "Product mix by fabric"
    ranked = sorted([(k, v) for k, v in fab_units.items() if k != "other" and v], key=lambda kv: -kv[1])
    if len(ranked) >= 2:
        (a, ua), (b, ub) = ranked[0], ranked[1]
        ratio = ua / ub
        la, lb = FABRIC_LABEL.get(a, a.title()), FABRIC_LABEL.get(b, b.title()).lower()
        fab_title = f"{la} outsells {lb} {ratio:.1f} to 1" if ratio >= 1.2 else f"{la} and {lb} sell about the same"
    line_units = {r["line"]: r["units"] or 0 for r in line}
    tot_units = sum(line_units.values()) or 1
    line_title = f"The children's line is {line_units.get('children', 0) / tot_units * 100:.0f}% of units sold" if line_units.get("children") else "Sales by product line"
    top_ch = channels[0] if channels else None
    ch_title = f"{top_ch['channel']} brings {top_ch['revenue'] / max(1, sum(c['revenue'] or 0 for c in channels)) * 100:.0f}% of revenue" if top_ch else "Where sales come from"
    peak = max(seasonality, key=lambda r: r["orders"]) if seasonality else None
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    season_title = f"{months[peak['m'] - 1]} is your busiest month" if peak else "Seasonality"
    if peak and prof.key_date(ws, peak["m"]):
        season_title = f"{months[peak['m'] - 1]} ({prof.key_date(ws, peak['m'])}) is your busiest month"
    total_c = sum(r["customers"] for r in dist) or 1
    one = next((r["customers"] for r in dist if r["grp"] == "One order"), 0)
    dist_title = (f"{one / total_c * 100:.0f}% of customers have bought only once" if dist else
                  "Repeat customers need a customer email or id in your sales file")

    return {
        "period": {"label": p.label, "start": p.start.isoformat(), "end": p.end.isoformat()},
        "kpis": {
            "revenue": {"value": cur["revenue"], "prev": prev["revenue"], "change": rev_change, "spark": [r["revenue"] for r in spark]},
            "orders": {"value": cur["orders"], "prev": prev["orders"], "change": pct_change(cur["orders"], prev["orders"]), "spark": [r["orders"] for r in spark]},
            "aov": {"value": cur["aov"], "prev": prev["aov"], "change": pct_change(cur["aov"], prev["aov"])},
            "units": {"value": cur["units"], "prev": prev["units"], "change": pct_change(cur["units"], prev["units"])},
            "returning_share": {"value": cur["returning_share"], "prev": prev["returning_share"]},
            "repeat_rate": {"value": repeat_rate(ws, p.end), "prev": repeat_rate(ws, p.prev_end)},
            "gift_share": {"value": cur["gift_share"], "prev": prev["gift_share"]},
            "new_customers": {"value": cur["new_customers"], "prev": prev["new_customers"]},
        },
        "revenue_chart": {"title": rev_title, "subtitle": subtitle(p, src), "bucket": bucket, "current": cur_series, "last_year": ly_series},
        "channels": {"title": ch_title, "subtitle": subtitle(p, src), "rows": channels},
        "codes": {"title": (f"{codes[0]['code']} is your most used discount code" if codes else "No discount codes used in this period"),
                  "subtitle": subtitle(p, src), "rows": codes},
        "products": {"title": f"{products[0]['product']} earns the most" if products else "Top products", "subtitle": subtitle(p, src), "rows": products},
        "fabric": {"title": fab_title, "subtitle": subtitle(p, src), "rows": [{**r, "label": FABRIC_LABEL.get(r["fabric"], r["fabric"].title())} for r in fabric]},
        "line": {"title": line_title, "subtitle": subtitle(p, src), "rows": [{**r, "label": LINE_LABEL.get(r["line"], r["line"].title())} for r in line]},
        "colours": {"title": f"{colours[0]['colour']} is the best-selling colour" if colours else "Colours", "subtitle": subtitle(p, src), "rows": colours},
        "seasonality": {"title": season_title, "subtitle": "Average orders per calendar month, all data · Shopify orders",
                        "rows": [{"month": months[r["m"] - 1][:3], **r} for r in seasonality],
                        "awareness": {months[d["month"] - 1][:3]: d["label"] for d in prof.get(ws)["key_dates"]},
                        "attribute_label": prof.get(ws)["attribute_label"]},
        "loyalty": {"title": dist_title, "subtitle": f"All customers to date · {src}", "rows": dist},
        "cohorts": cohorts(ws, p.end),
        "gift": {"value": cur["gift_share"]},
    }


def cohorts(ws: str, end) -> dict:
    rows = db.rows("""WITH o AS (SELECT customer_id, date_trunc('month', date)::DATE AS m FROM orders WHERE ws = ? AND customer_id IS NOT NULL AND date <= ?),
        f AS (SELECT customer_id, min(m) cohort FROM o GROUP BY 1),
        j AS (SELECT f.cohort, datediff('month', f.cohort, o.m) k, o.customer_id FROM o JOIN f USING (customer_id))
        SELECT cohort, k, count(DISTINCT customer_id) n FROM j WHERE k <= 6 GROUP BY 1, 2 ORDER BY 1, 2""", [ws, end])
    by: dict = {}
    for r in rows:
        by.setdefault(r["cohort"], {})[r["k"]] = r["n"]
    cohorts_sorted = sorted(by)[-12:]
    matrix = []
    for c in cohorts_sorted:
        size = by[c].get(0, 0)
        matrix.append({"cohort": c, "size": size, "retention": [round(by[c].get(k, 0) / size, 3) if size else None for k in range(1, 7)]})
    m1 = [m["retention"][0] for m in matrix if m["retention"][0] is not None]
    avg_m3 = [sum(x for x in m["retention"][:3] if x) for m in matrix[:-3]]
    title = "Customers who come back within three months" if not avg_m3 else \
        f"About {sum(avg_m3) / len(avg_m3) * 100:.0f}% of new customers buy again within three months"
    return {"title": title, "subtitle": "Monthly groups of first-time buyers · Shopify orders", "rows": matrix, "has_data": bool(m1)}


def web(ws: str, p: Period) -> dict:
    if not has("web_sessions", ws):
        return {"empty": True}
    def t(a, b):
        return db.rows("""SELECT sum(sessions) sessions, sum(users) users, sum(conversions) conversions, sum(revenue) revenue
            FROM web_sessions WHERE ws = ? AND date BETWEEN ? AND ?""", [ws, a, b])[0]
    cur, prev = t(p.start, p.end), t(p.prev_start, p.prev_end)
    conv = div(cur["conversions"], cur["sessions"])
    sources = db.rows("""SELECT source, sum(sessions) sessions, sum(conversions) conversions, sum(conversions)/nullif(sum(sessions),0) conv_rate
        FROM web_sessions WHERE ws = ? AND date BETWEEN ? AND ? GROUP BY 1 ORDER BY sessions DESC LIMIT 8""", [ws, p.start, p.end])
    pages = db.rows("""SELECT landing_page page, sum(sessions) sessions, sum(conversions)/nullif(sum(sessions),0) conv_rate
        FROM web_sessions WHERE ws = ? AND date BETWEEN ? AND ? AND landing_page IS NOT NULL GROUP BY 1 ORDER BY sessions DESC LIMIT 8""",
                    [ws, p.start, p.end])
    devices = db.rows("""SELECT coalesce(device, 'unknown') device, sum(sessions) sessions, sum(conversions)/nullif(sum(sessions),0) conv_rate
        FROM web_sessions WHERE ws = ? AND date BETWEEN ? AND ? GROUP BY 1 ORDER BY sessions DESC""", [ws, p.start, p.end])
    bucket = bucket_for(p)
    trend = db.rows(f"""SELECT date_trunc('{bucket}', date)::DATE AS period, sum(sessions) sessions FROM web_sessions
        WHERE ws = ? AND date BETWEEN ? AND ? GROUP BY 1 ORDER BY 1""", [ws, p.start, p.end])
    orders = db.one("SELECT count(*) FROM orders WHERE ws = ? AND date BETWEEN ? AND ?", [ws, p.start, p.end])
    src = "Google Analytics"
    mob = next((d for d in devices if d["device"] == "mobile"), None)
    desk = next((d for d in devices if d["device"] == "desktop"), None)
    dev_title = "Visits by device"
    if mob and desk and mob["conv_rate"] and desk["conv_rate"]:
        share = mob["sessions"] / sum(d["sessions"] for d in devices)
        dev_title = f"{share * 100:.0f}% of visits are on phones, but phones convert {desk['conv_rate'] / mob['conv_rate']:.1f}x less often"
    top = sources[0] if sources else None
    return {
        "kpis": {"sessions": {"value": cur["sessions"], "prev": prev["sessions"], "change": pct_change(cur["sessions"], prev["sessions"])},
                 "conversion": {"value": conv, "prev": div(prev["conversions"], prev["sessions"])},
                 "revenue": {"value": cur["revenue"], "prev": prev["revenue"]}},
        "trend": {"title": f"{cur['sessions']:,.0f} visits, {'up' if (pct_change(cur['sessions'], prev['sessions']) or 0) >= 0 else 'down'} "
                           f"{abs(pct_change(cur['sessions'], prev['sessions']) or 0):.0f}% on the previous period",
                  "subtitle": subtitle(p, src), "rows": trend},
        "sources": {"title": f"Most visitors find you through {top['source']}" if top else "Where visitors came from",
                    "subtitle": subtitle(p, src), "rows": sources},
        "pages": {"title": "Pages people land on first", "subtitle": subtitle(p, src), "rows": pages},
        "devices": {"title": dev_title, "subtitle": subtitle(p, src), "rows": devices},
        "funnel": {"title": f"{conv * 100:.1f}% of visits end in a purchase" if conv else "From visit to purchase",
                   "subtitle": subtitle(p, f"{src} and Shopify"),
                   "steps": [{"step": "Visits", "value": cur["sessions"]}, {"step": "Purchases (website)", "value": cur["conversions"]},
                             {"step": "Orders (all channels)", "value": orders}]},
    }


def email(ws: str, p: Period) -> dict:
    if not has("email_campaigns", ws):
        return {"empty": True}
    rows = db.rows("""SELECT campaign, count(*) sends, sum(opens)/sum(recipients) open_rate, sum(clicks)/sum(recipients) click_rate,
        sum(revenue) revenue FROM email_campaigns WHERE ws = ? AND date BETWEEN ? AND ? GROUP BY 1 ORDER BY open_rate DESC""",
                   [ws, p.start - timedelta(days=270), p.end])
    title = f"'{rows[0]['campaign']}' gets the best open rate" if rows else "Email campaigns"
    return {"title": title, "subtitle": f"Last 12 months to {p.end:%-d %b %Y} · Klaviyo", "rows": rows}
