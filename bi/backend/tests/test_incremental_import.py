from tests.conftest import csv_file

BASE = "id,day,amount\n1,2025-01-01,10\n2,2025-01-02,20\n3,2025-01-03,30\n"


def _import(client, text, **data):
    return client.post("/api/data/import", files=csv_file(text, "orders.csv"), data=data)


def test_append_new_by_key_skips_existing_and_duplicates(client):
    assert _import(client, BASE, mode="replace").status_code == 200
    more = "id,day,amount\n2,2025-01-02,20\n3,2025-01-03,30\n4,2025-01-04,40\n4,2025-01-04,40\n5,2025-01-05,50\n"
    r = _import(client, more, mode="append_new", key="id")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["added"] == 2 and j["rows"] == 5 and j["skipped_existing"] == 3
    again = _import(client, more, mode="append_new", key="id").json()
    assert again["added"] == 0 and again["rows"] == 5  # idempotent


def test_append_new_by_date(client):
    _import(client, BASE, mode="replace")
    r = _import(client, "id,day,amount\n3,2025-01-03,30\n4,2025-01-04,40\n", mode="append_new", date_column="day").json()
    assert r["added"] == 1 and r["rows"] == 4


def test_append_new_needs_rule_and_table(client):
    assert _import(client, BASE, mode="append_new", key="id").status_code == 400  # no table yet
    _import(client, BASE, mode="replace")
    assert _import(client, BASE, mode="append_new").status_code == 400  # no key or date
    assert _import(client, BASE, mode="append_new", key="id", date_column="day").status_code == 400
    assert _import(client, BASE, mode="append_new", key="nope").status_code == 400
    assert _import(client, "id,day,other\n9,2025-02-01,1\n", mode="append_new", key="id").status_code == 400  # columns differ


def test_schema_diff_on_preview_and_import(client):
    _import(client, BASE, mode="replace")
    changed = "id,day,amount,region\n1,2025-01-01,abc,N\n"
    pv = client.post("/api/data/preview", files=csv_file(changed, "orders.csv")).json()
    d = pv["schema_diff"]
    assert d and d["added"] == ["region"] and d["identical"] is False
    assert d["type_changed"] == [{"column": "amount", "was": "number", "now": "text"}]
    same = client.post("/api/data/preview", files=csv_file(BASE, "orders.csv")).json()["schema_diff"]
    assert same["identical"] is True
    new = client.post("/api/data/preview", files=csv_file(BASE, "brand_new.csv")).json()
    assert new["schema_diff"] is None
    res = _import(client, changed, mode="replace").json()
    assert res["schema_diff"]["removed"] == [] and res["schema_diff"]["added"] == ["region"]


def test_rescue_keeps_extra_columns_and_fills_missing(client):
    _import(client, BASE, mode="replace")
    plain = _import(client, "id,day,amount,coupon\n4,2025-01-04,40,SAVE5\n", mode="append")
    assert plain.status_code == 400  # without rescue the mismatch is refused
    r = _import(client, "id,day,amount,coupon\n4,2025-01-04,40,SAVE5\n5,2025-01-05,50,\n", mode="append", rescue="true")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["rescued_columns"] == ["coupon"] and j["rows"] == 5
    rows = client.get("/api/data/tables/orders/rows").json()
    text = str(rows)
    assert "SAVE5" in text and "_rescued" in text
    # a file that lacks a column still loads, with the gap left empty
    r2 = _import(client, "id,day\n6,2025-01-06\n", mode="append", rescue="true")
    assert r2.status_code == 200, r2.text
    assert r2.json()["rows"] == 6
