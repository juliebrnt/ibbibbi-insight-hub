"""Tell the founder, for every uploaded file, where its data now appears or exactly why it does not and how to fix the file."""
from __future__ import annotations

import json
from datetime import date

from .. import db

PAGES = {
    "orders": [("Home", "/"), ("Sales", "/sales")],
    "products": [("Sales: products", "/sales")],
    "customers": [("Sales: customers", "/sales")],
    "reviews": [("Feedback", "/feedback"), ("Home", "/")],
    "feedback": [("Feedback", "/feedback"), ("Home", "/")],
    "survey_responses": [("Feedback", "/feedback"), ("Home", "/")],
    "social_posts": [("Social", "/social"), ("Home", "/")],
    "social_comments": [("Social: comments", "/social"), ("Feedback", "/feedback")],
    "social_daily": [("Social: Instagram account", "/social")],
    "web_sessions": [("Sales: website", "/sales")],
    "email_campaigns": [("Sales: email", "/sales")],
}

GENERIC_FIX = ("Check that the first row holds the column names, each following row is one record, "
               "and dates and amounts sit in their own columns. Then upload it again.")


def _days(a, b) -> int | None:
    if not a or not b:
        return None
    a = a if isinstance(a, date) else date.fromisoformat(str(a)[:10])
    b = b if isinstance(b, date) else date.fromisoformat(str(b)[:10])
    return (b - a).days + 1


def explain(ds: dict) -> dict:
    """ds is a row of the datasets table (flex_config and report may be JSON strings or dicts)."""
    rows = ds.get("rows_imported") or 0
    report = ds.get("report") or {}
    if isinstance(report, str):
        report = json.loads(report or "{}")
    issues = report.get("issues") or []
    shown, reasons, fixes, notes = [], [], [], []

    if rows == 0:
        reasons.append("No rows could be read from this file.")
        if issues:
            reasons.append(f"For example, row {issues[0]['row']}: {issues[0]['problem'].lower()}.")
        fixes.append(GENERIC_FIX)
        return {"status": "not_shown", "shown_on": [], "reasons": reasons, "fixes": fixes, "notes": notes}

    if ds.get("flexible"):
        cfg = ds.get("flex_config") or {}
        if isinstance(cfg, str):
            cfg = json.loads(cfg or "{}")
        cols = cfg.get("columns") or []
        has_date = any(c["type"] == "date" for c in cols)
        has_num = any(c["type"] == "number" for c in cols)
        labels = {str(c.get("label", "")).strip().lower() for c in cols}
        if labels == {"fecha", "primary"} or labels == {"date", "primary"}:
            from .registry import daily_metric
            if daily_metric(cfg.get("title"), ds.get("file_name"))[0]:
                return {"status": "partial", "shown_on": [{"label": "Sales: your own files", "path": "/sales"}] if cfg.get("trend") else [],
                        "reasons": ["This is an Instagram account figure, uploaded before the hub could read them, so it is not on Social."],
                        "fixes": ["Undo this upload (the arrow on the right) and upload the same file again. It will then appear on Social."],
                        "notes": notes}
        if cfg.get("trend"):
            shown.append({"label": "Sales: your own files", "path": "/sales"})
        if cfg.get("text_column"):
            shown.append({"label": "Feedback", "path": "/feedback"})
        if not shown:
            reasons.append("We could not tell what kind of data this is, and it has nothing we can chart on its own.")
            if not has_date:
                reasons.append("No column could be read as dates, so it cannot be shown over time.")
                fixes.append("Add a column with the date of each row, written like 25/11/2026.")
            if not has_num:
                reasons.append("No column could be read as numbers (amounts, units, counts).")
                fixes.append("Put amounts in their own column with only the number, like 24,50 or 24,50 €.")
            if has_date and has_num:
                fixes.append("Open Uploaded files and choose Make a trend to pick the date and the number to follow.")
            fixes.append("If this is sales, reviews, social media or survey data, using the platform's own export works best.")
        elif cfg.get("trend"):
            notes.append("We did not recognise this as a standard export, so it is shown as a simple monthly trend.")
    else:
        for label, path in PAGES.get(ds.get("table_type"), []):
            shown.append({"label": label, "path": path})

    if issues:
        notes.append(f"{len(issues)} row{'s' if len(issues) != 1 else ''} could not be read (for example row {issues[0]['row']}: "
                      f"{issues[0]['problem'].lower()}). The rest is shown.")
    span = _days(ds.get("date_min"), ds.get("date_max"))
    if span is not None and span < 56 and shown:
        notes.append(f"This file covers {span} days. Comparisons with an earlier period appear once you add older or newer data.")
    if ds.get("table_type") == "orders":
        has_cust = db.one("SELECT count(*) FROM orders WHERE dataset_id = ? AND customer_id IS NOT NULL", [ds["id"]]) or 0
        if not has_cust:
            notes.append("There is no customer email or number, so repeat customers cannot be counted. Names are never stored.")

    status = "shown" if shown and not reasons else ("not_shown" if not shown else "partial")
    return {"status": status, "shown_on": shown, "reasons": reasons, "fixes": fixes, "notes": notes}
