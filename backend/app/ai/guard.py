"""Number guard: AI-written text may only contain numbers that exist in the facts payload."""
from __future__ import annotations

import re

NUM_RE = re.compile(r"(?<![\w.])[-+]?\d[\d.,]*\d|(?<![\w.])\d")
# small numbers that appear in ordinary language ("one in three", "two weeks", years)
ALLOWED_FREE = {0, 1, 2, 3, 4, 5, 6, 7, 10, 12, 15, 30, 100}


def _to_float(tok: str) -> float | None:
    t = tok.strip("+")
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", t):
        t = t.replace(",", "")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", t):
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def payload_numbers(obj) -> list[float]:
    out: list[float] = []

    def walk(o):
        if isinstance(o, bool) or o is None:
            return
        if isinstance(o, (int, float)):
            out.append(float(o))
        elif isinstance(o, str):
            for tok in NUM_RE.findall(o):
                v = _to_float(tok)
                if v is not None:
                    out.append(v)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)
    walk(obj)
    return out


def _matches(v: float, known: list[float]) -> bool:
    for k in known:
        for cand in (k, k * 100, k / 100):
            if abs(cand) < 1e-9 and abs(v) < 1e-9:
                return True
            tol = max(0.051, abs(cand) * 0.006) if abs(cand) < 1000 else abs(cand) * 0.006
            if abs(v - cand) <= tol or abs(v - round(cand)) < 1e-9 or abs(v - round(cand, 1)) < 1e-9:
                return True
    return False


def check(text: str, facts) -> tuple[bool, list[str]]:
    """Return (ok, unknown_numbers). Years and tiny everyday numbers are allowed."""
    known = payload_numbers(facts)
    bad = []
    for tok in NUM_RE.findall(text):
        v = _to_float(tok)
        if v is None:
            continue
        if v in ALLOWED_FREE or (1990 <= v <= 2100 and v.is_integer()):
            continue
        if not _matches(v, known):
            bad.append(tok)
    return (not bad, bad)
