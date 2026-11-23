"""Voice of the customer: ratings, sentiment, themes, NPS, languages and who is missing."""
from __future__ import annotations

from .. import db
from .common import Period, bucket_for, div, has, pct_change, subtitle
from .text import LANG_NAMES, THEMES

MIN_THEME_N = 5


def nps(ws: str, a, b) -> dict:
    r = db.rows("""SELECT count(*) n, avg(CASE WHEN nps >= 9 THEN 1 ELSE 0 END) pro, avg(CASE WHEN nps <= 6 THEN 1 ELSE 0 END) det
        FROM feedback WHERE ws = ? AND nps IS NOT NULL AND date BETWEEN ? AND ?""", [ws, a, b])[0]
    if not r["n"]:
        return {"n": 0, "score": None}
    return {"n": r["n"], "score": round((r["pro"] - r["det"]) * 100), "promoters": r["pro"], "detractors": r["det"],
            "passives": 1 - r["pro"] - r["det"]}


def rating(ws: str, a, b) -> dict:
    return db.rows("""SELECT count(*) n, avg(rating) avg FROM feedback WHERE ws = ? AND rating IS NOT NULL AND date BETWEEN ? AND ?""",
                   [ws, a, b])[0]


def theme_table(ws: str, a, b, where: str = "") -> list[dict]:
    return db.rows(f"""SELECT theme, count(*) n, avg(sentiment_score) sentiment,
        avg(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) neg_share
        FROM (SELECT unnest(string_split(themes, ',')) theme, sentiment, sentiment_score FROM feedback
              WHERE ws = ? AND date BETWEEN ? AND ? AND themes <> '' {where})
        GROUP BY 1 ORDER BY n DESC""", [ws, a, b])


