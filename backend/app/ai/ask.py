"""Ask: plain-language questions answered only from the data.

Without an AI key a keyword router picks one of a small set of safe analytics functions.
With a key, the model chooses a function or writes a read-only SELECT that is validated
(SELECT only, whitelisted tables, row limit) before it runs.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta

from .. import db
from ..analytics import feedback as fb
from ..analytics.common import latest_date
from ..analytics.text import THEMES
from ..ingest.parsing import norm
from ..privacy.pii import scrub
from . import client, guard

MONTHS = {"january": 1, "enero": 1, "gener": 1, "february": 2, "febrero": 2, "febrer": 2, "march": 3, "marzo": 3, "marc": 3,
          "april": 4, "abril": 4, "may": 5, "mayo": 5, "maig": 5, "june": 6, "junio": 6, "juny": 6, "july": 7, "julio": 7, "juliol": 7,
          "august": 8, "agosto": 8, "agost": 8, "september": 9, "septiembre": 9, "setembre": 9, "october": 10, "octubre": 10,
          "november": 11, "noviembre": 11, "novembre": 11, "december": 12, "diciembre": 12, "desembre": 12}
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _ans(answer, chart=None, table=None, method="", sources=None, ok=True, followups=None):
    return {"answer": answer, "chart": chart, "table": table, "method": method, "sources": sources or [], "ok": ok,
            "followups": followups or []}


def _none(what: str, upload: str):
    return _ans(f"I cannot answer that from your data yet because there is no {what}. Upload {upload} and ask again.", ok=False,
                method="Checked which datasets are loaded.")


# --------------------------------------------------------------------------------------
# Safe analytics functions
# --------------------------------------------------------------------------------------
def best_reviewed_products(ws, q=""):
    rows = db.rows("""SELECT regexp_replace(product, ' - .*$', '') product, round(avg(rating), 2) avg_rating, count(*) reviews
        FROM feedback WHERE ws = ? AND rating IS NOT NULL AND product IS NOT NULL GROUP BY 1 HAVING count(*) >= 3
        ORDER BY avg_rating DESC, reviews DESC LIMIT 10""", [ws])
    if not rows:
        return _none("product review", "your reviews export (for example from Judge.me or Shopify)")
    top = rows[0]
    worst = rows[-1]
    return _ans(f"{top['product']} gets the best reviews: {top['avg_rating']:.2f} out of 5 from {top['reviews']} reviews. "
                f"At the other end, {worst['product']} averages {worst['avg_rating']:.2f}. Only products with 3 or more reviews are compared.",
                {"type": "bar", "x": "product", "y": "avg_rating", "rows": rows, "label": "Average rating"}, rows,
                "Average star rating per product across all reviews, products with at least 3 reviews.", ["Product reviews"],
                ["What do people complain about?", "Which fabric is best rated?"])


def best_time_to_post(ws, q=""):
    rows = db.rows("""SELECT isodow(date) dow, count(*) posts,
        round(avg((coalesce(likes,0)+coalesce(comments,0)+coalesce(saves,0)+coalesce(shares,0))/nullif(reach,0))*100, 2) er
        FROM social_posts WHERE ws = ? AND platform = 'Instagram' GROUP BY 1 ORDER BY 1""", [ws])
    if not rows:
        return _none("Instagram post data", "your Instagram posts export")
    for r in rows:
        r["day"] = DAYS[r["dow"] - 1]
    hours = db.rows("""SELECT CAST(hour(ts)/3 AS INT)*3 h, count(*) posts,
        round(avg((coalesce(likes,0)+coalesce(comments,0)+coalesce(saves,0)+coalesce(shares,0))/nullif(reach,0))*100, 2) er
        FROM social_posts WHERE ws = ? AND platform = 'Instagram' GROUP BY 1 HAVING count(*) >= 3 ORDER BY er DESC""", [ws])
    eligible = [r for r in rows if r["posts"] >= 3] or rows
    best = max(eligible, key=lambda r: r["er"] or 0)
    h = f" Posts between {hours[0]['h']:02d}:00 and {hours[0]['h'] + 3:02d}:00 do best ({hours[0]['er']:.2f}%)." if hours else ""
    return _ans(f"{best['day']} is your best day: posts get a {best['er']:.2f}% engagement rate on average across {best['posts']} posts.{h} "
                "Days with fewer than 3 posts are not compared.",
                {"type": "bar", "x": "day", "y": "er", "rows": [{"day": r["day"], "er": r["er"]} for r in rows], "label": "Engagement rate (%)"},
                rows, "Average engagement rate ((likes + comments + saves + shares) / reach) by weekday and three-hour block.",
                ["Instagram posts"], ["Which format works best?", "Does mission content work?"])


def best_format(ws, q=""):
    rows = db.rows("""SELECT format, count(*) posts, round(avg(saves), 1) saves, round(avg(reach)) reach, round(avg(shares), 1) shares
        FROM social_posts WHERE ws = ? AND platform = 'Instagram' GROUP BY 1 ORDER BY saves DESC""", [ws])
    if not rows:
        return _none("Instagram post data", "your Instagram posts export")
    b = rows[0]
    return _ans(f"{b['format']} posts work best: {b['saves']:.1f} saves and {b['reach']:,.0f} reach per post on average ({b['posts']} posts).",
                {"type": "bar", "x": "format", "y": "saves", "rows": rows, "label": "Saves per post"}, rows,
                "Average saves, reach and shares per post by format, all Instagram posts.", ["Instagram posts"], ["When should we post?"])


def mission_content(ws, q=""):
    rows = db.rows("""SELECT pillar, count(*) posts, round(avg(saves), 1) saves, round(avg(shares), 1) shares FROM social_posts
        WHERE ws = ? GROUP BY 1 ORDER BY saves DESC""", [ws])
    if not rows:
        return _none("social post data", "your Instagram posts export")
    from ..analytics.text import PILLAR_LABELS
    for r in rows:
        r["topic"] = PILLAR_LABELS.get(r["pillar"], r["pillar"])
    m = next((r for r in rows if r["pillar"] == "mission"), None)
    txt = (f"Mission and community posts average {m['saves']:.1f} saves and {m['shares']:.1f} shares per post across {m['posts']} posts. "
           f"The best topic overall is {rows[0]['topic'].lower()}." if m else "There are no mission-led posts yet to compare.")
    return _ans(txt, {"type": "bar", "x": "topic", "y": "saves", "rows": rows, "label": "Saves per post"}, rows,
                "Captions are sorted into topics with keyword rules; averages per topic.", ["Instagram posts"])


def sales_change(ws, q=""):
    if not db.one("SELECT count(*) FROM orders WHERE ws = ?", [ws]):
        return _none("order data", "your Shopify orders export")
    qn = norm(q)
    month = next((v for k, v in MONTHS.items() if re.search(rf"\b{k}\b", qn)), None)
    end = latest_date(ws)
    if month:
        year = end.year if month <= end.month else end.year - 1
        m_start = date(year, month, 1)
    else:
        m_start = date(end.year, end.month, 1)
        if (end - m_start).days < 14:
            m_start = (m_start - timedelta(days=1)).replace(day=1)
    m_end = (m_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    p_end = m_start - timedelta(days=1)
    p_start = p_end.replace(day=1)

    def tot(a, b):
        return db.rows("SELECT count(*) orders, coalesce(sum(total),0) revenue, avg(total) aov FROM orders WHERE ws = ? AND date BETWEEN ? AND ?",
                       [ws, a, b])[0]
    cur, prev = tot(m_start, m_end), tot(p_start, p_end)
    if not prev["orders"]:
        return _ans(f"There are no orders in {MONTH_NAMES[p_start.month - 1]} to compare {MONTH_NAMES[month - 1] if month else 'this month'} against.", ok=False)
    by = db.rows("""SELECT coalesce(channel, 'Unknown') channel,
        sum(CASE WHEN date BETWEEN ? AND ? THEN total ELSE 0 END) cur, sum(CASE WHEN date BETWEEN ? AND ? THEN total ELSE 0 END) prev
        FROM orders WHERE ws = ? AND date BETWEEN ? AND ? GROUP BY 1""", [m_start, m_end, p_start, p_end, ws, p_start, m_end])
    for r in by:
        r["diff"] = round(r["cur"] - r["prev"], 2)
    by.sort(key=lambda r: r["diff"])
    ch = (cur["revenue"] - prev["revenue"]) / prev["revenue"] * 100
    name, pname = MONTH_NAMES[m_start.month - 1], MONTH_NAMES[p_start.month - 1]
    direction = "fell" if ch < 0 else "rose"
    biggest = by[0] if ch < 0 else by[-1]
    order_ch = (cur["orders"] - prev["orders"]) / prev["orders"] * 100
    aov_part = (f" Average order value moved from €{prev['aov']:.2f} to €{cur['aov']:.2f}." if prev["aov"] and cur["aov"] else "")
    seasonal = ""
    if m_start.month in (1, 8):
        seasonal = f" {name} is usually a quieter month in your history, so part of this is seasonal."
    if p_start.month == 10:
        seasonal = " The month before was October, your awareness-month peak, so a drop afterwards is expected."
    text = (f"Revenue {direction} {abs(ch):.0f}% in {name} {m_start.year} (€{cur['revenue']:,.0f}) compared with {pname} (€{prev['revenue']:,.0f}). "
            f"Orders changed by {order_ch:+.0f}% ({prev['orders']} to {cur['orders']}).{aov_part} "
            f"The biggest change came from {biggest['channel']} ({'+' if biggest['diff'] >= 0 else '-'}€{abs(biggest['diff']):,.0f}).{seasonal}")
    return _ans(text, {"type": "bar", "x": "channel", "y": "diff", "rows": by, "label": f"Change in revenue vs {pname} (€)"}, by,
                f"Compared total order value in {name} with {pname}, then broke the difference down by sales channel.", ["Shopify orders"],
                ["Which products sell best?", "When should we post?"])


def complaints(ws, q=""):
    rows = fb.theme_table(ws, date(2000, 1, 1), date(2100, 1, 1), "AND sentiment = 'negative'")
    if not rows:
        return _none("feedback", "reviews, survey answers or pasted messages")
    for r in rows:
        r["label"] = THEMES.get(r["theme"], {}).get("label", r["theme"])
    top = rows[0]
    ex = db.rows("""SELECT DISTINCT text FROM feedback WHERE ws = ? AND sentiment = 'negative' AND themes LIKE ? AND NOT distress LIMIT 2""",
                 [ws, f"%{top['theme']}%"])
    examples = " For example: " + " / ".join(f"\"{e['text'][:90]}\"" for e in ex) if ex else ""
    return _ans(f"The most common complaint is about {top['label'].lower()} ({top['n']} negative mentions)"
                + (f", followed by {rows[1]['label'].lower()} ({rows[1]['n']})." if len(rows) > 1 else ".") + examples,
                {"type": "bar", "x": "label", "y": "n", "rows": rows[:8], "label": "Negative mentions"}, rows[:8],
                "Counted themes in feedback marked negative by the sentiment rules (or a low rating).", ["Reviews, surveys and messages"],
                ["Who is missing from our feedback?", "What is our NPS?"])


def nps_summary(ws, q=""):
    end = latest_date(ws)
    n = fb.nps(ws, end - timedelta(days=364), end)
    if not n["n"]:
        return _none("NPS survey answers", "your survey responses (for example a Google Forms export)")
    det = fb.theme_table(ws, end - timedelta(days=364), end, "AND nps <= 6")
    reason = f" Detractors most often mention {THEMES.get(det[0]['theme'], {}).get('label', det[0]['theme']).lower()}." if det else ""
    rows = [{"group": "Promoters (9-10)", "share": round(n["promoters"] * 100)}, {"group": "Passives (7-8)", "share": round(n["passives"] * 100)},
            {"group": "Detractors (0-6)", "share": round(n["detractors"] * 100)}]
    return _ans(f"Your NPS over the last 12 months is {n['score']} from {n['n']} answers.{reason}",
                {"type": "bar", "x": "group", "y": "share", "rows": rows, "label": "Share of answers (%)"}, rows,
                "NPS = % promoters (9-10) minus % detractors (0-6), last 12 months.", ["Survey responses"])


def where_found(ws, q=""):
    rows = db.rows("""SELECT heard_from, count(*) answers FROM feedback WHERE ws = ? AND heard_from IS NOT NULL GROUP BY 1 ORDER BY answers DESC""", [ws])
    if not rows:
        web = db.rows("SELECT source, sum(sessions) visits FROM web_sessions WHERE ws = ? GROUP BY 1 ORDER BY visits DESC LIMIT 8", [ws])
        if not web:
            return _none("survey or website data", "a survey with 'How did you find us?' or a Google Analytics export")
        return _ans(f"Most website visitors come from {web[0]['source']} ({web[0]['visits']:,.0f} visits).",
                    {"type": "bar", "x": "source", "y": "visits", "rows": web, "label": "Visits"}, web, "Website sessions by source.", ["Google Analytics"])
    tot = sum(r["answers"] for r in rows)
    return _ans(f"{rows[0]['heard_from']} is the most common way customers found you ({rows[0]['answers'] / tot * 100:.0f}% of {tot} survey answers)"
                + (f", then {rows[1]['heard_from']} ({rows[1]['answers'] / tot * 100:.0f}%)." if len(rows) > 1 else "."),
                {"type": "bar", "x": "heard_from", "y": "answers", "rows": rows, "label": "Survey answers"}, rows,
                "Counted answers to 'How did you find us?' in your surveys.", ["Survey responses"])


def top_products(ws, q=""):
    rows = db.rows("""SELECT regexp_replace(product, ' - .*$', '') product, sum(quantity) units, round(sum(quantity*price)) revenue
        FROM order_items WHERE ws = ? GROUP BY 1 ORDER BY revenue DESC LIMIT 10""", [ws])
    if not rows:
        return _none("order line data", "your Shopify orders export")
    return _ans(f"{rows[0]['product']} is your best seller by revenue (€{rows[0]['revenue']:,.0f}, {rows[0]['units']:,.0f} units).",
                {"type": "bar", "x": "product", "y": "revenue", "rows": rows, "label": "Revenue (€)"}, rows,
                "Summed quantity times unit price per product, all orders.", ["Shopify orders"])


def repeat_customers(ws, q=""):
    rows = db.rows("""SELECT CASE WHEN n = 1 THEN 'One order' WHEN n <= 3 THEN '2 to 3 orders' ELSE '4 or more' END grp, count(*) customers
        FROM (SELECT customer_id, count(*) n FROM orders WHERE ws = ? AND customer_id IS NOT NULL GROUP BY 1) GROUP BY 1 ORDER BY 1""", [ws])
    if not rows:
        return _none("order data", "your Shopify orders export")
    tot = sum(r["customers"] for r in rows)
    order = {"One order": 0, "2 to 3 orders": 1, "4 or more": 2}
    rows.sort(key=lambda r: order[r["grp"]])
    rep = tot - rows[0]["customers"]
    return _ans(f"{rep / tot * 100:.0f}% of your {tot:,} customers have ordered more than once; "
                f"{rows[-1]['customers'] / tot * 100:.0f}% have ordered four or more times.",
                {"type": "bar", "x": "grp", "y": "customers", "rows": rows, "label": "Customers"}, rows,
                "Counted orders per anonymous customer id (hashed email).", ["Shopify orders"])


def missing_voices(ws, q=""):
    end = latest_date(ws)
    from ..analytics.common import period
    w = fb.who_is_missing(ws, period(ws, "365d"))
    if not w["groups"]:
        return _ans("There is not enough feedback and sales data yet to compare who is speaking with who is buying.", ok=False)
    rows = [{"group": g["label"], "share_of_sales": round(g["buyer_share"] * 100), "share_of_feedback": round(g["feedback_share"] * 100)} for g in w["groups"]]
    return _ans(w["title"] + ".", {"type": "bar", "x": "group", "y": "share_of_feedback", "rows": rows, "label": "Share of feedback (%)"}, rows,
                "Compared each group's share of sales with its share of feedback over the last 12 months.", ["Orders", "Feedback"])


FUNCTIONS = {
    "best_reviewed_products": (best_reviewed_products, "Which products get the best reviews", ["review", "rated", "rating", "estrellas", "valor"]),
    "best_time_to_post": (best_time_to_post, "When to post on Instagram", ["when", "post", "publicar", "time", "day", "cuando", "hora"]),
    "best_format": (best_format, "Which post format works best", ["format", "reel", "carousel", "static", "formato"]),
    "mission_content": (mission_content, "How mission content performs", ["mission", "community", "mision", "comunidad"]),
    "sales_change": (sales_change, "Why sales changed in a month", ["why", "dip", "drop", "fell", "change", "sales", "ventas", "bajaron", "revenue"]),
    "complaints": (complaints, "What customers complain about", ["complain", "complaint", "queja", "problem", "negative", "unhappy", "improve"]),
    "nps_summary": (nps_summary, "NPS and detractor reasons", ["nps", "recommend", "promoter", "detractor"]),
    "where_found": (where_found, "Where customers found the brand", ["found", "find", "hear", "discover", "conocieron", "where"]),
    "top_products": (top_products, "Best-selling products", ["best seller", "best-selling", "sell best", "top product", "sells", "popular"]),
    "repeat_customers": (repeat_customers, "How many customers buy again", ["repeat", "again", "loyal", "return", "vuelven"]),
    "missing_voices": (missing_voices, "Who is under-represented in feedback", ["missing", "represent", "who", "voice", "children"]),
}
SUGGESTED = ["Which products get the best reviews?", "When should we post?", "Why did sales dip in January?", "What do customers complain about?",
             "Where do customers find us?", "How many customers buy again?", "Which post format works best?", "Who is missing from our feedback?"]


def route(q: str) -> str | None:
    t = " " + norm(q) + " "
    scores = {}
    for name, (_f, _d, kws) in FUNCTIONS.items():
        s = sum(2 if " " in k else 1 for k in kws if k in t)
        if s:
            scores[name] = s
    if "who is missing" in t or "under represented" in t:
        return "missing_voices"
    if ("post" in t or "publicar" in t) and ("when" in t or "cuando" in t or "day" in t):
        return "best_time_to_post"
    return max(scores, key=scores.get) if scores else None


# --------------------------------------------------------------------------------------
# SQL validation (for AI-written queries)
# --------------------------------------------------------------------------------------
WHITELIST = {"orders", "order_items", "products", "customers", "feedback", "social_posts", "social_comments", "web_sessions", "email_campaigns"}
FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|create|alter|attach|detach|copy|pragma|install|load|export|import|call|set|grant|"
                       r"truncate|replace|vacuum|checkpoint|read_csv\w*|read_parquet|read_json\w*|glob|httpfs|system|getenv)\b", re.I)
SQL_KEYWORDS = {"where", "group", "order", "limit", "join", "left", "right", "inner", "outer", "full", "cross", "on", "using", "having",
                "union", "window", "qualify", "as", "natural", "and", "or", "select", "from", "with"}
MAX_ROWS = 200


class SQLRejected(ValueError):
    pass


def validate_sql(sql: str, ws: str) -> str:
    s = sql.strip().rstrip(";").strip()
    if ";" in s:
        raise SQLRejected("Only one statement is allowed.")
    if not re.match(r"^(select|with)\b", s, re.I):
        raise SQLRejected("Only SELECT queries are allowed.")
    if FORBIDDEN.search(s):
        raise SQLRejected("The query uses a command that is not allowed.")
    if re.search(r"--|/\*", s):
        raise SQLRejected("Comments are not allowed in queries.")
    ctes = {m.lower() for m in re.findall(r"(?:with|,)\s*([A-Za-z_]\w*)\s+as\s*\(", s, re.I)}
    refs = re.findall(r"\b(?:from|join)\s+([A-Za-z_][\w.\"]*)", s, re.I)
    for r in refs:
        name = r.strip('"').lower()
        if name in ctes:
            continue
        if name not in WHITELIST:
            raise SQLRejected(f"Table '{name}' is not available.")

    # scope every whitelisted table to the current workspace
    def repl(m):
        kw, name, nxt = m.group(1), m.group(2), m.group(3) or ""
        if name.lower() in ctes or name.lower() not in WHITELIST:
            return m.group(0)
        sub = f"(SELECT * EXCLUDE (ws, dataset_id, _key) FROM main.{name.lower()} WHERE ws = '{ws}')"
        alias_follows = nxt and nxt.strip().lower() not in SQL_KEYWORDS and re.match(r"\s+[A-Za-z_]", nxt)
        return f"{kw} {sub}" + (nxt if alias_follows else f" AS {name}{nxt}")
    s = re.sub(r"\b(from|join)\s+([A-Za-z_]\w*)(\s+\w+)?", repl, s, flags=re.I)
    if ws not in ("demo", "mine"):
        raise SQLRejected("Unknown workspace.")
    return f"SELECT * FROM ({s}) AS q LIMIT {MAX_ROWS}"


SCHEMA_DOC = """Tables (DuckDB SQL, read-only):
orders(order_id, ts, date, customer_id, subtotal, total, discount_code, discount, shipping, channel, is_gift, city, country, currency)
order_items(order_id, date, customer_id, product, sku, quantity, price, fabric[bamboo|cotton|silk], line[women|children], colour)
products(product, sku, price, type, fabric, line, colour, inventory)
customers(customer_id, city, country, language, orders_count, total_spent, accepts_marketing)
feedback(date, kind[review|survey|message], source, text, title, rating[1-5], nps[0-10], product, fabric, line, language, customer_id,
         heard_from, consent_quote, sentiment[positive|neutral|negative], sentiment_score, themes[comma list], distress)
