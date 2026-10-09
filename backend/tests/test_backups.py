from tests.conftest import csv_file


def test_backup_restore_roundtrip(client):
    before = client.get("/api/analytics/summary").json()
    b = client.post("/api/backups", json={"note": "first"}).json()
    assert b["name"].endswith("_first.duckdb")
    client.post("/api/ingest/csv?mode=replace", files=csv_file("record_date,entity_id,revenue,operational_cost,units_processed\n2026-05-01,Z,1,1,1\n"))
    assert client.get("/api/analytics/summary").json() != before
    r = client.post("/api/backups/restore", json={"name": b["name"]})
    assert r.status_code == 200, r.text
    assert client.get("/api/analytics/summary").json() == before
    kinds = [x["kind"] for x in client.get("/api/backups").json()["backups"]]
    assert "safety-before-restore" in kinds              # the restore itself can be undone


def test_real_gets_safety_backup_before_replace(client):
    client.post("/api/workspaces/active", json={"name": "real"})
    ok = "record_date,entity_id,revenue,operational_cost,units_processed\n2026-05-01,Z,1,1,1\n"
    client.post("/api/ingest/csv?mode=append", files=csv_file(ok))
    client.post("/api/ingest/csv?mode=replace", files=csv_file(ok))
    names = [b["kind"] for b in client.get("/api/backups").json()["backups"]]
    assert "safety-before-replace-import" in names
    client.post("/api/workspaces/active", json={"name": "practice"})
    client.post("/api/ingest/csv?mode=replace", files=csv_file(ok))
    assert client.get("/api/backups").json()["backups"] == []     # practice is meant to be broken: no safety copies


def test_backup_names_validated_and_pruned(client):
    assert client.post("/api/backups/restore", json={"name": "../../etc/passwd"}).status_code == 404
    assert client.get("/api/backups/..%2Fx/download").status_code == 404
    client.put("/api/workspaces/practice/settings", json={"backup_keep": 2})
    for i in range(4):
        client.post("/api/backups", json={"note": f"n{i}"})
    assert len(client.get("/api/backups").json()["backups"]) == 2


def test_audit_log_records_actions(client):
    client.post("/api/data/import", files=csv_file("a\n1\n", "t.csv"))
    client.post("/api/data/import", files=csv_file("", "empty.csv"))
    client.post("/api/workspaces/active", json={"name": "real"})
    e = client.get("/api/audit").json()
    acts = [x["action"] for x in e["entries"]]
    assert "import_table" in acts and "workspace_switch" in acts
    assert any(not x["ok"] for x in e["entries"])
    assert client.get("/api/audit", params={"workspace": "real"}).json()["entries"][0]["workspace"] == "real"
