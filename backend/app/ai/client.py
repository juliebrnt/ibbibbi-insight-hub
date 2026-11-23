"""The only place that talks to an AI provider. Swap providers here.

Everything else in the app works without a key. When ANTHROPIC_API_KEY is set and
the user has AI analysis switched on, richer features use these helpers.
"""
from __future__ import annotations

import base64
import json
import re
from functools import lru_cache

from .. import db
from ..config import AI_MODEL, ANTHROPIC_API_KEY


def configured() -> bool:
    return bool(ANTHROPIC_API_KEY)


def enabled(ws: str | None = None) -> bool:
    return configured() and bool(db.get_setting("ai_enabled", True))


@lru_cache(maxsize=1)
def _client():
    import anthropic

    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, max_retries=2, timeout=60.0)


def complete(system: str, user: str | list, max_tokens: int = 2000, effort: str = "low") -> str | None:
    """Return the model's text, or None on any failure (callers fall back to templates)."""
    if not configured():
        return None
    import anthropic

    content = user if isinstance(user, list) else [{"type": "text", "text": user}]
    kwargs = dict(model=AI_MODEL, max_tokens=max_tokens, system=system, messages=[{"role": "user", "content": content}],
                  output_config={"effort": effort})
    try:
        try:
            resp = _client().beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
        except anthropic.BadRequestError:
            resp = _client().messages.create(**kwargs)
    except anthropic.APIError as e:  # rate limits, network, auth: degrade quietly
        print(f"AI call failed: {type(e).__name__}")
        return None
    if resp.stop_reason == "refusal":
        return None
    return "".join(b.text for b in resp.content if b.type == "text").strip() or None


def complete_json(system: str, user: str | list, max_tokens: int = 2000) -> dict | None:
    text = complete(system + "\nReply with a single JSON object and nothing else.", user, max_tokens)
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def image_block(data: bytes, media_type: str) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": base64.standard_b64encode(data).decode()}}


def pdf_block(data: bytes) -> dict:
    return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": base64.standard_b64encode(data).decode()}}
