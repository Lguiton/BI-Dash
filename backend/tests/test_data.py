import io

from tests.conftest import csv_file

SAAS = "tier,active_users,mrr,churn_rate\nFree,1200,0,0.08\nPro,340,\"$4,200.50\",0.03\nTeam,90,7800,0.02\nEnterprise,12,15000,0.01\n"


def test_import_profile_and_charts(client):
    r = client.post("/api/data/import", files=csv_file(SAAS, "saas_metrics.csv"), data={"mode": "replace"})
    assert r.status_code == 200, r.text
    assert r.json()["table"] == "saas_metrics" and r.json()["rows"] == 4
    types = {c["name"]: c["type"] for c in r.json()["columns"]}
    assert types["mrr"] == "DOUBLE" and types["active_users"] == "BIGINT"
    prof = client.get("/api/data/tables/saas_metrics/profile").json()
    assert prof["rows"] == 4
    assert client.get("/api/data/tables").json()["tables"][0]["table_name"] == "saas_metrics"
    agg = client.get("/api/data/tables/saas_metrics/chart", params={"kind": "aggregate", "x": "tier", "y": "mrr", "agg": "sum"}).json()
    assert agg["data"][0]["x"] == "Enterprise"
    h = client.get("/api/data/tables/saas_metrics/chart", params={"kind": "histogram", "x": "active_users", "bins": 5}).json()
    assert sum(b["count"] for b in h["bins"]) == 4
    b = client.get("/api/data/tables/saas_metrics/chart", params={"kind": "box", "x": "mrr"}).json()
    assert b["boxes"][0]["n"] == 4
    s = client.get("/api/data/tables/saas_metrics/chart", params={"kind": "scatter", "x": "active_users", "y": "mrr"}).json()
    assert s["n"] == 4


def test_identifiers_are_not_injectable(client):
    client.post("/api/data/import", files=csv_file(SAAS, "saas_metrics.csv"))
    r = client.get("/api/data/tables/saas_metrics/chart", params={"kind": "aggregate", "x": 'tier"; DROP TABLE fact_operations; --', "y": "mrr"})
    assert r.status_code == 400
    assert client.get("/api/data/tables/fact_operations/profile").status_code == 404   # built-ins are not reachable here
    assert client.get("/api/analytics/summary").status_code == 200


def test_types_dates_and_leading_zero_codes(client):
    text = "zip,d,flag,n\n02134,2026-01-05,true,1\n10001,2026-02-10,false,\n"
    client.post("/api/data/import", files=csv_file(text, "t.csv"))
    cols = {c["name"]: c["type"] for c in client.get("/api/data/tables").json()["tables"][0]["columns"]}
    assert cols == {"zip": "VARCHAR", "d": "DATE", "flag": "BOOLEAN", "n": "BIGINT"}
    agg = client.get("/api/data/tables/t/chart", params={"x": "d", "y": "n", "bucket": "month"}).json()
    assert [r["x"] for r in agg["data"]] == ["2026-01-01", "2026-02-01"]


def test_semicolon_and_append_mismatch(client):
    client.post("/api/data/import", files=csv_file("a;b\n1;2\n3;4\n", "s.csv"))
    r = client.post("/api/data/import", files=csv_file("a,c\n1,2\n", "s.csv"), data={"mode": "append"})
    assert r.status_code == 400
    r = client.post("/api/data/import", files=csv_file("a;b\n5;6\n", "s.csv"), data={"mode": "append"})
    assert r.json()["rows"] == 3


def test_builtin_name_protected_and_delete(client):
    r = client.post("/api/data/import", files=csv_file("a\n1\n", "fact_operations.csv"))
    assert r.json()["table"] == "my_fact_operations"
    assert client.delete("/api/data/tables/my_fact_operations").status_code == 200
    assert client.delete("/api/data/tables/dim_entities").status_code == 404


def test_excel_import(client):
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active
    ws.append(["Month", "Sales"]); ws.append(["2026-01-01", 10]); ws.append(["2026-02-01", 12.5])
    buf = io.BytesIO(); wb.save(buf)
    r = client.post("/api/data/import", files={"file": ("sales.xlsx", buf.getvalue(), "application/octet-stream")})
    assert r.status_code == 200 and r.json()["rows"] == 2


def test_map_operations_with_defaults(client):
    r = client.post("/api/data/map-operations", files=csv_file("when,sales,spend\n2026-03-01,100,40\n2026-03-02,120,50\n", "x.csv"),
                    data={"mapping": '{"record_date":"when","revenue":"sales","operational_cost":"spend"}',
                          "defaults": '{"entity_id":"ALL","units_processed":"1"}', "mode": "replace"})
    assert r.status_code == 200, r.text
    assert r.json()["rows_loaded"] == 2
    assert client.get("/api/analytics/summary").status_code == 200
    bad = client.post("/api/data/map-operations", files=csv_file("a\n1\n", "x.csv"), data={"mapping": "{}"})
    assert bad.status_code == 400


def test_workspaces_isolated(client):
    client.post("/api/data/import", files=csv_file(SAAS, "saas_metrics.csv"))
    assert client.post("/api/workspaces/active", json={"name": "real"}).json()["active"] == "real"
    assert client.get("/api/data/tables").json()["tables"] == []
    assert client.get("/api/analytics/summary").status_code == 200
    ws = client.get("/api/workspaces").json()
    assert next(w for w in ws["workspaces"] if w["name"] == "real")["settings"]["ai_mode"] == "off"
    client.post("/api/workspaces/active", json={"name": "practice"})
    assert len(client.get("/api/data/tables").json()["tables"]) == 1
    assert client.put("/api/workspaces/real/settings", json={"ai_mode": "bogus"}).status_code == 400


def test_old_study_state_migrates_once(tmp_path, monkeypatch):
    import duckdb
    from app.services import db, state, study, workspaces
    path = tmp_path / "old.duckdb"
    c = duckdb.connect(str(path))
    c.execute("CREATE TABLE study_progress(item_id VARCHAR PRIMARY KEY, done_at TIMESTAMP)")
    c.execute("INSERT INTO study_progress VALUES ('a','2026-09-01 10:00:00')")
    c.close()
    monkeypatch.setenv("BI_DB_PATH", str(path)); monkeypatch.setenv("BI_SCHEDULER", "0")
    db.close_connection(); state.close_all()
    workspaces.startup(); workspaces.startup()
    assert list(study.done_items()) == ["a"]
    db.close_connection(); state.close_all()
