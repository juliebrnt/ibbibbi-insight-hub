"""Business profile: everything that used to be hard-coded for one company.

Any business sets its name, industry, mission, key dates and whether its customers may be in a
vulnerable situation. Wording, seasonal context, reply drafts and care features adapt to it.
"""
from __future__ import annotations

from . import db

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

DEMO = {
    "name": "iBBIBBI", "industry": "Fashion and accessories (oncology headwear)",
    "mission": "Normalise oncology headwear as an expression of style and identity, and contribute positively to the cancer community.",
    "sensitive": True, "attribute_label": "Fabric", "line_label": "Product line",
    "key_dates": [{"month": 2, "label": "World Cancer Day (4 Feb)"}, {"month": 9, "label": "Childhood Cancer Awareness Month"},
                  {"month": 10, "label": "Breast Cancer Awareness Month"}, {"month": 12, "label": "Christmas"}],
}
DEFAULT = {"name": "Your business", "industry": "", "mission": "", "sensitive": False, "attribute_label": "Material", "line_label": "Product line",
           "key_dates": [{"month": 12, "label": "Christmas"}]}


def get(ws: str) -> dict:
    saved = db.get_setting(f"profile:{ws}", None)
    base = DEMO if ws == "demo" else DEFAULT
    return {**base, **(saved or {})}


def save(ws: str, data: dict) -> dict:
    allowed = {k: data[k] for k in DEFAULT if k in data}
    if "key_dates" in allowed:
        allowed["key_dates"] = [{"month": int(d["month"]), "label": str(d["label"])[:80]} for d in allowed["key_dates"]
                                if 1 <= int(d.get("month", 0)) <= 12 and d.get("label")]
    db.set_setting(f"profile:{ws}", {**(db.get_setting(f"profile:{ws}", None) or {}), **allowed})
    return get(ws)


def key_date(ws: str, month: int) -> str | None:
    return next((d["label"] for d in get(ws)["key_dates"] if d["month"] == month), None)


def peak_months(ws: str) -> set[int]:
    return {d["month"] for d in get(ws)["key_dates"]}