def overview(ws: str, p: Period) -> dict:
    if not has("feedback", ws):
        return {"empty": True}
    total = db.one("SELECT count(*) FROM feedback WHERE ws = ? AND date BETWEEN ? AND ?", [ws, p.start, p.end])
    rt, rt_prev = rating(ws, p.start, p.end), rating(ws, p.prev_start, p.prev_end)
    n_cur, n_prev = nps(ws, p.start, p.end), nps(ws, p.prev_start, p.prev_end)
    # NPS needs a decent sample: widen to 12 months if the period is thin
    n_wide = nps(ws, p.end.replace(year=p.end.year - 1), p.end)
    sent = db.rows("""SELECT sentiment, count(*) n FROM feedback WHERE ws = ? AND date BETWEEN ? AND ? GROUP BY 1""", [ws, p.start, p.end])
    sent_map = {r["sentiment"]: r["n"] for r in sent}
    pos_share = div(sent_map.get("positive", 0), sum(sent_map.values()))

    bucket = "month" if p.days > 120 else "week"
    stream_start = p.start if p.days > 120 else p.end.replace(year=p.end.year - 1)
    stream = db.rows(f"""SELECT date_trunc('{bucket}', date)::DATE AS period, sentiment, count(*) n FROM feedback
        WHERE ws = ? AND date BETWEEN ? AND ? AND date IS NOT NULL GROUP BY 1, 2 ORDER BY 1""", [ws, stream_start, p.end])

    dist = db.rows("""SELECT rating::INT stars, count(*) n FROM feedback WHERE ws = ? AND rating IS NOT NULL AND date BETWEEN ? AND ?
        GROUP BY 1 ORDER BY 1 DESC""", [ws, p.start, p.end])
    by_fabric = db.rows("""SELECT fabric, avg(rating) avg, count(*) n FROM feedback WHERE ws = ? AND rating IS NOT NULL AND fabric IS NOT NULL
        AND date BETWEEN ? AND ? GROUP BY 1 HAVING count(*) >= 3 ORDER BY avg DESC""", [ws, p.start, p.end])

    cur_t = {r["theme"]: r for r in theme_table(ws, p.start, p.end)}
    prev_t = {r["theme"]: r for r in theme_table(ws, p.prev_start, p.prev_end)}
    n_cur_total = max(total, 1)
    n_prev_total = max(db.one("SELECT count(*) FROM feedback WHERE ws = ? AND date BETWEEN ? AND ?", [ws, p.prev_start, p.prev_end]), 1)
    themes = []
    for k, r in cur_t.items():
        share, prev_share = r["n"] / n_cur_total, (prev_t.get(k, {}).get("n", 0) / n_prev_total)
        themes.append({"theme": k, "label": THEMES.get(k, {}).get("label", k.title()), "n": r["n"], "share": round(share, 3),
                       "sentiment": round(r["sentiment"], 2), "neg_share": round(r["neg_share"], 3),
                       "change_pts": round((share - prev_share) * 100, 1) if prev_t else None})
    themes.sort(key=lambda r: -r["n"])
    rising = [t for t in themes if t["change_pts"] is not None and t["change_pts"] >= 3 and t["n"] >= MIN_THEME_N]
    falling = [t for t in themes if t["change_pts"] is not None and t["change_pts"] <= -3 and t["n"] >= MIN_THEME_N]

    # NPS reasons over the wider window for a stable sample
    a12 = p.end.replace(year=p.end.year - 1)
    det = theme_table(ws, a12, p.end, "AND nps IS NOT NULL AND nps <= 6")
    pro = theme_table(ws, a12, p.end, "AND nps IS NOT NULL AND nps >= 9")
    heard = db.rows("""SELECT heard_from, count(*) n, avg(nps) avg_nps FROM feedback WHERE ws = ? AND heard_from IS NOT NULL
        AND date BETWEEN ? AND ? GROUP BY 1 ORDER BY n DESC""", [ws, a12, p.end])
    products = db.rows("""SELECT regexp_replace(product, ' - .*$', '') product, avg(rating) avg, count(*) n,
        avg(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) neg_share
        FROM feedback WHERE ws = ? AND rating IS NOT NULL AND product IS NOT NULL AND date BETWEEN ? AND ?
        GROUP BY 1 HAVING count(*) >= 3 ORDER BY avg DESC""", [ws, a12, p.end])
    langs = db.rows("""SELECT language, count(*) n FROM feedback WHERE ws = ? AND date BETWEEN ? AND ? GROUP BY 1 ORDER BY n DESC""",
                    [ws, p.start, p.end])
    for r in langs:
        r["label"] = LANG_NAMES.get(r["language"], r["language"])
    quotes = db.rows("""SELECT _key id, date, kind, source, text, rating, nps, product, language, consent_quote, sentiment, themes
        FROM feedback WHERE ws = ? AND date BETWEEN ? AND ? AND length(text) > 25 AND NOT distress
        ORDER BY CASE sentiment WHEN 'positive' THEN 0 WHEN 'negative' THEN 1 ELSE 2 END, date DESC LIMIT 60""", [ws, p.start, p.end])
    care = db.rows("""SELECT _key id, date, source, text FROM feedback WHERE ws = ? AND distress ORDER BY date DESC LIMIT 10""", [ws])
    care += db.rows("""SELECT _key id, date, platform AS source, text FROM social_comments WHERE ws = ? AND distress
        ORDER BY date DESC LIMIT 10""", [ws])

    src = "Reviews, surveys and messages"
    rchg = (rt["avg"] - rt_prev["avg"]) if rt["avg"] and rt_prev["avg"] else None
    if rt["n"]:
        rating_title = f"Customers rate you {rt['avg']:.1f} out of 5" + (f", {'up' if rchg >= 0 else 'down'} {abs(rchg):.1f} on the previous period" if rchg and abs(rchg) >= 0.1 else "")
    else:
        rating_title = "No ratings in this period yet"
    fab_title = f"{by_fabric[0]['fabric'].title()} is your best-rated fabric ({by_fabric[0]['avg']:.1f})" if by_fabric else "Ratings by fabric"
    top_theme = themes[0] if themes else None
    theme_title = f"{top_theme['label']} is what customers talk about most" if top_theme else "What customers talk about"
    neg = sorted([t for t in themes if t["n"] >= MIN_THEME_N], key=lambda t: -t["neg_share"] * t["n"])
    neg_title = f"Most complaints are about {neg[0]['label'].lower()}" if neg and neg[0]["neg_share"] > 0.2 else None
    nps_title = "Not enough survey answers yet for a reliable NPS"
    if n_wide["n"] >= 30:
        nps_title = f"NPS is {n_wide['score']}" + (f"; detractors mostly mention {det[0]['theme'] and THEMES.get(det[0]['theme'], {}).get('label', '').lower()}" if det else "")
    stream_title = "How customers feel over time"
    if pos_share is not None:
        stream_title = f"{pos_share * 100:.0f}% of feedback in this period is positive"

    return {
        "kpis": {
            "rating": {"value": rt["avg"], "prev": rt_prev["avg"], "n": rt["n"]},
            "nps": {"value": n_wide["score"] if n_wide["n"] >= 30 else None, "n": n_wide["n"], "period_value": n_cur["score"],
                    "prev": n_prev["score"]},
            "positive_share": {"value": pos_share},
            "volume": {"value": total, "prev": n_prev_total if n_prev_total > 1 else None, "change": pct_change(total, n_prev_total)},
            "care": {"value": len(care)},
        },
        "stream": {"title": stream_title, "subtitle": subtitle(p, src), "bucket": bucket, "rows": stream},
        "ratings": {"title": rating_title, "subtitle": subtitle(p, "Product reviews"), "rows": dist},
        "fabric": {"title": fab_title, "subtitle": subtitle(p, "Product reviews"), "rows": by_fabric},
        "themes": {"title": theme_title, "subtitle": subtitle(p, src), "rows": themes, "rising": rising, "falling": falling,
                   "complaint_title": neg_title},
        "nps": {"title": nps_title, "subtitle": f"Last 12 months · Survey responses ({n_wide['n']} answers)", "summary": n_wide,
                "detractor_reasons": det[:5], "promoter_reasons": pro[:5], "heard_from": heard},
        "products": {"title": f"{products[0]['product']} has the happiest reviewers" if products else "Ratings by product",
                     "subtitle": "Last 12 months · Product reviews (products with 3 or more reviews)", "rows": products},
        "languages": {"title": (f"{langs[0]['n'] / max(1, sum(r['n'] for r in langs)) * 100:.0f}% of feedback is in {langs[0]['label']}" if langs else "Languages"),
                      "subtitle": subtitle(p, src), "rows": langs},
        "quotes": quotes, "care": care,
        "who_is_missing": who_is_missing(ws, p),
    }


