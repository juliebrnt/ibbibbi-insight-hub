"""Read numbers from screenshots (for example Instagram Insights) and scanned PDFs when AI is available."""
from __future__ import annotations

import pandas as pd

from ..ai import client
from .readers import RawTable

PROMPT = """This is a screenshot or document uploaded by a small business owner (for example Instagram Insights, a Shopify report or a
survey summary). Extract the data it shows as one table. Return JSON: {"description": "<one sentence>", "columns": [...],
"rows": [[...], ...]}. Copy numbers exactly as shown; do not estimate missing values. Do not include people's names, handles,
emails or phone numbers."""


def extract(file_name: str, data: bytes) -> RawTable | None:
    if not client.enabled():
        return None
    ext = file_name.lower().rsplit(".", 1)[-1]
    if ext == "pdf":
        block = client.pdf_block(data)
    else:
        media = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}.get(ext)
        if not media:
            return None
        block = client.image_block(data, media)
    out = client.complete_json("You extract tables from images accurately.", [block, {"type": "text", "text": PROMPT}], max_tokens=4000)
    if not out or not out.get("columns") or not out.get("rows"):
        return None
    cols = [str(c) for c in out["columns"]]
    rows = [list(r)[:len(cols)] + [None] * (len(cols) - len(r)) for r in out["rows"] if isinstance(r, list)]
    df = pd.DataFrame(rows, columns=cols, dtype=object)
    return RawTable(f"{file_name} · read by AI", df, file_name, notes=[out.get("description", "Read from an image by AI. Please check the numbers.")])
