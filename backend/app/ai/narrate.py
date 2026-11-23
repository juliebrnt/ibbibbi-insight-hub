"""Founder-friendly wording for insights, with the number guard as a safety net."""
from __future__ import annotations

import hashlib
import json

from ..privacy.pii import scrub
from . import client, guard

SYSTEM = """You write short, warm, plain-English summaries for the owners of a small business, from the facts given.
Use British English. Never use em dashes. Never invent numbers: use only numbers present in the facts. Never suggest targeting or
segmenting people by health status or treatment stage, and never suggest using someone's personal story without explicit consent.
Keep care and selling separate."""

_cache: dict[str, dict] = {}


def narrate(insight: dict) -> dict:
    """Return the insight with AI wording if it passes the guard, otherwise unchanged."""
    if not client.enabled():
        return insight
    facts = {k: insight[k] for k in ("title", "finding", "why_it_matters", "recommended_action", "evidence")}
    key = hashlib.md5(json.dumps(facts, sort_keys=True, default=str).encode()).hexdigest()
    if key in _cache:
        return {**insight, **_cache[key]}
    prompt = ("Rewrite these facts for the founders. Return JSON with keys title (under 12 words), finding (2 sentences), "
              "recommended_action (1 or 2 sentences).\n\nFacts:\n" + scrub(json.dumps(facts, default=str, ensure_ascii=False)))
    out = client.complete_json(SYSTEM, prompt, max_tokens=800)
    if not out:
        return insight
    text = " ".join(str(out.get(k, "")) for k in ("title", "finding", "recommended_action"))
    ok, _bad = guard.check(text, facts)
    if not ok or "—" in text:
        return insight
    from ..insights.rules import passes_guardrails

    if not passes_guardrails(str(out.get("recommended_action", ""))):
        return insight
    upd = {k: out[k] for k in ("title", "finding", "recommended_action") if out.get(k)}
    upd["ai_written"] = True
    _cache[key] = upd
    return {**insight, **upd}
