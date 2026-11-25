"""Translation core shared by the backend and the harvest script. The TypeScript twin is frontend/src/lib/i18n.ts.

A string is looked up three ways, in order:
1. exactly;
2. as a template, with numbers, months and weekdays replaced by {0}, {1}, ... (so "Revenue fell 23%" matches "Revenue fell {0}%");
3. against wildcard patterns in which {x} stands for any name (a product, channel or platform).
Numbers are re-formatted the Spanish way (1.234,5) and month and day names are translated.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
ABBR_EN = [m[:3] for m in MONTHS_EN]
ABBR_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"]
DAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
WORDS = {**dict(zip(MONTHS_EN, MONTHS_ES)), **dict(zip(ABBR_EN, ABBR_ES)), **dict(zip(DAYS_EN, DAYS_ES))}

TOKEN = re.compile(r"\d[\d,.]*\d|\d|\b(?:" + "|".join(MONTHS_EN + DAYS_EN) + r")\b|\b(?:" + "|".join(ABBR_EN) + r")\b(?!\w)")
CATALOG_DIR = Path(__file__).resolve().parent / "i18n"


def templatize(s: str) -> tuple[str, list[str]]:
    vals: list[str] = []

    def rep(m):
        vals.append(m.group(0))
        return "{" + str(len(vals) - 1) + "}"
    t = TOKEN.sub(rep, s.replace("{", "{{").replace("}", "}}"))
    return t, vals


def es_value(v: str) -> str:
    if v in WORDS:
        return WORDS[v]
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?|\d+\.\d+", v):  # 1,234.5 -> 1.234,5
        return v.replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")
    return v


@lru_cache(maxsize=1)
def catalog() -> tuple[dict, list]:
    exact: dict[str, str] = {}
    patterns: list = []
    for f in sorted(CATALOG_DIR.glob("es*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for en, es in data.get("strings", {}).items():
            exact[en] = es
            low = en[:1].lower() + en[1:]
            if en[:1].isupper() and low not in exact and not en.isupper():  # same label used mid-sentence
                exact[low] = es[:1].lower() + es[1:]
        for en, es in data.get("patterns", {}).items():
            rx = re.escape(en).replace(r"\{x\}", "(?P<x>.+?)").replace(r"\{y\}", "(?P<y>.+?)").replace(r"\{z\}", "(?P<z>.*)")
            patterns.append((re.compile("^" + rx + "$"), es))
    return exact, patterns


def _cap(src: str, out: str) -> str:
    return out[:1].upper() + out[1:] if src[:1].isupper() and out[:1].islower() else out


def _numbers_only(t: str, vals: list[str]) -> str | None:
    """'{0}', '€{0}', '{0}%', '{0} to {1}' with no words: format numbers the Spanish way."""
    if re.search(r"[A-Za-z]", t.replace("{", "").replace("}", "")):
        return None
    t = re.sub(r"€\{(\d+)\}", r"{\1} €", t)
    t = re.sub(r"\{(\d+)\}%", r"{\1} %", t)
    try:
        return t.format(*[es_value(v) for v in vals])
    except (IndexError, KeyError):
        return None


def translate(s: str, lang: str = "es") -> str:
    if lang != "es" or not s or not s.strip():
        return s
    out = _translate(s)
    return _cap(s.strip(), out) if out != s else out


def _sentence(p: str, lang: str = "es") -> str:
    t = translate(p + ".", lang)
    if t != p + "." and t.endswith("."):
        return t[:-1]
    return translate(p, lang)


def _translate(s: str, lang: str = "es") -> str:
    core = s.strip()
    whole = _translate_one(s)
    if whole != s:
        return whole
    for sep in (" · ", ". "):  # joined subtitles, then a title followed by a sentence
        if sep not in core:
            continue
        parts = core.split(sep)
        # a sentence split off at ". " keeps its full stop while it is looked up
        out = [_sentence(p, lang) if sep == ". " and i < len(parts) - 1 else translate(p, lang) for i, p in enumerate(parts)]
        if out != parts:
            return s[: len(s) - len(s.lstrip())] + sep.join(out) + s[len(s.rstrip()):]
    if core[-1:] in ".:" and len(core) > 3:  # a sentence with a full stop added on screen
        inner = _translate_one(core[:-1])
        if inner != core[:-1]:
            return s[: len(s) - len(s.lstrip())] + inner + core[-1] + s[len(s.rstrip()):]
    return _translate_one(s)


def _translate_one(s: str, lang: str = "es") -> str:
    exact, patterns = catalog()
    core = s.strip()
    lead, trail = s[: len(s) - len(s.lstrip())], s[len(s.rstrip()):]
    if core in exact:
        return lead + exact[core] + trail
    t, vals = templatize(core)
    if t in exact:
        try:
            return lead + exact[t].format(*[es_value(v) for v in vals]) + trail
        except (IndexError, KeyError):
            return s
    if vals:
        n = _numbers_only(t, vals)
        if n is not None:
            return lead + n + trail
    for rx, es in patterns:
        m = rx.match(t)
        if m:
            g = {}
            for k, v in m.groupdict().items():
                raw = _untemplate(v, vals)
                tr = raw if k == "z" else translate(raw, lang)
                if tr != raw and not es.startswith("{" + k + "}"):
                    tr = tr[:1].lower() + tr[1:]  # translated label mid-sentence
                g[k] = tr
            out = es.replace("{x}", "\u0001").replace("{y}", "\u0002").replace("{z}", "\u0003")
            try:
                out = out.format(*[es_value(v) for v in vals]) if vals else out.replace("{{", "{").replace("}}", "}")
            except (IndexError, KeyError):
                return s
            result = lead + out.replace("\u0001", g.get("x", "")).replace("\u0002", g.get("y", "")).replace("\u0003", g.get("z", "")) + trail
            if result != s:
                return result
    return s


def _untemplate(part: str, vals: list[str]) -> str:
    """Put the original numbers back into a wildcard capture ("{3} Instagram" -> "12 Instagram")."""
    return re.sub(r"\{(\d+)\}", lambda m: vals[int(m.group(1))] if int(m.group(1)) < len(vals) else m.group(0), part)


def translate_tree(obj, lang: str = "es", skip=frozenset({"text", "caption", "product", "campaign", "file_name", "id", "_key", "post_id",
                                                           "reply_text", "draft", "sql", "url", "admin_url", "docs", "icon", "key"})):
    if lang != "es":
        return obj
    if isinstance(obj, str):
        return translate(obj, lang)
    if isinstance(obj, list):
        return [translate_tree(x, lang, skip) for x in obj]
    if isinstance(obj, dict):
        return {k: (v if k in skip else translate_tree(v, lang, skip)) for k, v in obj.items()}
    return obj
