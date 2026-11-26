"""Shared helpers: periods, formatting and safe division."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .. import db

RANGES = {"28d": 28, "90d": 91, "365d": 365}


@dataclass
class Period:
    start: date
    end: date
    prev_start: date
    prev_end: date
    label: str
    ly_start: date
    ly_end: date

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def params(self):
        return [self.start, self.end]


def latest_date(ws: str) -> date:
    d = db.one("""SELECT max(d) FROM (
        SELECT max(date) d FROM orders WHERE ws = ? UNION ALL SELECT max(date) FROM feedback WHERE ws = ?
        UNION ALL SELECT max(date) FROM social_posts WHERE ws = ? UNION ALL SELECT max(date) FROM web_sessions WHERE ws = ? UNION ALL SELECT max(date) FROM social_daily WHERE ws = ?)""",
               [ws, ws, ws, ws, ws])
    today = date.today()
    return min(d, today) if d else today


def earliest_date(ws: str) -> date | None:
    return db.one("""SELECT min(d) FROM (
        SELECT min(date) d FROM orders WHERE ws = ? UNION ALL SELECT min(date) FROM feedback WHERE ws = ?
        UNION ALL SELECT min(date) FROM social_posts WHERE ws = ? UNION ALL SELECT min(date) FROM web_sessions WHERE ws = ? UNION ALL SELECT min(date) FROM social_daily WHERE ws = ?)""",
                  [ws, ws, ws, ws, ws])


def period(ws: str, rng: str = "90d") -> Period:
    end = latest_date(ws)
    if rng and ".." in rng:
        a, b = rng.split("..")
        start, end = date.fromisoformat(a), date.fromisoformat(b)
        label = f"{start:%-d %b %Y} to {end:%-d %b %Y}"
    elif rng == "all":
        start = earliest_date(ws) or end - timedelta(days=365)
        label = "All time"
    else:
        days = RANGES.get(rng, 91)
        start = end - timedelta(days=days - 1)
        label = {"28d": "Last 4 weeks", "90d": "Last 3 months", "365d": "Last 12 months"}.get(rng, f"Last {days} days")
    span = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span - 1)
    try:
        ly_start, ly_end = start.replace(year=start.year - 1), end.replace(year=end.year - 1)
    except ValueError:
        ly_start, ly_end = start - timedelta(days=365), end - timedelta(days=365)
    return Period(start, end, prev_start, prev_end, label, ly_start, ly_end)


def pct_change(cur, prev):
    if cur is None or prev in (None, 0):
        return None
    return round((cur - prev) / abs(prev) * 100, 1)


def div(a, b, nd=4):
    if a is None or b in (None, 0):
        return None
    return round(a / b, nd)


def eur(x) -> str:
    if x is None:
        return "n/a"
    return f"€{x:,.0f}" if abs(x) >= 100 else f"€{x:,.2f}"


def fmt_pct(x, nd=0) -> str:
    return "n/a" if x is None else f"{x * 100:.{nd}f}%"


def has(table: str, ws: str) -> int:
    return int(db.one(f"SELECT count(*) FROM {table} WHERE ws = ?", [ws]) or 0)


def bucket_for(p: Period) -> str:
    return "day" if p.days <= 31 else "week" if p.days <= 200 else "month"


def subtitle(p: Period, source: str) -> str:
    return f"{p.label} ({p.start:%-d %b %Y} to {p.end:%-d %b %Y}) · {source}"
