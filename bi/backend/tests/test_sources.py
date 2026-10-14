import http.server
import socketserver
import sqlite3
import threading

import pytest

from tests.conftest import csv_file

CSV1 = "day,sales\n2026-01-01,10\n2026-01-02,12\n2026-01-03,9\n2026-01-04,15\n"


@pytest.fixture()
def web():
    body = {"data": CSV1.encode()}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/boom":
                self.send_response(500); self.end_headers(); return
            self.send_response(200); self.send_header("Content-Type", "text/csv"); self.end_headers(); self.wfile.write(body["data"])

        def log_message(self, *a):
            pass

    srv = socketserver.TCPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", body
    srv.shutdown()


def test_url_source_refresh_and_shrink_guard(client, web):
    url, body = web
    r = client.post("/api/sources", json={"name": "Daily sales", "kind": "url", "config": {"url": url + "/s.csv"}, "target": "daily_sales", "interval_minutes": 60})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    assert client.post(f"/api/sources/{sid}/run").json()["rows"] == 4
    assert client.get("/api/data/tables").json()["tables"][0]["rows_count"] == 4
    body["data"] = b"day,sales\n2026-01-05,1\n"        # a broken export: 1 row instead of 4
    bad = client.post(f"/api/sources/{sid}/run")
    assert bad.status_code == 422 and "Refusing" in bad.json()["detail"]
    assert client.get("/api/data/tables").json()["tables"][0]["rows_count"] == 4     # untouched
    s = client.get("/api/sources").json()["sources"][0]
    assert s["last_status"] == "error"
    assert [x["ok"] for x in client.get(f"/api/sources/{sid}/runs").json()["runs"]] == [0, 1]
    body["data"] = CSV1.encode() + b"2026-01-05,20\n"
    assert client.post(f"/api/sources/{sid}/run").json()["rows"] == 5


def test_http_error_is_recorded_not_raised_to_scheduler(client, web):
    url, _ = web
    sid = client.post("/api/sources", json={"name": "x", "kind": "url", "config": {"url": url + "/boom"}, "target": "t"}).json()["id"]
    r = client.post(f"/api/sources/{sid}/run")
    assert r.status_code == 422 and "500" in r.json()["detail"]


def test_file_source_and_path_confinement(client, tmp_path, monkeypatch):
    inbox = tmp_path / "inbox"; inbox.mkdir()
    (inbox / "a.csv").write_text(CSV1)
    (tmp_path / "secret.csv").write_text("x\n1\n")
    ok = client.post("/api/sources", json={"name": "inbox file", "kind": "file", "config": {"path": "a.csv"}, "target": "from_inbox"})
    assert ok.status_code == 200, ok.text
    assert client.post(f"/api/sources/{ok.json()['id']}/run").json()["rows"] == 4
    for evil in ("../secret.csv", str(tmp_path / "secret.csv"), "/etc/passwd"):
        assert client.post("/api/sources", json={"name": "evil", "kind": "file", "config": {"path": evil}, "target": "t"}).status_code in (400, 404)
    assert any(f["name"] == "a.csv" for f in client.get("/api/sources/files").json()["files"])


def test_sqlite_source_is_read_only(client, tmp_path):
    inbox = tmp_path / "inbox"; inbox.mkdir()
    con = sqlite3.connect(inbox / "shop.sqlite"); con.execute("create table o(id int, amt real)"); con.executemany("insert into o values (?,?)", [(1, 5.5), (2, 7)]); con.commit(); con.close()
    cfg = {"driver": "sqlite", "path": "shop.sqlite", "query": "select * from o"}
    r = client.post("/api/sources", json={"name": "shop", "kind": "sql", "config": cfg, "target": "orders"})
    assert client.post(f"/api/sources/{r.json()['id']}/run").json()["rows"] == 2
    for q in ("delete from o", "select 1; drop table o", "update o set amt=0"):
        assert client.post("/api/sources", json={"name": "w", "kind": "sql", "config": {**cfg, "query": q}, "target": "t"}).status_code == 400


def test_bad_inputs_rejected(client):
    assert client.post("/api/sources", json={"name": "u", "kind": "url", "config": {"url": "file:///etc/passwd"}, "target": "t"}).status_code == 400
    assert client.post("/api/sources", json={"name": "u", "kind": "url", "config": {"url": "https://x.test", "auth_env": "not a var"}, "target": "t"}).status_code == 400
    assert client.post("/api/sources", json={"name": "u", "kind": "url", "config": {"url": "https://x.test"}, "target": "t", "interval_minutes": 1}).status_code == 400
    assert client.post("/api/sources", json={"name": "p", "kind": "sql", "config": {"driver": "postgres", "dsn_env": "postgres://user:pw@h/db", "query": "select 1"}, "target": "t"}).status_code == 400


def test_operations_source_and_due(client, web):
    url, body = web
    body["data"] = b"record_date,entity_id,revenue,operational_cost,units_processed\n2026-05-01,A,100,40,3\n2026-05-02,A,120,50,4\n2026-05-03,A,1,1,1\n2026-05-04,A,1,1,1\n"
    sid = client.post("/api/sources", json={"name": "ops", "kind": "url", "config": {"url": url + "/o.csv"}, "load": "operations", "mode": "replace", "interval_minutes": 5}).json()["id"]
    from app.services import sources
    assert [s["id"] for s in sources.due()] == [sid]
    assert client.post(f"/api/sources/{sid}/run").json()["rows"] == 4
    assert sources.due() == []
    assert client.patch(f"/api/sources/{sid}", json={"enabled": False}).json()["enabled"] is False
    assert client.delete(f"/api/sources/{sid}").status_code == 200


def test_source_scoped_to_workspace(client, web):
    url, _ = web
    sid = client.post("/api/sources", json={"name": "p", "kind": "url", "config": {"url": url}, "target": "t"}).json()["id"]
    client.post("/api/workspaces/active", json={"name": "real"})
    assert client.get("/api/sources").json()["sources"] == []
    assert client.post(f"/api/sources/{sid}/run").status_code == 409


def test_postgres_source(client, monkeypatch):
    import os
    pytest.importorskip("psycopg")
    dsn = os.environ.get("BI_TEST_PG_URL")
    if not dsn:
        pytest.skip("set BI_TEST_PG_URL to run the Postgres connector test")
    monkeypatch.setenv("PG_URL", dsn)
    cfg = {"driver": "postgres", "dsn_env": "PG_URL", "query": "select generate_series(1,5) as n, 'x' as label"}
    sid = client.post("/api/sources", json={"name": "pg", "kind": "sql", "config": cfg, "target": "pg_t"}).json()["id"]
    assert client.post(f"/api/sources/{sid}/run").json()["rows"] == 5
    cfg["query"] = "insert into x values (1)"
    assert client.post("/api/sources", json={"name": "w", "kind": "sql", "config": cfg, "target": "t"}).status_code == 400
