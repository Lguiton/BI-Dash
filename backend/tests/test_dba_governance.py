from app.services import db
from tests.conftest import csv_file

PEOPLE = ("customer_name,email,phone,ssn,card,notes\n"
          "Ann Lee,ann@example.com,702-555-0101,123-45-6789,4111111111111111,vip\n"
          "Bo Chan,bo@example.org,(702) 555-0102,987-65-4321,5500005555555559,\n"
          "Cy Diaz,cy@example.net,702.555.0103,111-22-3333,4012888888881881,new\n")


def test_health_reports_tables_constraints_and_integrity(client):
    h = client.get("/api/dba/health").json()
    t = {x["name"]: x for x in h["tables"]}
    assert t["fact_operations"]["rows"] == 6 and t["fact_operations"]["has_pk"] and "DuckDB" in h["engine"]
    assert any(c["table"] == "fact_operations" and c["type"] == "PRIMARY KEY" for c in h["constraints"])
    assert all(c["ok"] for c in h["integrity"]) and h["file"]["size_bytes"] > 0
    assert any("no backups" in f["text"] for f in h["findings"])           # none taken yet
    assert len(client.get("/api/dba/health").json()["growth"]) == 1       # snapshots are rate limited to one per hour


def test_integrity_catches_orphans_and_the_finding_is_high(client):
    with db.get_cursor() as cur:
        cur.execute("INSERT INTO fact_operations VALUES ('F-ORPHAN', '2026-10-07', 'NOPE', 1, 1, 1, 1, 'Completed')")
    h = client.get("/api/dba/health").json()
    bad = [c for c in h["integrity"] if not c["ok"]]
    assert [c["name"] for c in bad] == ["Every record points to a real entity"] and "1 orphan" in bad[0]["detail"]
    assert any(f["level"] == "high" and "orphan" in f["text"] for f in h["findings"])


def test_benchmarks_and_checkpoint(client):
    b = client.get("/api/dba/benchmarks").json()
    assert len(b["queries"]) == 6 and all(q["median_ms"] >= 0 and q["plan"] and len(q["runs_ms"]) == 3 for q in b["queries"])
    c = client.post("/api/dba/checkpoint").json()
    assert c["after_bytes"] > 0
    assert any(e["action"] == "dba_checkpoint" for e in client.get("/api/audit").json()["entries"])


def test_verify_backup_opens_a_copy_and_compares(client):
    assert client.post("/api/dba/verify-backup", json={}).status_code == 404
    client.post("/api/backups", json={"note": "v"})
    v = client.post("/api/dba/verify-backup", json={}).json()
    assert v["ok"] and v["matches_live"] and v["counts"]["fact_operations"] == {"backup": 6, "live": 6} and v["tables"] >= 3
    client.post("/api/ingest/csv?mode=replace", files=csv_file("record_date,entity_id,revenue,operational_cost,units_processed\n2026-05-01,Z,1,1,1\n"))
    v2 = client.post("/api/dba/verify-backup", json={}).json()
    assert v2["ok"] and not v2["matches_live"]
    assert client.post("/api/dba/verify-backup", json={"name": "20200101-000000_x.duckdb"}).status_code == 404


def test_corrupt_backup_is_reported_not_trusted(client):
    b = client.post("/api/backups", json={"note": "bad"}).json()
    from app.config import backups_dir
    (backups_dir() / "practice" / b["name"]).write_bytes(b"this is not a database")
    v = client.post("/api/dba/verify-backup", json={"name": b["name"]}).json()
    assert v["ok"] is False and "Do not rely" in v["message"]


def test_pii_scan_finds_personal_data_without_returning_values(client):
    client.post("/api/data/import", files=csv_file(PEOPLE, "people.csv"))
    r = client.get("/api/governance/pii-scan")
    found = {(f["column"], f["category"]): f for f in r.json()["findings"]}
    assert ("email", "email") in found and found[("email", "email")]["confidence"] == "high"
    assert ("ssn", "national id") in found and ("card", "card number") in found and ("phone", "phone") in found and ("customer_name", "person name") in found
    assert "notes" not in {c for c, _ in found}
    body = r.text
    for secret in ("ann@example.com", "123-45-6789", "4111111111111111", "702-555-0101"):
        assert secret not in body
    assert not any(f["table"] in ("fact_operations", "dim_entities") for f in r.json()["findings"])     # entity "name" is not a person