social_posts(post_id, platform, ts, date, format[Reel|Carousel|Static image|Video], caption, pillar[mission|product|behind|education],
             reach, views, likes, comments, saves, shares, follows, hashtags, caption_length)
social_comments(platform, post_id, date, text, author_id, language, sentiment, category[partnership|request|sizing|question|praise|sensitive|other], replied, likes)
web_sessions(date, source, medium, landing_page, device, sessions, users, conversions, revenue)
email_campaigns(date, campaign, recipients, opens, clicks, orders, revenue)"""

ASK_SYSTEM = """You help the founders of iBBIBBI (oncology headwear brand, Spain) answer questions from their own data.
You never answer from general knowledge. Decide how to answer: either pick one function, or write one read-only DuckDB SELECT.
Functions: {functions}
{schema}
Return JSON: {{"function": "<name>"}} or {{"sql": "<SELECT ...>", "chart": {{"type": "bar|line", "x": "<col>", "y": "<col>"}}}}
or {{"cannot": "<what data would be needed>"}}. Never select free text of feedback marked distress. Never infer anyone's health status."""

ANSWER_SYSTEM = """Write a two or three sentence answer for the founders in British English, warm and plain. Use only numbers that
appear in the result rows. Never use em dashes. If the rows do not answer the question, say so."""


