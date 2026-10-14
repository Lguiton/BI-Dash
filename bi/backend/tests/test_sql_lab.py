import pytest

from app.services import sql_lab


def run(client, sql):
    return client.post("/api/sql/run", json={"sql": sql})


def test_select_runs_and_serializes(client):
    r = run(client, "SELECT record_date, revenue, status FROM fact_operations ORDER BY record_date LIMIT 2")
    assert r.status_code == 200
    j = r.json()
    assert j["columns"] == ["record_date", "revenue", "status"]
    assert j["rows"][0] == ["2026-10-01", 450.0, "Completed"] and j["row_count"] == 2 and not j["truncated"]


@pytest.mark.parametrize("sql", [
    "DELETE FROM fact_operations", "DROP TABLE fact_operations", "INSERT INTO dim_entities VALUES ('X','x','y',1)",
    "UPDATE fact_operations SET revenue = 0", "CREATE TABLE z AS SELECT 1", "ATTACH '/tmp/x.db'",
    "COPY fact_operations TO '/tmp/x.csv'", "INSTALL httpfs", "SET enable_external_access = true",
    "PRAGMA database_size; DELETE FROM fact_operations", "SELECT 1; DELETE FROM fact_operations",
    "EXPLAIN ANALYZE DELETE FROM fact_operations", "EXPLAIN ANALYZE UPDATE fact_operations SET revenue = 0",
])
def test_writes_and_dangerous_statements_are_blocked(client, sql):
    r = run(client, sql)
    assert r.status_code == 400
    assert client.get("/api/analytics/summary").json()["record_count"] == 6  # data intact


def test_file_and_network_access_is_blocked(client):
    for sql in ["SELECT * FROM read_csv('/etc/passwd')", "SELECT * FROM read_text('/etc/hostname')",
                "SELECT * FROM glob('/*')", "SELECT * FROM read_parquet('https://example.com/x.parquet')"]:
        r = run(client, sql)
        assert r.status_code == 400, sql
        assert "disabled" in r.json()["detail"].lower() or "permission" in r.json()["detail"].lower() or "not" in r.json()["detail"].lower()


def test_allowed_read_only_forms(client):
    for sql in ["DESCRIBE fact_operations", "SUMMARIZE dim_entities", "EXPLAIN SELECT * FROM fact_operations",
                "WITH x AS (SELECT 1 AS a) SELECT * FROM x", "FROM dim_entities", "VALUES (1),(2)"]:
        assert run(client, sql).status_code == 200, sql


def test_errors_are_readable(client):
    r = run(client, "SELEC * FROM fact_operations")
    assert r.status_code == 400 and "syntax" in r.json()["detail"].lower()
    r = run(client, "SELECT nope FROM fact_operations")
    assert r.status_code == 400 and "nope" in r.json()["detail"]
    assert run(client, "   ").status_code == 400


def test_row_cap_and_truncation(client):
    j = run(client, "SELECT * FROM range(5000)").json()
    assert j["row_count"] == sql_lab.MAX_ROWS and j["truncated"] is True


def test_timeout_cancels_runaway_query(client, monkeypatch):
    monkeypatch.setattr(sql_lab, "TIMEOUT_SECONDS", 0.5)
    r = run(client, "SELECT COUNT(*) FROM range(3000000000) a, range(1000) b")
    assert r.status_code == 400 and "cancelled" in r.json()["detail"].lower()
    assert run(client, "SELECT 1").status_code == 200  # engine still healthy afterwards


def test_schema(client):
    objs = {o["name"]: o for o in client.get("/api/sql/schema").json()["objects"]}
    assert {"fact_operations", "dim_entities", "dim_date", "v_operations_flat"} <= set(objs)
    assert "app_meta" not in objs
    assert objs["fact_operations"]["kind"] == "table" and objs["fact_operations"]["row_count"] == 6
    assert objs["dim_date"]["kind"] == "view"
    assert {"name": "revenue", "type": "DOUBLE"} in objs["fact_operations"]["columns"]


def test_every_reference_solution_runs_and_passes_its_own_check(client):
    exs = client.get("/api/sql/exercises").json()["exercises"]
    assert len(exs) >= 15 and all("solution" not in e for e in exs)  # solutions are not leaked in the list
    for e in exs:
        sol = client.get(f"/api/sql/exercises/{e['id']}/solution").json()["solution"]
        r = client.post(f"/api/sql/exercises/{e['id']}/check", json={"sql": sol})
        assert r.status_code == 200 and r.json()["correct"] is True, e["id"]


def test_check_feedback(client):
    chk = lambda i, sql: client.post(f"/api/sql/exercises/{i}/check", json={"sql": sql}).json()
    # alias / formatting differences don't matter
    assert chk("status-counts", "SELECT status AS s, COUNT(*) AS n FROM fact_operations GROUP BY 1")["correct"]
    # wrong shape
    assert "column" in chk("status-counts", "SELECT status FROM fact_operations GROUP BY 1")["message"]
    assert "row" in chk("top-days", "SELECT record_date, SUM(revenue) FROM fact_operations GROUP BY 1 ORDER BY 2 DESC LIMIT 2")["message"]
    # right rows, wrong order
    m = chk("top-days", "SELECT record_date, SUM(revenue) r FROM fact_operations GROUP BY 1 ORDER BY 2 ASC LIMIT 3")
    assert not m["correct"]
    # wrong values
    assert not chk("totals", "SELECT SUM(revenue), SUM(operational_cost), SUM(revenue) FROM fact_operations")["correct"]
    # unsafe input is refused, not graded
    assert client.post("/api/sql/exercises/totals/check", json={"sql": "DELETE FROM fact_operations"}).status_code == 400
    assert client.post("/api/sql/exercises/nope/check", json={"sql": "SELECT 1"}).status_code == 404


def test_exercises_also_work_on_larger_data(client):
    """Reference solutions must hold up on the realistic 10-entity year, not just the 6-row demo."""
    import csv, io
    from conftest import csv_file
    from test_sample_data import _load
    from datetime import date
    gen = _load()
    rows = gen.generate(200, date(2026, 10, 6), 42)
    buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=gen.HEADER); w.writeheader(); w.writerows(rows)
    assert client.post("/api/ingest/csv", params={"mode": "replace"}, files=csv_file(buf.getvalue())).status_code == 200
    for e in client.get("/api/sql/exercises").json()["exercises"]:
        sol = client.get(f"/api/sql/exercises/{e['id']}/solution").json()["solution"]
        r = client.post(f"/api/sql/exercises/{e['id']}/check", json={"sql": sol})
        assert r.status_code == 200 and r.json()["correct"], e["id"]
    # the budget exercise should surface the entities the generator built to run over budget
    sol = client.get("/api/sql/exercises/budget/solution").json()["solution"]
    names = [r[0] for r in client.post("/api/sql/run", json={"sql": sol}).json()["rows"]]
    assert "Downtown Corridor" in names and names[0] == "Downtown Corridor"


def test_non_additive_exercise_rejects_the_averaged_ratio(client):
    """The classic mistake (average of per-row margins) must NOT pass; the ratio of sums must."""
    wrong = ("SELECT e.category, AVG((f.revenue - f.operational_cost) / f.revenue) * 100 "
             "FROM fact_operations f JOIN dim_entities e ON f.entity_id = e.entity_id GROUP BY e.category")
    r = client.post("/api/sql/exercises/non-additive/check", json={"sql": wrong}).json()
    assert r["correct"] is False and "values differ" in r["message"]
