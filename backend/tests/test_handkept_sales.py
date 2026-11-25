"""A sales log kept by hand in Excel: no order numbers, a 'Cliente' column with names, mixed price formats."""
import pandas as pd

from app.ingest.classify import classify
from app.ingest.parsing import number_series
from app.ingest.transform import Report, to_orders
from app.privacy import pii

DF = pd.DataFrame({
    "Fecha": ["03/11/2026", "04/11/2026", "09/11/2026", "10/11/2026", "13/11/2026"],
    "Producto": ["Pañuelo multi-tie", "Gorro de dormir", "Turbante", "Pañuelo multi-tie", "Turbante"],
    "Cliente": ["Marta G.", "Laura Pérez", "Ana López", "Camille", "Elena V."],
    "Unidades": ["2", "1", "1", "4", "2"],
    "Precio unitario": ["€ 28,00", "€35", "€24.50", "28,00", "24,50 €"],
    "Importe": ["€ 56,00", "€ 35,00", "24,50 €", "112,00", "49,00 €"],
})


def test_recognised_as_sales_without_order_numbers():
    best = classify(DF, "ventas_noviembre.xlsx")[0]
    assert best.table_type == "orders" and best.confidence >= 0.6
    assert not best.missing_required


def test_mixed_decimal_styles_in_one_column():
    assert list(number_series(DF["Precio unitario"])) == [28.0, 35.0, 24.5, 28.0, 24.5]
    assert list(number_series(pd.Series(["1.234,50 €", "2.000", "12,5"]))) == [1234.5, 2000.0, 12.5]


def test_customer_names_are_dropped():
    mapping = classify(DF, "ventas_noviembre.xlsx")[0].mapping
    found = {p["column"]: p for p in pii.detect(DF, mapping)}
    assert found["Cliente"]["kind"] == "name" and found["Cliente"]["action"] == "drop"
    clean = pii.apply(DF, list(found.values()))
    assert "Cliente" not in clean.columns


def test_customer_ids_are_not_treated_as_names():
    ids = pd.DataFrame({"Customer": ["c_101", "c_102", "c_103"]})
    assert not pii.detect(ids, {})


def test_each_row_becomes_one_sale_and_reimport_matches():
    best = classify(DF, "ventas_noviembre.xlsx")[0]
    m = {k: v for k, v in best.mapping.items() if v["column"] != "Cliente"}
    clean = DF.drop(columns=["Cliente"])
    r1, r2 = Report(), Report()
    a = to_orders(clean, m, r1, 2)["orders"]
    b = to_orders(clean, m, r2, 2)["orders"]
    assert len(a) == 5 and round(a["total"].sum(), 2) == 276.5
    assert list(a["_key"]) == list(b["_key"])  # same file again is recognised as duplicates
    assert any("no order number" in n for n in r1.notes)


def test_explain_says_why_nothing_is_shown():
    from app.ingest.explain import explain
    no_dates = {"id": "x", "rows_imported": 12, "flexible": True, "table_type": "flexible", "report": {},
                "flex_config": {"columns": [{"column": "nombre", "type": "category"}, {"column": "importe", "type": "number"}]}}
    e = explain(no_dates)
    assert e["status"] == "not_shown" and any("dates" in r for r in e["reasons"]) and e["fixes"]
    empty = {"id": "y", "rows_imported": 0, "report": {"issues": [{"row": 3, "problem": "Order without a readable date or total"}]}}
    e = explain(empty)
    assert e["status"] == "not_shown" and "row 3" in " ".join(e["reasons"])
    charted = {**no_dates, "flex_config": {**no_dates["flex_config"], "trend": {"date": "d", "value": "importe"}}}
    assert explain(charted)["shown_on"][0]["path"] == "/sales"
