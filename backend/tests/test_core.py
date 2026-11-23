"""Tests for parsers, classification, privacy, number guard, SQL validation, rules and the import pipeline."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("DB_PATH", str(Path(tempfile.mkdtemp()) / "test.duckdb"))
os.environ["ANTHROPIC_API_KEY"] = ""

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from app.ai import ask, guard  # noqa: E402
from app.ingest import parsing, readers  # noqa: E402
from app.ingest.classify import classify  # noqa: E402
from app.privacy import pii  # noqa: E402

DEMO = Path(__file__).resolve().parents[2] / "demo_data"


# ---------------- parsers ----------------
@pytest.mark.parametrize("raw,expected", [
    ("1.234,56 €", 1234.56), ("1,234.56", 1234.56), ("12,5", 12.5), ("45%", 45.0), ("(12.50)", -12.5), ("€ 39,00", 39.0),
    ("", None), ("n/a", None), ("1.000.000", 1000000.0), (7, 7.0),
])
def test_parse_number(raw, expected):
    assert parsing.parse_number(raw) == expected


def test_number_series_european_column():
    s = pd.Series(["1.234,50", "39,00", "2.000,00"])
    assert parsing.number_series(s).tolist() == [1234.5, 39.0, 2000.0]


def test_dates_day_first_and_iso_and_compact():
    assert parsing.date_series(pd.Series(["04/03/2026 10:22", "25/12/2025 09:00"])).dt.strftime("%Y-%m-%d").tolist() == ["2026-03-04", "2025-12-25"]
    assert parsing.date_series(pd.Series(["2025-03-04 10:22:11 +0100"])).dt.strftime("%Y-%m-%d").tolist() == ["2025-03-04"]
    assert parsing.date_series(pd.Series(["20250105", "20251231"])).dt.strftime("%Y-%m-%d").tolist() == ["2025-01-05", "2025-12-31"]


def test_us_dates_detected_when_unambiguous():
    out = parsing.date_series(pd.Series(["03/25/2026 10:00", "12/31/2025 08:00"]))
    assert out.dt.month.tolist() == [3, 12]


def test_header_row_found_below_comments():
    text = "# Report\n# Account: x\n\nDate,Sessions,Device category\n20250101,12,mobile\n20250102,9,desktop\n"
    df = readers.read_delimited(text)
    assert list(df.columns) == ["Date", "Sessions", "Device category"] and len(df) == 2


def test_semicolon_and_bom():
    data = "﻿Fecha;Caja (€)\n01/03/2025;125,63\n".encode("utf-8")
    t = readers.read_file("x.csv", data)[0]
    assert list(t.df.columns) == ["Fecha", "Caja (€)"]


def test_split_pasted_messages():
    assert len(readers.split_messages("Hola, me encanta.\n\nMuy suave.\n\n  \nGracias!")) == 3


# ---------------- classification ----------------
EXPECTED = {
    "shopify_orders_export_2025.csv": "orders", "pedidos_shopify_2026.csv": "orders", "products_export.csv": "products",
    "customers_export.csv": "customers", "judgeme_reviews_export.csv": "reviews", "instagram_posts_meta_export.csv": "social_posts",
    "instagram_comments.json": "social_comments", "tiktok_content_analytics.xlsx": "social_posts", "ga4_traffic_acquisition.csv": "web_sessions",
    "klaviyo_campaigns.csv": "email_campaigns", "mensajes_whatsapp_pegados.txt": "feedback",
}


@pytest.mark.parametrize("name,expected", EXPECTED.items())
def test_classify_demo_files(name, expected):
    t = readers.read_file(name, (DEMO / name).read_bytes())[0]
    top = classify(t.df, name, t.kind_hint)[0]
    assert top.table_type == expected and top.confidence >= 0.6


def test_two_sheet_workbook():
    tables = readers.read_file("encuesta_nps_y_mensajes.xlsx", (DEMO / "encuesta_nps_y_mensajes.xlsx").read_bytes())
    types = [classify(t.df, t.file_name)[0].table_type for t in tables]
    assert types == ["survey_responses", "feedback"]


def test_unknown_file_is_flexible():
    t = readers.read_file("mercadillo_ventas.csv", (DEMO / "mercadillo_ventas.csv").read_bytes())[0]
    assert classify(t.df, t.file_name)[0].confidence < 0.6


def test_renamed_headers_still_match():
    df = pd.DataFrame({"Order #": ["1001"], "Fecha del pedido": ["01/02/2026"], "Importe total": ["45,00"], "E-mail": ["a@b.com"]})
    top = classify(df, "export.csv")[0]
    assert top.table_type == "orders"


# ---------------- privacy ----------------
def test_pii_detect_defaults():
    df = pd.DataFrame({"Billing Name": ["Ana Puig"], "Email": ["ana@example.com"], "Billing Phone": ["+34 600 111 222"],
                       "Billing Street": ["Carrer Gran 1"], "Total": ["39,00"], "Created at": ["2025-01-01"]})
    found = {p["column"]: p["action"] for p in pii.detect(df)}
    assert found == {"Billing Name": "drop", "Email": "hash", "Billing Phone": "drop", "Billing Street": "drop"}


def test_hash_is_stable_and_not_reversible():
    a, b = pii.hash_value("Ana@Example.com "), pii.hash_value("ana@example.com")
    assert a == b and "ana" not in a


def test_scrub_removes_contact_details():
    t = pii.scrub("Escríbeme a ana@example.com o al +34 600 111 222, soy @ana_p, mira https://x.com/a")
    assert "@example" not in t and "600" not in t and "@ana_p" not in t and "https" not in t


# ---------------- number guard ----------------
def test_number_guard_accepts_payload_numbers():
    facts = {"evidence": [{"value": 38.75}, {"value": 0.27}], "finding": "Reels averaged 41 saves"}
    assert guard.check("Reels average 41 saves and 27% of orders are gifts; saves per post 38.8.", facts)[0]


def test_number_guard_rejects_invented_figure():
    facts = {"evidence": [{"value": 38.75}], "finding": "Reels averaged 41 saves"}
    ok, bad = guard.check("Reels average 41 saves, which will grow sales by 63%.", facts)
    assert not ok and "63" in bad


# ---------------- SQL validator ----------------
def test_sql_validator_allows_select_and_scopes_workspace():
    sql = ask.validate_sql("SELECT channel, sum(total) FROM orders o GROUP BY 1", "demo")
    assert "ws = 'demo'" in sql and sql.endswith("LIMIT 200")


@pytest.mark.parametrize("bad", ["DELETE FROM orders", "SELECT * FROM orders; DROP TABLE orders", "SELECT * FROM datasets",
                                 "SELECT * FROM read_csv('/etc/passwd')", "WITH x AS (SELECT 1) INSERT INTO orders SELECT * FROM x",
                                 "SELECT * FROM orders -- comment"])
def test_sql_validator_rejects(bad):
    with pytest.raises(ask.SQLRejected):
        ask.validate_sql(bad, "demo")


# ---------------- guardrails ----------------
def test_recommendation_guardrails():
    from app.insights.rules import passes_guardrails
    assert not passes_guardrails("Target ads at customers in chemotherapy treatment")
    assert not passes_guardrails("Segment buyers by treatment stage")
    assert passes_guardrails("Send a care-first email 30 days after purchase to everyone")


# ---------------- pipeline end to end ----------------
@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app
    c = TestClient(app)
    assert c.post("/api/demo/load").json()["ok"]
    return c


def test_demo_imports_every_file(client):
    ds = client.get("/api/datasets?ws=demo").json()["datasets"]
    assert len(ds) >= 13 and all(d["rows_imported"] > 0 for d in ds)


def test_reupload_does_not_duplicate(client):
    from app import db
    from app.ingest import pipeline
    before = db.one("SELECT count(*) FROM orders WHERE ws = 'demo'")
    res = pipeline.auto_import("pedidos_shopify_2026.csv", (DEMO / "pedidos_shopify_2026.csv").read_bytes(), "demo")[0]
    assert res["report"]["imported"] == 0 and res["report"]["duplicates"] > 0
    assert db.one("SELECT count(*) FROM orders WHERE ws = 'demo'") == before
    pipeline.undo(res["dataset_id"])


def test_european_file_parses_correctly(client):
    from app import db
    r = db.rows("SELECT total, date FROM orders WHERE ws = 'demo' AND order_id = (SELECT min(order_id) FROM orders WHERE ws='demo' AND year(date) = 2026)")
    assert r and 10 < r[0]["total"] < 500


def test_privacy_applied_no_emails_stored(client):
    from app import db
    assert db.one("SELECT count(*) FROM orders WHERE customer_id LIKE '%@%'") == 0
    assert db.one("SELECT count(*) FROM feedback WHERE text LIKE '%@example.com%'") == 0


def test_flexible_flow_and_insight(client):
    st = client.post("/api/upload", files={"files": ("mercadillo_ventas.csv", (DEMO / "mercadillo_ventas.csv").read_bytes())},
                     data={"ws": "demo"}).json()[0]
    t = st["tables"][0]
    assert t["flexible_suggested"]
    res = client.post("/api/import", json={"upload_id": st["upload_id"], "index": 0, "flexible": True, "ws": "demo"}).json()
    assert res["ok"] and res["flexible"]
    cfg = res["config"]
    value_col = next(c["column"] for c in cfg["columns"] if c["label"] == "Caja (€)")
    client.post(f"/api/datasets/{res['dataset_id']}/flex", json={"trend": {"date": cfg["suggestion"]["date"], "value": value_col,
                                                                            "label": "Market stalls", "value_label": "Caja (€)"}})
    ins = client.get("/api/home?ws=demo").json()["insights"]
    assert any(i["id"].startswith("flex_") for i in ins)
    assert client.post(f"/api/datasets/{res['dataset_id']}/undo").json()["ok"]


def test_home_top_insights_have_evidence(client):
    h = client.get("/api/home?ws=demo&range=90d").json()
    assert len(h["insights"]) >= 3 and all(i["evidence"] for i in h["insights"][:3])


def test_not_enough_data_message(client):
    h = client.get("/api/home?ws=mine").json()
    assert h["insights"] == [] and h["waiting"]


def test_add_to_plan_captures_baseline_and_review_computes_change(client):
    d = client.post("/api/decisions", json={"title": "Two Reels a week", "metric": "ig_saves", "ws": "demo"}).json()
    assert d["baseline"] is not None
    plan = client.get("/api/plan?ws=demo").json()
    past = next(x for x in plan["decisions"] if x["due"])
    r = client.post(f"/api/decisions/{past['id']}/review", json={"learning": "It helped", "ws": "demo"}).json()
    assert r["result_value"] is not None and r["change"] is not None


def test_ask_without_key(client):
    for q in ["Which products get the best reviews?", "When should we post?", "Why did sales dip in March?"]:
        a = client.post("/api/ask", json={"question": q, "ws": "demo"}).json()
        assert a["ok"] and a["chart"] and a["method"]


def test_briefing_exports(client):
    assert "<h1>" in client.get("/api/briefing?ws=demo&format=html").text
    assert client.get("/api/briefing?ws=demo&format=md").text.startswith("# Weekly briefing")


# ---------------- test pack regressions ----------------
def test_short_comments_with_numbers_are_not_feedback():
    df = pd.DataFrame({"Fecha": ["01/03/2025", "08/03/2025", "15/03/2025"] * 5, "Piezas": ["4", "14", "9"] * 5,
                       "Caja (€)": ["125,63", "396,38", "250,00"] * 5, "Comentario": ["Buen día", "Pidieron más colores", ""] * 5})
    assert classify(df, "ventas.csv")[0].confidence < 0.6


def test_empty_file_gets_friendly_message():
    from app.ingest import pipeline
    st = pipeline.stage("empty.csv", b"", "mine")
    assert "empty" in st["error"].lower()


def test_totals_row_is_dropped():
    grid = [["Informe"], [], ["Fecha", "Unidades"], ["01/10/2026", "3"], ["02/10/2026", "4"], ["TOTAL", "7"]]
    assert len(readers.grid_to_df(grid)) == 2


# ---------------- live connectors (mocked platform APIs, no real store needed) ----------------
import httpx  # noqa: E402

SHOPIFY_PAGE = {"data": {"orders": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "edges": [{"node": {
    "id": "gid://shopify/Order/1", "name": "#9001", "createdAt": "2026-11-20T10:15:00Z", "displayFinancialStatus": "PAID", "sourceName": "web",
    "note": "Es un regalo", "customAttributes": [], "customer": {"id": "gid://shopify/Customer/77"},
    "currentTotalPriceSet": {"shopMoney": {"amount": "68.00", "currencyCode": "EUR"}}, "subtotalPriceSet": {"shopMoney": {"amount": "68.00"}},
    "totalShippingPriceSet": {"shopMoney": {"amount": "0.00"}}, "totalDiscountsSet": {"shopMoney": {"amount": "0.00"}}, "discountCodes": [],
    "shippingAddress": {"city": "Girona", "countryCodeV2": "ES"},
    "lineItems": {"edges": [{"node": {"name": "Turbante Luna bambú - Arena", "quantity": 1, "sku": "IBB-BAM-101", "originalUnitPriceSet": {"shopMoney": {"amount": "39.00"}}}},
                            {"node": {"name": "Gorro Nube bambú - Gris perla", "quantity": 1, "sku": "IBB-BAM-104", "originalUnitPriceSet": {"shopMoney": {"amount": "29.00"}}}}]}}}]}}}
JUDGEME_PAGE = {"current_page": 1, "per_page": 100, "reviews": [
    {"id": 555, "title": "Precioso", "body": "Suavísimo y muy cómodo, me encanta.", "rating": 5, "product_title": "Turbante Luna bambú - Arena",
     "product_handle": "turbante-luna", "reviewer": {"id": 1, "email": "ana@example.com", "name": "Ana P"}, "source": "web", "curated": "ok",
     "hidden": False, "verified": "buyer", "created_at": "2026-11-19T09:00:00Z"},
    {"id": 556, "title": "Hidden", "body": "spam", "rating": 1, "hidden": True, "created_at": "2026-11-19T09:00:00Z", "reviewer": {}}]}


def mock_client(calls: list):
    def handler(req: httpx.Request):
        calls.append(req)
        if "myshopify.com" in req.url.host:
            assert req.headers["X-Shopify-Access-Token"] == "shpat_test_token_123"
            body = json.loads(req.content)
            return httpx.Response(200, json={"data": {"shop": {"name": "Test Shop"}}} if "shop {" in body["query"] else SHOPIFY_PAGE)
        assert req.headers["X-Api-Token"] == "jdgm_private_test_key"
        if req.method == "POST":
            return httpx.Response(200, json={})
        return httpx.Response(200, json=JUDGEME_PAGE)
    return httpx.Client(transport=httpx.MockTransport(handler))


import json  # noqa: E402


def test_shopify_and_judgeme_connect_sync_and_reply(client):
    from app import db
    from app.models import connectors
    calls: list = []
    c = mock_client(calls)
    assert connectors.connect("mine", "shopify", "test-shop", "shpat_test_token_123", c)["account"] == "Test Shop"
    assert connectors.sync("mine", "shopify", c)["status"] == "ok"
    o = db.rows("SELECT * FROM orders WHERE ws = 'mine' AND order_id = '#9001'")
    assert o and o[0]["total"] == 68.0 and o[0]["customer_id"].startswith("c_") and o[0]["is_gift"]
    # token is encrypted at rest and never stored in plain text
    raw = db.one("SELECT value FROM settings WHERE key = 'cred:mine:shopify'")
    assert "shpat_test_token_123" not in raw
    assert connectors.connect("mine", "judgeme", "test-shop.myshopify.com", "jdgm_private_test_key", c)["ok"]
    assert connectors.sync("mine", "judgeme", c)["status"] == "ok"
    r = db.rows("SELECT _key, platform, external_id, text FROM feedback WHERE ws = 'mine' AND external_id = '555'")
    assert r and r[0]["platform"] == "Judge.me" and db.one("SELECT count(*) FROM feedback WHERE external_id = '556'") == 0
    # replying goes through POST /replies with the Judge.me review id
    from app.analytics import voice
    res = voice.publish_reply("mine", r[0]["_key"], "¡Gracias Ana!", client=c)
    assert res["ok"], res
    post = [x for x in calls if x.method == "POST" and "/replies" in str(x.url)][-1]
    assert json.loads(post.content) == {"review_id": 555, "send_reply_email": False, "reply": {"content": "¡Gracias Ana!"}}
    assert db.one("SELECT reply_status FROM feedback WHERE _key = ?", [r[0]["_key"]]) == "published"


def test_bad_token_gives_friendly_error():
    from app.models import connectors
    c = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(401, json={})))
    with pytest.raises(connectors.ConnectorError, match="did not accept"):
        connectors.connect("mine", "shopify", "x.myshopify.com", "shpat_wrong_token_000", c)


def test_example_reviews_are_labelled():
    from app.analytics import voice
    ex = voice.examples()
    assert ex["items"] and all(i["example"] for i in ex["items"]) and "made-up" in ex["note"]
