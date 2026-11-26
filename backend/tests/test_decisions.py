"""Decision helpers on the demo data: each gives one answer, rows and a next step, and none mistakes the season for an effect."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("DB_PATH", str(Path(tempfile.mkdtemp()) / "test.duckdb"))
os.environ["ANTHROPIC_API_KEY"] = ""

from app.analytics import common, decisions  # noqa: E402
from app.demo import loader  # noqa: E402

WS = "t_dec"


def setup_module():
    loader.load(WS)


def end():
    return common.latest_date(WS)


def test_instagram_sales_removes_the_season():
    d = decisions.instagram_sales(WS, end())
    assert d and d["title"] and d["todo"] and d["rows"]
    # the made-up data has no post effect built in, so once busy weeks are accounted for no lift should look large
    assert all(abs(r["lift"]) < 20 for r in d["rows"] if r["posts"] >= 20)
    assert "not proof" in d["note"]


def test_product_map_uses_every_group_and_compares_with_the_shop():
    d = decisions.product_map(WS, end())
    groups = {r["group"] for r in d["rows"]}
    assert {"grow", "fix"} <= groups and len(groups) >= 3
    assert d["brand_trend"] > 0 and all("vs_brand" in r for r in d["rows"])
    assert d["summary"].count("to ") == 4


def test_customer_groups_cover_everyone_once():
    d = decisions.segments(WS, end())
    assert sum(r["customers"] for r in d["rows"]) == d["customers"]
    assert abs(sum(r["revenue_share"] for r in d["rows"]) - 1) < 0.01
    assert all(r["action"] for r in d["rows"])


def test_seasonal_plan_gives_ranges_not_single_numbers():
    d = decisions.seasonal(WS, end())
    assert d["peak"] == "October" and d["peak_index"] > 1.5
    assert all(r["low"] < r["mid"] < r["high"] for r in d["rows"]) and any(r["label"].startswith("October") for r in d["rows"])
    assert d["sellers"]
