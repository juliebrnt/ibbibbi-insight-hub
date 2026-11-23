"""Turn a mapped raw table into canonical rows, with a validation report."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

import pandas as pd

from ..analytics import text as tx
from ..privacy.pii import hash_value, scrub_storage
from .parsing import date_series, norm, number_series, parse_bool


@dataclass
class Report:
    rows_in: int = 0
    imported: int = 0
    skipped: int = 0
    fixed: int = 0
    duplicates: int = 0
    notes: list[str] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)  # {row, problem}

    def issue(self, row: int, problem: str):
        if len(self.issues) < 50:
            self.issues.append({"row": int(row), "problem": problem})


def key_of(*vals) -> str:
    return hashlib.md5("|".join("" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v) for v in vals).encode()).hexdigest()[:16]


def col(df: pd.DataFrame, mapping: dict, name: str) -> pd.Series | None:
    m = mapping.get(name)
    if not m or m.get("column") not in df.columns:
        return None
    return df[m["column"]]


def nums(df, mapping, name, report: Report | None = None) -> pd.Series:
    s = col(df, mapping, name)
    if s is None:
        return pd.Series([None] * len(df), index=df.index, dtype="float64")
    out = number_series(s)
    if report is not None:
        raw = s.dropna().astype(str)
        eu = raw.str.contains(r"\d,\d{1,2}(?:\s|$|%|€)").sum() + raw.str.contains("[€$%]").sum()
        report.fixed += int(eu)
    return out


def dates(df, mapping, name, report: Report | None = None) -> pd.Series:
    s = col(df, mapping, name)
    if s is None:
        return pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    out = date_series(s)
    if report is not None:
        raw = s.dropna().astype(str)
        dayfirst = raw.str.match(r"^\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}").sum()
        if dayfirst:
            report.notes.append(f"Read {dayfirst:,} dates written day first (dd/mm/yyyy).")
            report.fixed += int(dayfirst)
    return out


def texts(df, mapping, name) -> pd.Series:
    s = col(df, mapping, name)
    if s is None:
        return pd.Series([None] * len(df), index=df.index, dtype=object)
    return s.map(lambda v: None if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "" else str(v).strip())


def fabric_of(name: str | None) -> str | None:
    t = norm(name or "")
    if re.search(r"bambu|bamboo", t):
        return "bamboo"
    if re.search(r"\bseda\b|silk", t):
        return "silk"
    if re.search(r"algodon|cotton|\bcoto\b", t):
        return "cotton"
    return None


def line_of(name: str | None) -> str | None:
    t = norm(name or "")
    if not t:
        return None
    return "children" if re.search(r"nin[oa]s?|kids?|infantil|child|gorrito|bandana pirata|nens", t) else "women"


def colour_of(name: str | None) -> str | None:
    if name and " - " in name:
        return name.split(" - ", 1)[1].strip()
    return None


CHANNELS = {"web": "Online store", "online store": "Online store", "instagram": "Instagram", "pos": "In person (markets)",
            "point of sale": "In person (markets)", "wholesale": "Wholesale (pharmacies)", "facebook": "Facebook", "shopify draft order":
            "Manual order", "tienda online": "Online store"}
FORMATS = {"ig reel": "Reel", "reel": "Reel", "reels": "Reel", "ig carousel": "Carousel", "carousel": "Carousel", "carousel album": "Carousel",
           "ig image": "Static image", "image": "Static image", "photo": "Static image", "ig story": "Story", "story": "Story",
           "video": "Video"}
GIFT_RE = re.compile(r"regal|gift|present|para mi (madre|amiga|hermana|mujer)|for my", re.I)


def base_rows(df: pd.DataFrame, first_row: int) -> pd.Series:
    return pd.Series(df.index.to_numpy() + first_row, index=df.index)


def to_orders(df, m, report: Report, first_row: int) -> dict[str, pd.DataFrame]:
    rows = base_rows(df, first_row)
    oid = texts(df, m, "order_id")
    if oid.isna().all():
        raise ValueError("No order numbers found")
    oid = oid.ffill()
    d = dates(df, m, "date", report)
    # fill dates within the same order
    d = d.groupby(oid).transform(lambda s: s.ffill().bfill())
    email = texts(df, m, "customer_email")
    email = email.groupby(oid).transform(lambda s: s.ffill().bfill())
    ref = texts(df, m, "customer_ref").groupby(oid).transform(lambda s: s.ffill().bfill())
    email = email.where(email.notna(), ref)
    cust = email.map(lambda v: v if v and str(v).startswith("c_") else hash_value(v))
    status = texts(df, m, "financial_status").map(lambda v: norm(v or ""))
    bad = status.isin({"refunded", "voided", "reembolsado", "anulado", "cancelled", "cancelado"})
    if bad.any():
        report.notes.append(f"Left out {int(bad.sum())} refunded or cancelled lines.")
    total = nums(df, m, "total", report)
    notes = texts(df, m, "notes").fillna("") + " " + texts(df, m, "note_attributes").fillna("")
    item_name = texts(df, m, "item_name")
    has_items = item_name.notna().any()

    o = pd.DataFrame({
        "order_id": oid, "date": d, "customer_id": cust, "subtotal": nums(df, m, "subtotal"), "total": total,
        "discount_code": texts(df, m, "discount_code").map(lambda v: v.upper() if v else None), "discount": nums(df, m, "discount"),
        "shipping": nums(df, m, "shipping"), "channel": texts(df, m, "channel").map(lambda v: CHANNELS.get(norm(v), v.title()) if v else None),
        "is_gift": notes.map(lambda v: bool(GIFT_RE.search(v))), "city": texts(df, m, "city"), "country": texts(df, m, "country"),
        "currency": texts(df, m, "currency"), "row_num": rows, "_bad": bad,
    })
    agg = o[~o["_bad"]].groupby("order_id", sort=False).agg({
        "date": "first", "customer_id": "first", "subtotal": "first", "total": "first", "discount_code": "first", "discount": "first",
        "shipping": "first", "channel": "first", "is_gift": "max", "city": "first", "country": "first", "currency": "first", "row_num": "first"})
    agg = agg.reset_index()
    if has_items and agg["total"].isna().mean() > 0.5:
        # some exports only carry line totals
        line_tot = (nums(df, m, "item_qty").fillna(1) * nums(df, m, "item_price")).groupby(oid).sum()
        agg["total"] = agg["total"].fillna(agg["order_id"].map(line_tot))
    missing = agg["date"].isna() | agg["total"].isna()
    for _, r in agg[missing].head(30).iterrows():
        report.issue(r["row_num"], "Order without a readable date or total")
    report.skipped += int(missing.sum()) + int(bad.sum())
    agg = agg[~missing].copy()
    agg["ts"] = agg["date"]
    agg["date"] = agg["date"].dt.date
    agg["currency"] = agg["currency"].fillna("EUR")
    agg["_key"] = agg["order_id"].map(lambda v: key_of(v))
    out = {"orders": agg}
    if has_items:
        it = pd.DataFrame({"order_id": oid, "date": d.dt.date, "customer_id": cust, "product": item_name,
                           "sku": texts(df, m, "item_sku"), "quantity": nums(df, m, "item_qty").fillna(1),
                           "price": nums(df, m, "item_price"), "row_num": rows})
        it = it[~bad & it["product"].notna() & it["order_id"].isin(set(agg["order_id"]))].copy()
        it["fabric"] = it["product"].map(fabric_of)
        it["line"] = it["product"].map(line_of)
        it["colour"] = it["product"].map(colour_of)
        it["_key"] = [key_of(a, b, c, i) for i, (a, b, c) in enumerate(zip(it["order_id"], it["sku"], it["product"]))]
        # stable key within an order: position of the line inside its order
        it["_key"] = [key_of(a, b, c, n) for a, b, c, n in zip(it["order_id"], it["sku"], it["product"], it.groupby("order_id").cumcount())]
        out["order_items"] = it
    report.rows_in = len(df)
    report.notes.append(f"Found {len(agg):,} orders" + (f" with {len(out['order_items']):,} product lines." if has_items else "."))
    return out


def to_products(df, m, report, first_row):
    p = pd.DataFrame({"product": texts(df, m, "product"), "sku": texts(df, m, "sku"), "price": nums(df, m, "price", report),
                      "type": texts(df, m, "type"), "colour": texts(df, m, "colour"), "inventory": nums(df, m, "inventory"),
                      "row_num": base_rows(df, first_row)})
    tags = texts(df, m, "tags").fillna("")
    p["fabric"] = (p["product"].fillna("") + " " + tags).map(fabric_of)
    p["line"] = (p["product"].fillna("") + " " + tags + " " + p["type"].fillna("")).map(line_of)
    p["colour"] = p["colour"].fillna(p["product"].map(colour_of))
    bad = p["product"].isna()
    report.skipped += int(bad.sum())
    p = p[~bad].copy()
    p["_key"] = [key_of(s or n) for s, n in zip(p["sku"], p["product"])]
    return {"products": p}


def to_customers(df, m, report, first_row):
    email = texts(df, m, "customer_email")
    c = pd.DataFrame({"customer_id": email.map(lambda v: v if v and v.startswith("c_") else hash_value(v)),
                      "city": texts(df, m, "city"), "country": texts(df, m, "country"),
                      "language": texts(df, m, "language").map(lambda v: tx.language_from_label(v) or v),
                      "orders_count": nums(df, m, "orders_count"), "total_spent": nums(df, m, "total_spent", report),
                      "accepts_marketing": texts(df, m, "accepts_marketing").map(parse_bool), "row_num": base_rows(df, first_row)})
    bad = c["customer_id"].isna()
    for r in c[bad]["row_num"].head(20):
        report.issue(r, "Customer without an email")
    report.skipped += int(bad.sum())
    c = c[~bad].copy()
    c["_key"] = c["customer_id"].map(key_of)
    return {"customers": c}


def _enrich_feedback(f: pd.DataFrame) -> pd.DataFrame:
    f["text"] = f["text"].map(scrub_storage)
    lang_given = f["language"].map(lambda v: tx.language_from_label(v) if v else None)
    f["language"] = [g or tx.detect_language(t) for g, t in zip(lang_given, f["text"])]
    sent = [tx.sentiment(t, r if r == r else None) for t, r in zip(f["text"], f["rating"].fillna(float("nan")))]
    # NPS-only answers: use NPS score for sentiment
    sent = [tx.sentiment(t, n if (r != r and n == n) else (r if r == r else None)) for t, r, n in
            zip(f["text"], f["rating"].fillna(float("nan")), f["nps"].fillna(float("nan")))]
    f["sentiment"] = [s[0] for s in sent]
    f["sentiment_score"] = [s[1] for s in sent]
    f["themes"] = f["text"].map(lambda t: ",".join(tx.themes(t)))
    f["distress"] = f["text"].map(tx.is_distress)
    f["fabric"] = f["product"].map(fabric_of)
    f["line"] = [line_of(p) if p else ("children" if "children" in th.split(",") else None) for p, th in zip(f["product"], f["themes"])]
    return f


def to_feedback(df, m, report, first_row, kind: str, source: str):
    n = len(df)
    empty = pd.Series([None] * n, index=df.index, dtype=object)
    f = pd.DataFrame({
        "date": dates(df, m, "date", report).dt.date if col(df, m, "date") is not None else empty,
        "kind": kind, "source": texts(df, m, "source").fillna(source) if col(df, m, "source") is not None else source,
        "text": texts(df, m, "text"), "title": texts(df, m, "title"), "rating": nums(df, m, "rating"), "nps": nums(df, m, "nps"),
        "product": texts(df, m, "product"), "language": texts(df, m, "language"),
        "customer_id": texts(df, m, "customer_email").map(lambda v: v if v is None or v.startswith("c_") else hash_value(v)),
        "heard_from": texts(df, m, "heard_from"), "consent_quote": texts(df, m, "consent_quote").map(lambda v: bool(parse_bool(v))),
        "platform": texts(df, m, "platform").fillna(source.replace(" reviews", "")) if kind == "review" else None,
        "external_id": texts(df, m, "external_id"), "row_num": base_rows(df, first_row)})
    if kind == "review":
        f["rating"] = f["rating"].where(f["rating"].between(1, 5))
    if "nps" in m:
        bad_nps = f["nps"].notna() & ~f["nps"].between(0, 10)
        f.loc[bad_nps, "nps"] = None
    bad = f["text"].isna() & f["rating"].isna() & f["nps"].isna()
    for r in f[bad]["row_num"].head(20):
        report.issue(r, "Empty row (no text, rating or score)")
    report.skipped += int(bad.sum())
    f = f[~bad].copy()
    f = _enrich_feedback(f)
    f["_key"] = [key_of(p, x) if x else key_of(d, t, c, r, s) for d, t, c, r, s, p, x in
                 zip(f["date"], f["text"], f["customer_id"], f["rating"], f["nps"], f["platform"], f["external_id"])]
    report.notes.append(f"Analysed {len(f):,} pieces of feedback for sentiment, themes and language.")
    if f["distress"].any():
        report.notes.append(f"{int(f['distress'].sum())} messages may come from someone having a hard time. They are flagged for a personal reply.")
    return {"feedback": f}


def to_social_posts(df, m, report, first_row, platform: str):
    d = dates(df, m, "date", report)
    cap = texts(df, m, "caption")
    fmt = texts(df, m, "format").map(lambda v: FORMATS.get(norm(v), v.title()) if v else None)
    if platform == "TikTok":
        fmt = fmt.fillna("Video")
    p = pd.DataFrame({"post_id": texts(df, m, "post_id"), "platform": platform, "ts": d, "date": d.dt.date, "format": fmt.fillna("Post"),
                      "caption": cap, "reach": nums(df, m, "reach"), "views": nums(df, m, "views"), "likes": nums(df, m, "likes"),
                      "comments": nums(df, m, "comments"), "saves": nums(df, m, "saves"), "shares": nums(df, m, "shares"),
                      "follows": nums(df, m, "follows"), "row_num": base_rows(df, first_row)})
    if p["reach"].isna().all():
        p["reach"] = p["views"]
    p["pillar"] = p["caption"].map(tx.pillar)
    p["hashtags"] = p["caption"].fillna("").str.count("#")
    p["caption_length"] = p["caption"].fillna("").str.len()
    bad = p["date"].isna()
    for r in p[bad]["row_num"].head(20):
        report.issue(r, "Post without a readable publish date")
    report.skipped += int(bad.sum())
    p = p[~bad].copy()
    p["post_id"] = [pid or key_of(d, c) for pid, d, c in zip(p["post_id"], p["date"], p["caption"])]
    p["_key"] = [key_of(platform, pid) for pid in p["post_id"]]
    report.notes.append("Sorted posts into content pillars from their captions (you can edit the pillar words in Settings).")
    return {"social_posts": p}


def to_social_comments(df, m, report, first_row, platform: str):
    t = texts(df, m, "text").map(scrub_storage)
    c = pd.DataFrame({"platform": platform.replace(" comments", ""), "post_id": texts(df, m, "post_id"),
                      "date": dates(df, m, "date", report).dt.date, "text": t,
                      "author_id": texts(df, m, "username").map(lambda v: v if v is None or v.startswith("c_") else hash_value(v)),
                      "likes": nums(df, m, "likes"), "replied": texts(df, m, "replied").map(parse_bool),
                      "row_num": base_rows(df, first_row)})
    bad = c["text"].isna()
    report.skipped += int(bad.sum())
    c = c[~bad].copy()
    c["language"] = c["text"].map(tx.detect_language)
    c["sentiment"] = c["text"].map(lambda v: tx.sentiment(v)[0])
    c["category"] = c["text"].map(tx.comment_category)
    c["distress"] = c["text"].map(tx.is_distress)
    c["_key"] = [key_of(p, d, t, a) for p, d, t, a in zip(c["post_id"], c["date"], c["text"], c["author_id"])]
    return {"social_comments": c}


def to_web(df, m, report, first_row):
    src = texts(df, m, "source").fillna("(unknown)")
    parts = src.str.split(" / ", n=1, expand=True)
    w = pd.DataFrame({"date": dates(df, m, "date", report).dt.date, "source": parts[0].str.strip(),
                      "medium": parts[1].str.strip() if parts.shape[1] > 1 else None, "landing_page": texts(df, m, "landing_page"),
                      "device": texts(df, m, "device").map(lambda v: v.lower() if v else None), "sessions": nums(df, m, "sessions"),
                      "users": nums(df, m, "users"), "conversions": nums(df, m, "conversions"), "revenue": nums(df, m, "revenue", report),
                      "row_num": base_rows(df, first_row)})
    bad = w["date"].isna() | w["sessions"].isna()
    report.skipped += int(bad.sum())
    for r in w[bad]["row_num"].head(20):
        report.issue(r, "Row without a date or a session count (often a total line)")
    w = w[~bad].copy()
    w["_key"] = [key_of(*v) for v in zip(w["date"], w["source"], w["medium"], w["landing_page"], w["device"])]
    return {"web_sessions": w}


def to_email(df, m, report, first_row):
    e = pd.DataFrame({"date": dates(df, m, "date", report).dt.date, "campaign": texts(df, m, "campaign"),
                      "recipients": nums(df, m, "recipients"), "opens": nums(df, m, "opens"), "clicks": nums(df, m, "clicks"),
                      "orders": nums(df, m, "orders"), "revenue": nums(df, m, "revenue", report), "row_num": base_rows(df, first_row)})
    bad = e["date"].isna() | e["campaign"].isna()
    report.skipped += int(bad.sum())
    e = e[~bad].copy()
    e["_key"] = [key_of(c, d) for c, d in zip(e["campaign"], e["date"])]
    return {"email_campaigns": e}


def transform(table_type: str, df: pd.DataFrame, mapping: dict, report: Report, first_row: int, source: str) -> dict[str, pd.DataFrame]:
    report.rows_in = len(df)
    if table_type == "orders":
        return to_orders(df, mapping, report, first_row)
    if table_type == "products":
        return to_products(df, mapping, report, first_row)
    if table_type == "customers":
        return to_customers(df, mapping, report, first_row)
    if table_type == "reviews":
        return to_feedback(df, mapping, report, first_row, "review", source)
    if table_type in ("survey_responses", "nps"):
        return to_feedback(df, mapping, report, first_row, "survey", source)
    if table_type == "feedback":
        return to_feedback(df, mapping, report, first_row, "message", source)
    if table_type == "social_posts":
        return to_social_posts(df, mapping, report, first_row, source)
    if table_type == "social_comments":
        return to_social_comments(df, mapping, report, first_row, source)
    if table_type == "web_sessions":
        return to_web(df, mapping, report, first_row)
    if table_type == "email_campaigns":
        return to_email(df, mapping, report, first_row)
    raise ValueError(f"Unknown table type {table_type}")