def test_protect_blocks_the_ai_for_real(client):
    client.post("/api/data/import", files=csv_file(PEOPLE, "people.csv"))
    assert client.post("/api/governance/protect", json={"columns": ["nope"]}).status_code == 404
    assert client.post("/api/governance/protect", json={"columns": ["email", "ssn"]}).json()["blocked_columns"] == ["email", "ssn"]
    assert client.get("/api/governance/pii-scan").json()["unprotected"] == 3         # phone, card, customer_name still open
    from app.services import ai_agent
    out, err = ai_agent._run_tool("run_sql", {"sql": "SELECT email FROM people"})
    assert err and "blocked" in out


def test_catalog_classification_and_retention(client):
    client.post("/api/data/import", files=csv_file(PEOPLE, "people.csv"))
    c = {a["name"]: a for a in client.get("/api/governance/catalog").json()["assets"]}
    assert c["people"]["suggested_classification"] == "confidential" and c["people"]["completeness_pct"] == round(100 * 17 / 18, 1)
    assert c["fact_operations"]["completeness_pct"] == 100.0 and c["fact_operations"]["duplicate_rows"] == 0
    assert client.put("/api/governance/assets/people", json={"classification": "secret"}).status_code == 400
    assert client.put("/api/governance/assets/people", json={"retention_days": 30}).status_code == 400                     # needs a column
    assert client.put("/api/governance/assets/fact_operations", json={"retention_days": 30, "retention_column": "revenue"}).status_code == 400
    assert client.put("/api/governance/assets/nope", json={}).status_code == 404
    ok = client.put("/api/governance/assets/fact_operations", json={"owner": "Lam", "classification": "internal", "retention_days": 1, "retention_column": "record_date"})
    assert ok.status_code == 200
    f = {a["name"]: a for a in client.get("/api/governance/catalog").json()["assets"]}["fact_operations"]
    assert f["owner"] == "Lam" and f["retention_eligible_rows"] == 6       # all six seed rows are dated before yesterday
    client.put("/api/governance/assets/fact_operations", json={"classification": "internal", "retention_days": 36500, "retention_column": "record_date"})
    f = {a["name"]: a for a in client.get("/api/governance/catalog").json()["assets"]}["fact_operations"]
    assert f["retention_eligible_rows"] == 0


def test_controls_lineage_and_access(client):
    client.post("/api/data/import", files=csv_file(PEOPLE, "people.csv"))
    ctl = client.get("/api/governance/controls").json()
    by = {c["id"]: c for c in ctl["controls"]}
    assert not by["pii_ai"]["ok"] and not by["owners"]["ok"] and not by["backup"]["ok"] and by["audit"]["ok"]
    client.post("/api/governance/protect", json={"columns": ["email", "phone", "ssn", "card", "customer_name"]})
    client.post("/api/backups", json={"note": "g"})
    by = {c["id"]: c for c in client.get("/api/governance/controls").json()["controls"]}
    assert by["pii_ai"]["ok"] and by["backup"]["ok"]
    lin = client.get("/api/governance/lineage").json()
    assert {"from": "fact_operations", "to": "v_operations_flat", "kind": "view reads table"} in lin["edges"]
    assert any(e["from"] == "upload" and e["to"] == "people" for e in lin["edges"])
    client.get("/api/export/operations?format=csv")
    acc = client.get("/api/governance/access").json()
    assert any(r["action"] == "export" for r in acc["data_leaving"]) and acc["ai"]["blocked_columns"]


def test_real_workspace_is_separate(client):
    client.post("/api/data/import", files=csv_file(PEOPLE, "people.csv"))
    client.post("/api/workspaces/active", json={"name": "real"})
    assert client.get("/api/governance/pii-scan").json()["findings"] == []
    assert client.get("/api/dba/health").json()["workspace"] == "real"