def ask(ws: str, question: str) -> dict:
    question = question.strip()[:500]
    if not question:
        return _ans("Ask me anything about your customers, content or sales.", ok=False)
    if client.enabled():
        res = _ask_ai(ws, question)
        if res:
            return res
    name = route(question)
    if not name:
        return _ans("I could not match that question to your data yet. Try one of the suggested questions, or turn on AI analysis "
                    "to ask in your own words.", ok=False, followups=SUGGESTED[:4])
    out = FUNCTIONS[name][0](ws, question)
    out["function"] = name
    out["ai_written"] = False
    return out


def _ask_ai(ws: str, question: str) -> dict | None:
    funcs = "; ".join(f"{k}: {v[1]}" for k, v in FUNCTIONS.items())
    plan = client.complete_json(ASK_SYSTEM.format(functions=funcs, schema=SCHEMA_DOC), scrub(question), max_tokens=1200)
    if not plan:
        return None
    if plan.get("cannot"):
        return _ans(f"Your data cannot answer that yet. {plan['cannot']}", ok=False, method="AI checked the available tables.",
                    followups=SUGGESTED[:3]) | {"ai_written": True}
    if plan.get("function") in FUNCTIONS:
        out = FUNCTIONS[plan["function"]][0](ws, question)
        out["function"] = plan["function"]
        out["method"] = "AI chose a built-in analysis. " + out["method"]
        return out
    if plan.get("sql"):
        try:
            safe = validate_sql(plan["sql"], ws)
            rows = db.rows(safe)
        except SQLRejected as e:
            return _ans(f"I tried a query that was not allowed ({e}). Try rephrasing.", ok=False)
        except Exception:  # noqa: BLE001
            return None
        rows = rows[:MAX_ROWS]
        facts = {"question": question, "rows": rows[:50]}
        text = client.complete(ANSWER_SYSTEM, json.dumps(facts, default=str, ensure_ascii=False), max_tokens=600)
        ok, bad = guard.check(text or "", facts)
        if not text or not ok:
            text = f"Here is what the data shows ({len(rows)} rows). I did not write a summary because it could not be checked against the numbers."
        ch = plan.get("chart") or {}
        chart = None
        if rows and ch.get("x") in rows[0] and ch.get("y") in rows[0]:
            chart = {"type": ch.get("type", "bar"), "x": ch["x"], "y": ch["y"], "rows": rows[:30], "label": ch["y"]}
        return {"answer": text, "chart": chart, "table": rows[:50], "method": "AI wrote this read-only query (checked before running):",
                "sql": plan["sql"], "sources": [], "ok": True, "followups": [], "ai_written": True}
    return None
