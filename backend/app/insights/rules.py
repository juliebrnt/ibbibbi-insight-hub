"""Insight engine: deterministic rules that turn analytics into ranked, evidence-backed recommendations.

Each rule has a minimum sample and an effect-size threshold. If a rule cannot run,
it says what data it is waiting for instead of guessing.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import timedelta

from .. import db
from ..analytics import cross, feedback, metrics, sales, social
from ..analytics.common import Period, eur, has, pct_change
from ..analytics.text import THEMES

GOALS = ["Feedback", "Marketing", "Product", "Efficiency", "Market growth"]


@dataclass
class Insight:
    id: str
    title: str
    finding: str
    why_it_matters: str
    recommended_action: str
    expected_impact: str
    effort: str  # Low / Medium / High
    confidence: float  # 0..1
    linked_goal: str
    impact: int  # 1..3
    evidence: list[dict] = field(default_factory=list)
    metric: str | None = None
    page: str = "/"
    kind: str = "opportunity"  # opportunity | risk | care | win
    score: float = 0.0
    ai_written: bool = False


@dataclass
class Waiting:
    id: str
    message: str
    upload: str


def ev(label: str, value, period: str, source: str, dataset: str | None = None) -> dict:
    return {"label": label, "value": value, "period": period, "source": source, "dataset": dataset}


# --------------------------------------------------------------------------------------
# Guardrails on recommendations
# --------------------------------------------------------------------------------------
BANNED = [
    r"target\w*\b.{0,40}\b(patient|treatment|chemo|diagnos|stage|illness|sick|health status)",
    r"segment\w*\b.{0,40}\b(treatment|chemo|diagnos|stage|health)",
    r"(infer|predict|estimate|guess)\w*\b.{0,30}\b(treatment|diagnos|stage|health|illness)",
    r"(use|share|feature|post)\w*\b.{0,30}\b(her|their|customer'?s?) (personal )?(story|stories|photo)\b(?!.{0,40}consent)",
]


def passes_guardrails(text: str) -> bool:
    t = text.lower()
    return not any(re.search(p, t) for p in BANNED)


# --------------------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------------------
def r_reels(ws, p, ctx):
    so = ctx["social"]
    if so.get("empty"):
        return Waiting("reels", "Upload your Instagram posts export to see which formats work best.", "Instagram")
    fmt = {r["format"]: r for r in so["formats"]["rows"]}
    reel, static = fmt.get("Reel"), fmt.get("Static image")
    if not reel or not static or reel["posts"] < 4 or static["posts"] < 4 or not static["saves"]:
        return Waiting("reels", "Not enough Reels and static posts yet to compare them fairly (4 of each needed).", "Instagram")
    ratio = reel["saves"] / static["saves"]
    if ratio < 1.3:
        return None
    reach_ratio = (reel["reach"] or 0) / max(static["reach"] or 1, 1)
    return Insight(
        "reels", f"Reels earn {ratio:.1f}x the saves of static posts",
        f"Over the last six months, Reels averaged {reel['saves']:.0f} saves and {reel['reach']:,.0f} reach per post, against "
        f"{static['saves']:.0f} saves and {static['reach']:,.0f} reach for static images.",
        "Saves are the strongest signal that content is useful enough to come back to, and they push posts to new people.",
        "Turn your two best static posts of the month into short Reels (15 to 30 seconds), for example a scarf-tying tutorial.",
        f"Around {ratio:.1f}x more saves per post on the content you move to Reels", "Medium", min(0.95, 0.5 + 0.05 * min(reel["posts"], static["posts"])),
        "Marketing", 3 if ratio >= 1.8 else 2,
        [ev("Saves per Reel", round(reel["saves"], 1), "Last 6 months", "Instagram posts"),
         ev("Saves per static post", round(static["saves"], 1), "Last 6 months", "Instagram posts"),
         ev("Reels posted", reel["posts"], "Last 6 months", "Instagram posts"),
         ev("Reach ratio (Reel vs static)", round(reach_ratio, 1), "Last 6 months", "Instagram posts")],
        "ig_saves", "/social", "opportunity")


def r_mission(ws, p, ctx):
    so = ctx["social"]
    if so.get("empty"):
        return None
    rows = so["pillars"]["rows"]
    m = next((r for r in rows if r["pillar"] == "mission"), None)
    others = [r for r in rows if r["pillar"] != "mission"]
    if not m or m["posts"] < 4 or not others:
        return Waiting("mission", "Post at least four mission or community posts to measure how they perform.", "Instagram")
    o_saves = sum(r["saves"] * r["posts"] for r in others) / max(1, sum(r["posts"] for r in others))
    o_shares = sum(r["shares"] * r["posts"] for r in others) / max(1, sum(r["posts"] for r in others))
    ratio = m["saves"] / o_saves if o_saves else None
    if not ratio or ratio < 1.3:
        return None
    share = so["kpis"]["mission_share"]["value"] or 0
    return Insight(
        "mission", f"Mission and community posts earn {ratio:.1f}x the saves of other posts",
        f"Mission-led posts averaged {m['saves']:.0f} saves and {m['shares']:.0f} shares, against {o_saves:.0f} saves and "
        f"{o_shares:.0f} shares for other posts. Only {share * 100:.0f}% of recent posts are mission-led.",
        "Your vision is to normalise oncology headwear. This content does that and is also what your audience values most.",
        "Make one in three posts mission-led: community voices (only with written consent), myth-busting and everyday style. "
        "Keep selling posts separate from care posts.",
        "More saves and shares, which grow reach without paid ads", "Low", min(0.9, 0.5 + 0.04 * m["posts"]), "Marketing", 3,
        [ev("Saves per mission post", round(m["saves"], 1), "Last 6 months", "Instagram posts"),
         ev("Saves per other post", round(o_saves, 1), "Last 6 months", "Instagram posts"),
         ev("Mission share of posts", round(share * 100), p.label, "Instagram posts")],
        "ig_saves", "/social", "opportunity")


def r_consistency(ws, p, ctx):
    so = ctx["social"]
    if so.get("empty"):
        return None
    ch = so["consistency"].get("change")
    if ch and ch["after_reach"] and ch["before_reach"] and ch["after_reach"] > ch["before_reach"] * 1.1:
        lift = pct_change(ch["after_reach"], ch["before_reach"])
        return Insight(
            "consistency_win", f"Posting regularly lifted reach by {lift:.0f}%",
            f"Since the week of {ch['switch_week']} you have posted {ch['after_per_week']} times a week (before: {ch['before_per_week']}). "
            f"Average reach per post rose from {ch['before_reach']:,.0f} to {ch['after_reach']:,.0f}.",
            "Consistency is the cheapest growth lever you have. Algorithms and people both reward a reliable rhythm.",
            "Protect the rhythm: batch-create two weeks of posts in one session and schedule them, so busy weeks do not break the streak.",
            "Keeps reach growing; avoids losing the gains", "Low", 0.75, "Efficiency", 2,
            [ev("Posts per week before", ch["before_per_week"], f"{ch['weeks_before']} weeks", "Instagram posts"),
             ev("Posts per week after", ch["after_per_week"], f"{ch['weeks_after']} weeks", "Instagram posts"),
             ev("Reach per post before", round(ch["before_reach"]), "Before", "Instagram posts"),
             ev("Reach per post after", round(ch["after_reach"]), "After", "Instagram posts")],
            "consistency", "/social", "win")
    score = so["kpis"]["consistency"]["value"]
    if score is not None and score < 50:
        c = so["consistency"]
        return Insight(
            "consistency_low", f"Posting is irregular (consistency {score} out of 100)",
            f"You posted {c['per_week']} times a week with a longest gap of {c['longest_gap']} days.",
            "Long gaps reset momentum and make the brand feel inactive to new visitors.",
            "Set a simple rhythm of three posts a week (Monday, Wednesday, Friday) and batch-create them once a fortnight.",
            "Steadier reach and follower growth", "Low", 0.7, "Efficiency", 2,
            [ev("Consistency score", score, p.label, "Instagram posts"), ev("Longest gap (days)", c["longest_gap"], p.label, "Instagram posts")],
            "consistency", "/social", "risk")
    return None


def r_colours(ws, p, ctx):
    fb = ctx["feedback"]
    if fb.get("empty"):
        return Waiting("colours", "Upload reviews or survey answers to learn what customers want changed.", "Feedback")
    det = fb["nps"]["detractor_reasons"]
    design = next((t for t in fb["themes"]["rows"] if t["theme"] == "design"), None)
    req = db.one("""SELECT count(*) FROM social_comments WHERE ws = ? AND category = 'request' AND date >= ?""",
                 [ws, p.end - timedelta(days=365)]) or 0
    det_design = next((t for t in det if t["theme"] == "design"), None)
    det_total = fb["nps"]["summary"].get("n", 0) * (fb["nps"]["summary"].get("detractors") or 0)
    if not (det_design and det_design["n"] >= 5) and req < 10:
        return None
    share = (det_design["n"] / det_total) if det_design and det_total else None
    finding = []
    if det_design:
        finding.append(f"{det_design['n']} of about {det_total:.0f} detractors in the last 12 months mention colour or design range")
    if req:
        finding.append(f"{req} Instagram comments asked for new colours or prints")
    return Insight(
        "colours", "Customers are asking for a wider colour range",
        ". ".join(finding) + ".",
        "Limited choice is the main reason people would not recommend you, and it is easy to test before investing in stock.",
        "Run a two-option colour poll in Stories, then pre-order the winning colour in a small batch before committing to full production.",
        "Fewer detractors and a reason for past customers to buy again", "Medium", 0.8 if det_design and det_design["n"] >= 8 else 0.6,
        "Product", 3,
        [ev("Detractors mentioning colour", det_design["n"] if det_design else 0, "Last 12 months", "Survey responses"),
         ev("Share of detractors", round(share * 100) if share else None, "Last 12 months", "Survey responses"),
         ev("Colour requests in comments", req, "Last 12 months", "Instagram comments"),
         ev("Negative share of design feedback", round((design or {}).get("neg_share", 0) * 100), p.label, "All feedback")],
        "nps", "/feedback", "opportunity")


def r_shipping(ws, p, ctx):
    fb = ctx["feedback"]
    if fb.get("empty"):
        return None
    a = p.end - timedelta(days=364)
    rows = {r["theme"]: r for r in feedback.theme_table(ws, a, p.end)}
    s = rows.get("shipping")
    if not s or s["n"] < 5 or s["neg_share"] < 0.5:
        return None
    return Insight(
        "shipping", "Shipping delays are a recurring complaint",
        f"{s['n']} pieces of feedback in the last 12 months mention delivery and {s['neg_share'] * 100:.0f}% of them are negative.",
        "Many customers buy close to a treatment date; a late parcel matters more here than in most shops.",
        "Show a clear delivery date on the product page and offer an express option. Check the courier's late-delivery rate this month.",
        "Fewer one-star reviews and support messages", "Low", 0.7, "Feedback", 2,
        [ev("Shipping mentions", s["n"], "Last 12 months", "Reviews, surveys and messages"),
         ev("Negative share", round(s["neg_share"] * 100), "Last 12 months", "Reviews, surveys and messages")],
        "avg_rating", "/feedback", "risk")


def r_bamboo(ws, p, ctx):
    a = p.end - timedelta(days=364)
    rows = db.rows("""SELECT fabric, avg(rating) avg, count(*) n FROM feedback WHERE ws = ? AND rating IS NOT NULL AND fabric IS NOT NULL
        AND date BETWEEN ? AND ? GROUP BY 1 HAVING count(*) >= 10 ORDER BY avg DESC""", [ws, a, p.end])
    if len(rows) < 2:
        return Waiting("fabric", "Upload product reviews to compare fabrics (10 reviews per fabric needed).", "Reviews")
    best, rest = rows[0], rows[1:]
    rest_avg = sum(r["avg"] * r["n"] for r in rest) / sum(r["n"] for r in rest)
    if best["avg"] - rest_avg < 0.2:
        return None
    units = {r["fabric"]: r["units"] for r in ctx["sales"].get("fabric", {}).get("rows", [])} if not ctx["sales"].get("empty") else {}
    return Insight(
        "fabric", f"{best['fabric'].title()} is your best-loved fabric ({best['avg']:.1f} out of 5)",
        f"{best['fabric'].title()} products average {best['avg']:.1f} stars from {best['n']} reviews, against {rest_avg:.1f} for other fabrics. "
        "Reviewers mention softness and comfort most.",
        "Leading with what people already love is the lowest-risk way to grow.",
        f"Lead product pages, ads and the 'first purchase' email with {best['fabric']}; test new colours in {best['fabric']} first.",
        "Higher conversion on your hero products", "Low", min(0.9, 0.5 + best["n"] / 200), "Product", 2,
        [ev(f"{best['fabric'].title()} rating", round(best["avg"], 2), "Last 12 months", "Product reviews"),
         ev("Other fabrics rating", round(rest_avg, 2), "Last 12 months", "Product reviews"),
         ev(f"{best['fabric'].title()} reviews", best["n"], "Last 12 months", "Product reviews"),
         ev(f"{best['fabric'].title()} units sold", units.get(best["fabric"]), p.label, "Shopify orders")],
        "avg_rating", "/feedback", "win")


def r_missing(ws, p, ctx):
    fb = ctx["feedback"]
    if fb.get("empty"):
        return None
    flagged = fb["who_is_missing"]["flagged"]
    if not flagged:
        return None
    f = flagged[0]
    return Insight(
        "missing_" + str(f["group"]), f"We hear too little from {f['label'].lower()} customers",
        f"{f['label']} is {f['buyer_share'] * 100:.0f}% of what you sell but only {f['feedback_share'] * 100:.0f}% of the feedback you receive.",
        "Decisions based on the loudest or most digital customers can miss real needs. Parents buying for children rarely leave reviews.",
        f"Ask {f['label'].lower()} customers directly: a two-question card in the parcel with a QR code to your feedback form, "
        "worded for parents and carers.",
        "Balanced evidence before product decisions", "Low", 0.75, "Feedback", 2,
        [ev("Share of sales", round(f["buyer_share"] * 100), "Last 12 months", "Shopify orders"),
         ev("Share of feedback", round(f["feedback_share"] * 100), "Last 12 months", "Reviews, surveys and messages")],
        "positive_share", "/feedback", "risk")


def r_repeat(ws, p, ctx):
    s = ctx["sales"]
    if s.get("empty"):
        return Waiting("repeat", "Upload your Shopify orders export to see repeat purchasing.", "Shopify")
    rr = s["kpis"]["repeat_rate"]["value"]
    n = db.one("SELECT count(DISTINCT customer_id) FROM orders WHERE ws = ?", [ws])
    if rr is None or n < 100:
        return Waiting("repeat", "Repeat purchasing needs at least 100 customers in your orders data.", "Shopify")
    one = 1 - rr
    if one < 0.5:
        return None
    return Insight(
        "repeat", f"{one * 100:.0f}% of customers have bought only once",
        f"Of {n:,} customers, {rr * 100:.0f}% have ordered two or more times.",
        "A second purchase is far cheaper to win than a new customer, and many customers need more than one piece.",
        "Send a warm, care-first email 30 days after purchase (how to wash, how to style, a new colour) to everyone, "
        "never based on assumptions about anyone's health.",
        "A few points more repeat purchases lifts revenue without ad spend", "Low", 0.8, "Market growth", 2,
        [ev("Repeat purchase rate", round(rr * 100, 1), "All time", "Shopify orders"), ev("Customers", n, "All time", "Shopify orders")],
        "repeat_rate", "/sales", "opportunity")


def r_october(ws, p, ctx):
    s = ctx["sales"]
    if s.get("empty"):
        return None
    rows = s["seasonality"]["rows"]
    if len(rows) < 10:
        return None
    avg = sum(r["orders"] for r in rows) / len(rows)
    octo = next((r for r in rows if r["m"] == 10), None)
    if not octo or octo["orders"] < avg * 1.3:
        return None
    days_to = (p.end.replace(month=10, day=1) - p.end).days
    if days_to < 0:
        days_to = (p.end.replace(year=p.end.year + 1, month=10, day=1) - p.end).days
    return Insight(
        "october", f"October brings {octo['orders'] / avg:.1f}x your usual orders",
        f"In October you average {octo['orders']:.0f} orders against a monthly average of {avg:.0f}. The next October starts in {days_to} days.",
        "Awareness month brings attention and demand. Stock-outs or rushed content waste it.",
        "Plan October in August: stock bestsellers, line up a partner association and prepare community content in advance.",
        "Capture the peak without stock-outs", "Medium", 0.85, "Market growth", 2 if days_to > 120 else 3,
        [ev("October orders (average)", round(octo["orders"]), "All years", "Shopify orders"),
         ev("Average month", round(avg), "All years", "Shopify orders"), ev("Days until October", days_to, "Today", "Calendar")],
        "orders", "/sales", "opportunity")


def r_partnerships(ws, p, ctx):
    n = db.one("""SELECT count(*) FROM social_comments WHERE ws = ? AND category = 'partnership' AND NOT coalesce(replied, false)""", [ws]) or 0
    if n < 3:
        return None
    total = db.one("SELECT count(*) FROM social_comments WHERE ws = ? AND category = 'partnership'", [ws])
    return Insight(
        "partnerships", f"{n} partnership enquiries are waiting for a reply",
        f"{total} comments came from associations, pharmacies or hospital staff asking to collaborate; {n} have no reply yet.",
        "Pharmacies and patient associations are a route to people who never search for you online.",
        "Reply to each one this week with a short partnership one-pager; pick two pharmacies for a three-month trial.",
        "New sales channel and community reach", "Low", 0.85, "Market growth", 3,
        [ev("Unanswered partnership enquiries", n, "All time", "Instagram comments"),
         ev("All partnership enquiries", total, "All time", "Instagram comments")],
        "comments_answered", "/social", "opportunity")


def r_sizing(ws, p, ctx):
    n = db.one("SELECT count(*) FROM social_comments WHERE ws = ? AND category = 'sizing' AND date >= ?", [ws, p.end - timedelta(days=364)]) or 0
    fit = db.one("""SELECT count(*) FROM feedback WHERE ws = ? AND themes LIKE '%fit%' AND sentiment = 'negative' AND date >= ?""",
                 [ws, p.end - timedelta(days=364)]) or 0
    if n + fit < 10:
        return None
    return Insight(
        "sizing", "People are unsure about sizing",
        f"{n} comments asked about sizes and {fit} pieces of feedback describe fit problems in the last 12 months.",
        "Uncertainty about fit stops people buying online, especially for children.",
        "Add a simple size guide with head measurements (adults and children) to every product page and pin a Story highlight.",
        "Higher conversion and fewer returns", "Low", 0.8, "Product", 2,
        [ev("Sizing questions in comments", n, "Last 12 months", "Instagram comments"),
         ev("Negative fit feedback", fit, "Last 12 months", "Reviews, surveys and messages")],
        "conversion", "/feedback", "opportunity")


def r_mobile(ws, p, ctx):
    w = ctx["web"]
    if w.get("empty"):
        return Waiting("web", "Upload a Google Analytics traffic export to see how visitors shop.", "Google Analytics")
    dev = {d["device"]: d for d in w["devices"]["rows"]}
    m, d = dev.get("mobile"), dev.get("desktop")
    if not m or not d or not m["conv_rate"] or not d["conv_rate"] or m["sessions"] < 500:
        return None
    gap = d["conv_rate"] / m["conv_rate"]
    share = m["sessions"] / sum(x["sessions"] for x in w["devices"]["rows"])
    if gap < 1.3 or share < 0.5:
        return None
    return Insight(
        "mobile", f"Phones bring {share * 100:.0f}% of visits but convert {gap:.1f}x less",
        f"Mobile visitors convert at {m['conv_rate'] * 100:.1f}% against {d['conv_rate'] * 100:.1f}% on desktop.",
        "Most of your audience arrives from Instagram on a phone, so small fixes to the mobile shop pay back quickly.",
        "Test checkout on your own phone; enable Shop Pay or Apple Pay and shorten product pages on mobile.",
        f"Closing half the gap would add roughly {((d['conv_rate'] - m['conv_rate']) / 2 * m['sessions']):.0f} purchases in this period",
        "Medium", 0.7, "Market growth", 2,
        [ev("Mobile conversion", round(m["conv_rate"] * 100, 2), p.label, "Google Analytics"),
         ev("Desktop conversion", round(d["conv_rate"] * 100, 2), p.label, "Google Analytics"),
         ev("Mobile share of visits", round(share * 100), p.label, "Google Analytics")],
        "conversion", "/sales", "opportunity")


def r_care(ws, p, ctx):
    fb = ctx["feedback"]
    n = len(fb.get("care", [])) if not fb.get("empty") else 0
    if not n:
        return None
    return Insight(
        "care", f"{n} messages may need a personal reply",
        "Some customers wrote about having a very hard time. These are flagged for care, not for marketing.",
        "Responding with warmth is part of the brand's mission. These words should never be used in campaigns.",
        "Reply personally and gently; where appropriate, share contacts for support associations. Do not quote these messages.",
        "Trust and care for people going through treatment", "Low", 0.9, "Feedback", 3,
        [ev("Messages flagged", n, "All time", "Feedback and comments")], None, "/feedback", "care")


def r_flex(ws, p, ctx):
    out = []
    for ds in db.rows("SELECT id, flex_config FROM datasets WHERE ws = ? AND flexible", [ws]):
        cfg = json.loads(ds["flex_config"] or "{}")
        t = cfg.get("trend")
        if not t:
            continue
        end = db.one(f'SELECT max(CAST("{t["date"]}" AS DATE)) FROM "{cfg["table"]}"')
        if not end:
            continue
        cur = metrics.value(ws, f"flex:{ds['id']}", end - timedelta(days=89), end)
        prev = metrics.value(ws, f"flex:{ds['id']}", end - timedelta(days=179), end - timedelta(days=90))
        ly = metrics.value(ws, f"flex:{ds['id']}", end - timedelta(days=89 + 365), end - timedelta(days=365))
        n = db.one(f'SELECT count(*) FROM "{cfg["table"]}" WHERE CAST("{t["date"]}" AS DATE) > ?', [end - timedelta(days=90)])
        if not cur or not prev or n < 4:
            continue
        ch = pct_change(cur, prev)
        if abs(ch) < 10:
            continue
        label = t.get("label") or cfg["title"]
        val_label = t.get("value_label", "total")
        is_money = "€" in (t.get("value_label") or "") or "caja" in val_label.lower() or "eur" in val_label.lower()
        fmtv = eur if is_money else (lambda v: f"{v:,.0f}")
        yoy = f" and {pct_change(cur, ly):+.0f}% on the same months last year" if ly else ""
        out.append(Insight(
            f"flex_{ds['id']}", f"{label}: {val_label.lower()} {'up' if ch > 0 else 'down'} {abs(ch):.0f}% in the last three months",
            f"{val_label} reached {fmtv(cur)} in the last 90 days, against {fmtv(prev)} in the 90 days before{yoy}.",
            "This comes from a file you added yourself, so it fills a gap the standard exports do not cover.",
            ("Keep a regular presence where it is growing, and bring QR cards to collect feedback in person." if ch > 0 else
             "Check whether fewer events, weather or stock explain the drop before deciding to cut back."),
            "Better decisions about offline channels", "Low", 0.6 if n < 8 else 0.7, "Market growth", 2,
            [ev(f"{val_label}, last 90 days", round(cur, 2), "Last 90 days", cfg["title"], ds["id"]),
             ev(f"{val_label}, previous 90 days", round(prev, 2), "Previous 90 days", cfg["title"], ds["id"]),
             ev("Records in the last 90 days", n, "Last 90 days", cfg["title"], ds["id"])],
            f"flex:{ds['id']}", "/data", "opportunity"))
    return out


def r_cross(ws, p, ctx):
    m = cross.mission_effect(ws)
    if not m.get("enough"):
        return Waiting("cross", "Linking content to visits needs 8 weeks of Instagram posts and website visits together. " + m.get("reason", ""), "Instagram and Google Analytics")
    corr = m["visits_lag0"]
    if corr is None or corr != corr or corr < 0.3:
        return None
    return Insight(
        "cross", "Weeks with mission posts bring more Instagram visitors to the shop",
        f"In weeks with at least one mission post, Instagram sent {m['ig_visits_with']:.0f} visits on average, against "
        f"{m['ig_visits_without']:.0f} in weeks without. Over {m['weeks']} weeks the correlation is {corr:.2f}. "
        "This is a correlation, not proof of cause.",
        "It suggests mission content does not only build the brand; it also brings people to the shop.",
        "Keep at least one mission post every week for the next eight weeks and check whether the pattern holds.",
        "More visits from Instagram", "Low", 0.55 if corr < 0.5 else 0.65, "Marketing", 2,
        [ev("Instagram visits, weeks with mission posts", m["ig_visits_with"], f"{m['weeks']} weeks", "Instagram and Google Analytics"),
         ev("Instagram visits, other weeks", m["ig_visits_without"], f"{m['weeks']} weeks", "Instagram and Google Analytics"),
         ev("Correlation", corr, f"{m['weeks']} weeks", "Instagram and Google Analytics")],
        "sessions", "/social", "opportunity")


def r_gift(ws, p, ctx):
    s = ctx["sales"]
    if s.get("empty"):
        return None
    g = s["kpis"]["gift_share"]["value"]
    if g is None or g < 0.2 or s["kpis"]["orders"]["value"] < 50:
        return None
    return Insight(
        "gift", f"{g * 100:.0f}% of orders are gifts",
        f"About {g * 100:.0f}% of orders in this period mention a gift in the order notes.",
        "Gift buyers are friends and family: a different audience with different questions.",
        "Add a gift option (wrapping, a note card, a gift card) and a short 'choosing a gift' guide.",
        "Higher order value and a new audience", "Low", 0.65, "Market growth", 2,
        [ev("Gift share of orders", round(g * 100), p.label, "Shopify orders")], "aov", "/sales", "opportunity")


def r_sales_change(ws, p, ctx):
    s = ctx["sales"]
    if s.get("empty"):
        return None
    k = s["kpis"]["revenue"]
    ch = k["change"]
    if ch is None or abs(ch) < 10 or (k["prev"] or 0) < 500:
        return None
    up = ch > 0
    return Insight(
        "sales_change", f"Revenue {'up' if up else 'down'} {abs(ch):.0f}% on the previous period",
        f"{eur(k['value'])} in {p.label.lower()}, against {eur(k['prev'])} in the period before.",
        "Knowing whether a change is seasonal or caused by something you did helps you repeat or fix it.",
        "Open Sales to see which products and channels moved, then note what you changed in the Plan's learning log.",
        "Clarity on what is driving sales", "Low", 0.7, "Market growth", 1,
        [ev("Revenue this period", round(k["value"], 2), p.label, "Shopify orders"), ev("Revenue previous period", round(k["prev"], 2), "Previous period", "Shopify orders")],
        "revenue", "/sales", "win" if up else "risk")


RULES = [r_care, r_reels, r_mission, r_consistency, r_colours, r_shipping, r_bamboo, r_missing, r_repeat, r_october, r_partnerships,
         r_sizing, r_mobile, r_flex, r_cross, r_gift, r_sales_change]


def context(ws: str, p: Period) -> dict:
    return {"sales": sales.overview(ws, p), "feedback": feedback.overview(ws, p), "social": social.overview(ws, p), "web": sales.web(ws, p)}


def priorities(ws: str) -> dict:
    pr = db.get_setting(f"priorities:{ws}", None) or {g: 1.0 for g in GOALS}
    return pr


def run(ws: str, p: Period, ctx: dict | None = None) -> dict:
    ctx = ctx or context(ws, p)
    insights: list[Insight] = []
    waiting: list[Waiting] = []
    for rule in RULES:
        try:
            res = rule(ws, p, ctx)
        except Exception as e:  # noqa: BLE001  (a broken rule should never break the page)
            print(f"rule {rule.__name__} failed: {e}")
            continue
        for r in (res if isinstance(res, list) else [res]):
            if isinstance(r, Insight):
                if passes_guardrails(r.recommended_action):
                    insights.append(r)
            elif isinstance(r, Waiting):
                waiting.append(r)
    pr = priorities(ws)
    goal_metrics = {g["metric"] for g in db.rows("SELECT metric FROM goals WHERE ws = ?", [ws])}
    for i in insights:
        boost = 1.3 if i.metric and i.metric in goal_metrics else 1.0
        care = 1.5 if i.kind == "care" else 1.0
        i.score = round(i.impact * i.confidence * pr.get(i.linked_goal, 1.0) * boost * care, 3)
    insights.sort(key=lambda i: -i.score)
    return {"insights": [asdict(i) for i in insights], "waiting": [asdict(w) for w in waiting]}


def what_changed(ws: str, p: Period) -> list[dict]:
    out = []
    for key in ("revenue", "orders", "aov", "avg_rating", "ig_saves", "sessions", "conversion", "positive_share"):
        cur = metrics.value(ws, key, p.start, p.end)
        prev = metrics.value(ws, key, p.prev_start, p.prev_end)
        if cur is None or prev in (None, 0):
            continue
        ch = pct_change(cur, prev)
        if ch is None or abs(ch) < 3:
            continue
        good = (ch > 0) == metrics.METRICS[key]["higher_is_better"]
        out.append({"metric": key, "label": metrics.METRICS[key]["label"], "value": cur, "prev": prev, "change": ch,
                    "display": metrics.fmt(key, cur), "prev_display": metrics.fmt(key, prev), "good": good})
    out.sort(key=lambda r: -abs(r["change"]))
    return out[:6]


__all__ = ["run", "what_changed", "passes_guardrails", "THEMES", "has"]