def who_is_missing(ws: str, p: Period) -> dict:
    """Compare who gives feedback with who buys, so decisions do not follow only the loudest voices."""
    a12 = p.end.replace(year=p.end.year - 1)
    groups = []
    # product line
    buy = db.rows("""SELECT line g, sum(quantity) n FROM order_items WHERE ws = ? AND date BETWEEN ? AND ? AND line IS NOT NULL GROUP BY 1""",
                  [ws, a12, p.end])
    fb = db.rows("""SELECT line g, count(*) n FROM feedback WHERE ws = ? AND date BETWEEN ? AND ? AND line IS NOT NULL GROUP BY 1""",
                 [ws, a12, p.end])
    groups += _compare("Product line", buy, fb, {"women": "Women's line", "children": "Children's line"}, "units bought", "feedback items")
    # language
    buy = db.rows("""SELECT c.language g, count(*) n FROM orders o JOIN customers c ON c.ws = o.ws AND c.customer_id = o.customer_id
        WHERE o.ws = ? AND o.date BETWEEN ? AND ? AND c.language IS NOT NULL GROUP BY 1""", [ws, a12, p.end])
    fb = db.rows("""SELECT language g, count(*) n FROM feedback WHERE ws = ? AND date BETWEEN ? AND ? AND language <> 'unknown' GROUP BY 1""",
                 [ws, a12, p.end])
    groups += _compare("Language", buy, fb, LANG_NAMES, "orders", "feedback items")
    # channel
    buy = db.rows("""SELECT channel g, count(*) n FROM orders WHERE ws = ? AND date BETWEEN ? AND ? AND channel IS NOT NULL GROUP BY 1""",
                  [ws, a12, p.end])
    fb_ch = db.rows("""SELECT CASE WHEN o.channel IS NULL THEN NULL ELSE o.channel END g, count(*) n FROM feedback f
        JOIN (SELECT DISTINCT customer_id, first(channel) channel FROM orders WHERE ws = ? GROUP BY 1) o USING (customer_id)
        WHERE f.ws = ? AND f.date BETWEEN ? AND ? GROUP BY 1""", [ws, ws, a12, p.end])
    if sum(r["n"] for r in fb_ch) >= 30:
        groups += _compare("Sales channel", buy, fb_ch, {}, "orders", "reviews from these buyers")
    flagged = [g for g in groups if g["flag"]]
    title = "Feedback represents your buyers well" if groups and not flagged else "Not enough data to compare yet"
    if flagged:
        f = flagged[0]
        title = f"{f['label']} buyers are under-represented in feedback ({f['feedback_share'] * 100:.0f}% of feedback vs {f['buyer_share'] * 100:.0f}% of sales)"
    return {"title": title, "subtitle": "Last 12 months · Orders compared with reviews, surveys and messages", "groups": groups,
            "flagged": flagged}


def _compare(dimension, buy, fb, labels, buy_unit, fb_unit):
    bt, ft = sum(r["n"] or 0 for r in buy), sum(r["n"] or 0 for r in fb)
    if bt < 50 or ft < 20:
        return []
    fmap = {r["g"]: r["n"] for r in fb}
    out = []
    for r in buy:
        bs = (r["n"] or 0) / bt
        fs = fmap.get(r["g"], 0) / ft
        ratio = fs / bs if bs else None
        out.append({"dimension": dimension, "group": r["g"], "label": labels.get(r["g"], r["g"]), "buyer_share": round(bs, 3),
                    "feedback_share": round(fs, 3), "ratio": round(ratio, 2) if ratio is not None else None,
                    "flag": bool(bs >= 0.05 and ratio is not None and ratio < 0.6), "buy_unit": buy_unit, "fb_unit": fb_unit})
    return sorted(out, key=lambda x: -x["buyer_share"])
