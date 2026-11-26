"""Meta Business Suite daily exports: a 'sep=,' line, a title line, then "Fecha","Primary" with one row per day."""
from __future__ import annotations

import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("DB_PATH", str(Path(tempfile.mkdtemp()) / "test.duckdb"))
os.environ["ANTHROPIC_API_KEY"] = ""

from app import db  # noqa: E402
from app.analytics import common, social  # noqa: E402
from app.ingest import pipeline  # noqa: E402
from app.ingest.explain import explain  # noqa: E402

WS = "t_ig"
START = date(2026, 10, 27)


def meta_csv(title: str, values: dict[int, int]) -> bytes:
    lines = ["sep=,", f'"{title}"', '"Fecha","Primary"']
    lines += [f'"{(START + timedelta(days=i)).isoformat()}T00:00:00","{v}"' for i, v in sorted(values.items())]
    return ("\n".join(lines) + "\n\n").encode()


def daily(vals: list[int]) -> dict[int, int]:
    return dict(enumerate(vals))


REACH = [281, 13, 1, 7, 0, 5, 163, 53, 1, 196, 25, 169, 167, 285, 559, 251, 16, 222, 27, 219, 23, 249, 15, 5, 7, 4, 8, 3, 1, 5]
VISITS = [8, 1, 0, 4, 3, 4, 6, 1, 0, 7, 1, 3, 10, 17, 11, 5, 0, 0, 16, 11, 5, 4, 1, 3, 2, 4, 3, 1, 1, 0]
FILES = {
    "Alcance.csv": meta_csv("Alcance", daily(REACH)),
    "Visitas.csv": meta_csv("Visitas al perfil de Instagram", daily(VISITS)),
    "Seguidores.csv": meta_csv("Seguidores de Instagram", {4: 1, 7: 1, 9: 1, 13: 2, 27: 1}),  # only days with new followers
    "Clics en el enlace.csv": meta_csv("Clics en el enlace de Instagram", daily([0] * 30)),
}


def setup_module():
    for name, data in FILES.items():
        res = pipeline.auto_import(name, data, WS)
        assert res and res[0]["ok"], res


def test_each_file_is_recognised_as_its_own_figure():
    rows = db.rows("SELECT file_name, table_type, source_label FROM datasets WHERE ws = ? ORDER BY file_name", [WS])
    got = {r["file_name"]: (r["table_type"], r["source_label"]) for r in rows}
    assert got["Alcance.csv"] == ("social_daily", "Instagram reach")
    assert got["Visitas.csv"] == ("social_daily", "Instagram profile visits")
    assert got["Seguidores.csv"] == ("social_daily", "Instagram follows")
    assert got["Clics en el enlace.csv"] == ("social_daily", "Instagram link clicks")


def test_status_says_where_it_is_shown_and_explains_missing_days():
    ds = db.rows("SELECT * FROM datasets WHERE ws = ? AND file_name = 'Seguidores.csv'", [WS])[0]
    import json
    ds["report"] = json.loads(ds["report"])
    e = explain(ds)
    assert e["status"] == "shown" and e["shown_on"][0]["path"] == "/social"
    assert any("count as 0" in n for n in ds["report"]["notes"])


def test_uploading_the_same_file_again_does_not_double_count():
    pipeline.auto_import("Alcance (1).csv", FILES["Alcance.csv"], WS)
    assert db.one("SELECT sum(value) FROM social_daily WHERE ws = ? AND metric = 'reach'", [WS]) == sum(REACH)


def test_account_view_totals_funnel_and_warnings():
    acc = social.account(WS, common.period(WS, "90d"))
    k = {x["metric"]: x["value"] for x in acc["kpis"]}
    assert k["reach"] == sum(REACH) and k["profile_visits"] == sum(VISITS) and k["follows"] == 6 and k["link_clicks"] == 0
    assert [f["metric"] for f in acc["funnel"]] == ["reach", "profile_visits", "follows", "link_clicks"]
    assert len(acc["series"]) == 30 and acc["series"][0]["follows"] == 0  # missing days filled with 0
    kinds = {w["kind"] for w in acc["warnings"]}
    assert "link" in kinds and "drop" in kinds
    assert "Visualizaciones (Views)" in acc["missing_files"]


def test_a_plain_date_and_number_file_is_not_taken_for_instagram():
    data = b"Fecha,Primary\n2026-11-01,3\n2026-11-02,4\n2026-11-03,5\n"
    st = pipeline.stage("export.csv", data, WS)
    assert st["tables"][0]["table_type"] != "social_daily"


def test_what_to_add_says_exactly_which_files_are_missing():
    from app.ingest.checklist import checklist
    items = {i["key"]: i for i in checklist(WS, today=date(2026, 11, 26))}
    ig = items["ig_daily"]
    assert ig["status"] == "partial" and "Visualizaciones (Views)" in ig["todo"] and "Alcance" not in ig["todo"]
    assert "from 26 Nov 2026 to today" in ig["todo"]
    assert items["orders"]["status"] == "missing" and items["orders"]["todo"]


def test_an_instagram_file_saved_as_own_dataset_earlier_says_to_upload_again():
    ds = {"id": "z", "rows_imported": 30, "flexible": True, "file_name": "Alcance.csv", "report": {},
          "flex_config": {"title": "Alcance", "trend": {"date": "fecha", "value": "primary"},
                          "columns": [{"column": "fecha", "label": "Fecha", "type": "date"}, {"column": "primary", "label": "Primary", "type": "number"}]}}
    e = explain(ds)
    assert e["status"] == "partial" and "upload the same file again" in e["fixes"][0]
