"""Robust value parsers for Spanish, European and US formats."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime

import pandas as pd

_NUM_CLEAN = re.compile(r"[^\d,.\-]")


def norm(s: str) -> str:
    """Lower-case, strip accents and punctuation so headers can be compared."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", " ", s).strip().lower()
    return s


def parse_number(v) -> float | None:
    """Parse '1.234,56 €', '1,234.56', '45%', '(12.5)', '12,5' and similar."""
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return None if pd.isna(v) else float(v)
    s = str(v).strip()
    if not s or s.lower() in {"nan", "none", "null", "-", "n/a", "na", "--"}:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = _NUM_CLEAN.sub("", s)
    if not s or s in {"-", ".", ","}:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):  # 1.234,56
            s = s.replace(".", "").replace(",", ".")
        else:  # 1,234.56
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        # '1,234' with exactly 3 trailing digits and several groups is a thousands separator
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) <= 3 and parts[0] not in {"0", "-0"}):
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        x = float(s)
    except ValueError:
        return None
    return -x if neg else x


def number_series(s: pd.Series) -> pd.Series:
    """Parse a column; if most values look like '1.234' European thousands, honour that."""
    vals = s.dropna().astype(str).str.strip()
    vals = vals[vals != ""]
    comma_dec = vals.str.contains(r"^\-?[\d.]*\d,\d{1,2}(?:\s|$|%|€)", regex=True).mean() if len(vals) else 0
    if comma_dec > 0.3:
        # European: dots are thousands, commas are decimals
        def eu(v):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            t = _NUM_CLEAN.sub("", str(v)).replace(".", "").replace(",", ".")
            try:
                return float(t) if t not in {"", "-", "."} else None
            except ValueError:
                return None
        return s.map(eu).astype("float64")
    return s.map(parse_number).astype("float64")


_DATE_FORMATS_DAYFIRST = ["%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%Y %H:%M"]
_DATE_FORMATS_ISO = ["%Y-%m-%d %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                     "%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"]
_DATE_FORMATS_US = ["%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"]
_ES_MONTHS = {"ene": "jan", "feb": "feb", "mar": "mar", "abr": "apr", "may": "may", "jun": "jun", "jul": "jul", "ago": "aug",
              "sep": "sep", "set": "sep", "oct": "oct", "nov": "nov", "dic": "dec", "gen": "jan", "febr": "feb", "abr.": "apr",
              "maig": "may", "juny": "jun", "jul.": "jul", "des": "dec"}


def _try_formats(vals: pd.Series, fmts: list[str]) -> tuple[pd.Series, float]:
    best, best_rate = None, -1.0
    for f in fmts:
        parsed = pd.to_datetime(vals, format=f, errors="coerce", utc="%z" in f)
        rate = parsed.notna().mean()
        if rate > best_rate:
            best, best_rate = parsed, rate
        if rate > 0.97:
            break
    return best, best_rate


def date_series(s: pd.Series) -> pd.Series:
    """Parse a column of dates. Day-first is preferred unless the data proves otherwise (for example 03/25/2026)."""
    if pd.api.types.is_datetime64_any_dtype(s):
        return pd.to_datetime(s).dt.tz_localize(None) if getattr(s.dt, "tz", None) else pd.to_datetime(s)
    raw = s.map(lambda v: v if isinstance(v, (datetime, date)) else (None if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()))
    if raw.map(lambda v: isinstance(v, (datetime, date))).mean() > 0.8:
        return pd.to_datetime(raw, errors="coerce")
    vals = raw.dropna().astype(str)
    vals = vals[vals != ""]
    if vals.empty:
        return pd.Series(pd.NaT, index=s.index)
    sample = vals.head(400)
    candidates = []
    for fmts in (_DATE_FORMATS_ISO, _DATE_FORMATS_DAYFIRST, _DATE_FORMATS_US):
        parsed, rate = _try_formats(sample, fmts)
        candidates.append((rate, fmts))
    # prefer day-first over US when tied (Spanish business)
    candidates.sort(key=lambda t: (-round(t[0], 3), 0 if t[1] is _DATE_FORMATS_ISO else 1 if t[1] is _DATE_FORMATS_DAYFIRST else 2))
    rate, fmts = candidates[0]
    full = raw.astype("string")
    if rate >= 0.6:
        out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
        remaining = full.notna()
        for f in fmts:
            if not remaining.any():
                break
            p = pd.to_datetime(full[remaining], format=f, errors="coerce", utc="%z" in f)
            if getattr(p.dt, "tz", None) is not None:
                p = p.dt.tz_convert("Europe/Madrid").dt.tz_localize(None)
            ok = p.notna()
            out.loc[p[ok].index] = p[ok].astype("datetime64[ns]")
            remaining = remaining & out.isna()
        return out
    # fallback: Spanish month names, then pandas inference with dayfirst
    def month_words(v):
        if v is None or pd.isna(v):
            return None
        t = str(v).lower()
        for es, en in _ES_MONTHS.items():
            t = re.sub(rf"\b{re.escape(es)}\w*", en, t)
        return t.replace(" de ", " ")
    try:
        out = pd.to_datetime(full.map(month_words), errors="coerce", dayfirst=True, format="mixed")
    except (ValueError, TypeError):
        out = pd.to_datetime(full.map(month_words), errors="coerce", dayfirst=True)
    if getattr(out.dt, "tz", None) is not None:
        out = out.dt.tz_localize(None)
    return out


def date_rate(s: pd.Series) -> float:
    vals = s.dropna()
    vals = vals[vals.astype(str).str.strip() != ""]
    if vals.empty:
        return 0.0
    sample = vals.head(200)
    # pure small integers are not dates
    if sample.astype(str).str.fullmatch(r"\-?\d{1,5}([.,]\d+)?").mean() > 0.5:
        return 0.0
    return float(date_series(sample).notna().mean())


def number_rate(s: pd.Series) -> float:
    vals = s.dropna()
    vals = vals[vals.astype(str).str.strip() != ""]
    if vals.empty:
        return 0.0
    sample = vals.head(300).astype(str)
    has_digit = sample.str.contains(r"\d")
    letters = sample.str.count(r"[A-Za-z]") > 3
    parsed = sample.map(parse_number).notna() & has_digit & ~letters
    return float(parsed.mean())


TRUE = {"yes", "y", "true", "1", "si", "sí", "s", "x", "oui", "verdadero", "cierto", "on", "regalo: sí", "gift: true"}
FALSE = {"no", "n", "false", "0", "falso", "off", ""}


def parse_bool(v) -> bool | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, bool):
        return v
    t = norm(str(v))
    if t in {norm(x) for x in TRUE}:
        return True
    if t in {norm(x) for x in FALSE}:
        return False
    return None
