"""Guess what a table is and how its columns map to canonical fields."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pandas as pd
from rapidfuzz import fuzz

from .parsing import date_rate, norm, number_rate
from .registry import DAILY_LABELS, TYPES, TableType, daily_metric

MATCH_THRESHOLD = 78


def header_score(header: str, synonym: str) -> float:
    h, s = norm(header), norm(synonym)
    if not h or not s:
        return 0
    if h == s:
        return 100
    if len(s) >= 4 and (f" {s} " in f" {h} "):
        return 86 if len(s) >= 6 else 79
    if len(s) >= 6 and s in h:
        return 82
    return fuzz.ratio(h, s) * 0.95


def fingerprint(columns: list[str]) -> str:
    return hashlib.sha1("|".join(sorted(norm(c) for c in columns)).encode()).hexdigest()[:16]


def text_stats(s: pd.Series) -> float:
    vals = s.dropna().astype(str)
    if vals.empty:
        return 0
    return float(vals.str.len().mean())


def content_ok(kind: str, col: pd.Series) -> bool:
    if kind == "date":
        return date_rate(col) >= 0.6
    if kind == "number":
        return number_rate(col) >= 0.6
    if kind == "email":
        return col.dropna().astype(str).str.contains("@").mean() >= 0.5 if col.notna().any() else True
    return True


@dataclass
class Candidate:
    table_type: str
    label: str
    confidence: float
    mapping: dict[str, dict]  # canonical field -> {column, score}
    missing_required: list[str]


def map_columns(df: pd.DataFrame, t: TableType) -> dict[str, dict]:
    pairs = []
    for f in t.fields:
        for col in df.columns:
            best = max(header_score(col, syn) for syn in f.synonyms)
            if best >= MATCH_THRESHOLD:
                pairs.append((best, f, col))
    pairs.sort(key=lambda p: -p[0])
    used_cols, mapping = set(), {}
    for score, f, col in pairs:
        if f.name in mapping or col in used_cols:
            continue
        if not content_ok(f.kind, df[col]):
            continue
        mapping[f.name] = {"column": col, "score": round(score)}
        used_cols.add(col)
    # content fallbacks for required fields
    for f in t.fields:
        if f.name in mapping or not f.required:
            continue
        free = [c for c in df.columns if c not in used_cols]
        if f.kind == "date":
            for c in free:
                if date_rate(df[c]) >= 0.8:
                    mapping[f.name] = {"column": c, "score": 60}
                    used_cols.add(c)
                    break
        elif f.kind == "text":
            longest = sorted(free, key=lambda c: -text_stats(df[c]))
            if longest and text_stats(df[longest[0]]) >= 20 and number_rate(df[longest[0]]) < 0.3:
                mapping[f.name] = {"column": longest[0], "score": 60}
                used_cols.add(longest[0])
        elif f.name == "nps":
            for c in free:
                vals = pd.to_numeric(df[c], errors="coerce").dropna()
                if len(vals) > 5 and vals.between(0, 10).all() and vals.max() > 5 and (vals % 1 == 0).all():
                    mapping[f.name] = {"column": c, "score": 60}
                    used_cols.add(c)
                    break
    return mapping


def classify(df: pd.DataFrame, file_name: str, kind_hint: str | None = None) -> list[Candidate]:
    fname = norm(file_name)
    cands: list[Candidate] = []
    long_text = max((text_stats(df[c]) for c in df.columns), default=0) if len(df.columns) else 0
    for t in TYPES.values():
        mapping = map_columns(df, t)
        req = [f for f in t.fields if f.required]
        opt = [f for f in t.fields if not f.required]
        req_cov = sum(mapping[f.name]["score"] / 100 for f in req if f.name in mapping) / max(len(req), 1)
        opt_hit = sum(mapping[f.name]["score"] / 100 for f in opt if f.name in mapping)
        opt_cov = min(1.0, opt_hit / max(1, min(5, len(opt))))
        conf = 0.62 * req_cov + 0.33 * opt_cov
        if any(h in fname for h in t.filename_hints):
            conf += 0.08
        missing = [f.name for f in req if f.name not in mapping]
        if missing:
            conf = min(conf, 0.45)
        # content heuristics
        if t.key == "feedback":
            if long_text >= 25 and len(df.columns) <= 6:
                conf += 0.15
            if "text" in mapping and kind_hint != "text":
                avg = text_stats(df[mapping["text"]["column"]])
                numeric_cols = sum(1 for c in df.columns if number_rate(df[c]) >= 0.8)
                if avg < 20 or (avg < 35 and numeric_cols >= 2):
                    conf -= 0.3
            if kind_hint == "text":
                conf = 0.97
        if t.key == "reviews" and "rating" in mapping:
            r = pd.to_numeric(df[mapping["rating"]["column"]], errors="coerce").dropna()
            if len(r) and r.between(1, 5).mean() < 0.9:
                conf -= 0.3
        if t.key == "social_comments" and "post_id" not in mapping:
            conf -= 0.15
        if t.key == "social_posts" and not ({"reach", "likes", "views"} & set(mapping)):
            conf -= 0.3
        if t.key == "social_daily":
            # Meta's one-figure-per-day export: a date, one number, and the figure's name in the title or file name
            metric, _ = daily_metric(df.attrs.get("title"), file_name)
            if metric and not missing and len(df.columns) <= 3:
                conf = max(conf, 0.9)
            else:
                conf = min(conf, 0.2)
        cands.append(Candidate(t.key, t.label, round(max(0.0, min(conf, 0.99)), 2), mapping, missing))
    cands.sort(key=lambda c: -c.confidence)
    return cands


def source_label(table_type: str, file_name: str, df: pd.DataFrame) -> str:
    f = norm(file_name) + " " + " ".join(norm(c) for c in df.columns[:30])
    if table_type == "social_posts":
        return "TikTok" if "tiktok" in f or "video title" in f else "Instagram"
    if table_type == "social_comments":
        return "TikTok comments" if "tiktok" in f else "Instagram comments"
    if table_type in {"orders", "products", "customers"}:
        return "Shopify " + {"orders": "orders", "products": "products", "customers": "customers"}[table_type] if (
            "lineitem" in f or "shopify" in f or "handle" in f or "articulo" in f or "accepts email" in f) else TYPES[table_type].label
    if table_type == "social_daily":
        metric, platform = daily_metric(df.attrs.get("title"), file_name)
        return f"{platform} {DAILY_LABELS[metric].lower()}" if metric else f"{platform} daily figures"
    if table_type == "web_sessions":
        return "Google Analytics 4" if "ga4" in f or "key events" in f or "session source" in f else "Website visits"
    if table_type == "email_campaigns":
        return "Klaviyo" if "klaviyo" in f or "placed order" in f else "Email campaigns"
    if table_type == "reviews":
        return "Judge.me reviews" if "judge" in f or "curated" in f else "Product reviews"
    if table_type == "survey_responses":
        return "Google Forms survey" if "marca temporal" in f or "timestamp" in f else "Survey responses"
    return TYPES[table_type].label if table_type in TYPES else "Your data"
