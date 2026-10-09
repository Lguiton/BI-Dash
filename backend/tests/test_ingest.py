from conftest import csv_file

GOOD = (
    "record_date,entity_id,entity_name,category,revenue,operational_cost,units_processed,duration_minutes,status\n"
    "2026-11-01,Z-1,Alpha,Express,100,40,10,60,Completed\n"
    "2026-11-02,Z-1,Alpha,Express,\"$1,200.50\",300,20,70,Completed\n"
    "11/03/2026,Z-2,Beta,Fleet,50,20,5,,Delayed\n"
)


def count(client):
    return client.get("/api/analytics/summary").json()["record_count"]


def test_append_loads_and_is_idempotent(client):
    r = client.post("/api/ingest/csv", files=csv_file(GOOD))
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["rows_loaded"] == 3 and j["rows_new"] == 3 and j["entities_created"] == 2
    assert j["date_min"] == "2026-11-01" and j["date_max"] == "2026-11-03"
    assert count(client) == 9  # 6 demo + 3
    # same file again: updates, no duplicates
    j2 = client.post("/api/ingest/csv", files=csv_file(GOOD)).json()
    assert j2["rows_updated"] == 3 and j2["rows_new"] == 0 and count(client) == 9
    s = client.get("/api/analytics/summary", params={"entity_id": "Z-1"}).json()
    assert s["total_revenue"] == 1300.5  # "$1,200.50" parsed


def test_replace_wipes_demo_data(client):
    r = client.post("/api/ingest/csv", params={"mode": "replace"}, files=csv_file(GOOD))
    assert r.status_code == 200
    assert count(client) == 3
    assert {e["entity_id"] for e in client.get("/api/analytics/meta").json()["entities"]} == {"Z-1", "Z-2"}


def test_invalid_file_is_all_or_nothing(client):
    bad = GOOD + "not-a-date,Z-3,Gamma,X,10,5,1,1,Completed\n2026-11-04,Z-3,Gamma,X,-5,1,1,1,Completed\n"
    r = client.post("/api/ingest/csv", files=csv_file(bad))
    assert r.status_code == 400
    d = r.json()["detail"]
    assert len(d["errors"]) == 2 and d["errors"][0].startswith("Line 5") and "Nothing was imported" in d["message"]
    assert count(client) == 6  # untouched


def test_missing_columns_and_empty(client):
    r = client.post("/api/ingest/csv", files=csv_file("record_date,revenue\n2026-01-01,5\n"))
    assert r.status_code == 400 and "Missing required" in r.json()["detail"]["errors"][0]
    assert client.post("/api/ingest/csv", files=csv_file("")).status_code == 400
    hdr = "record_date,entity_id,revenue,operational_cost,units_processed\n"
    assert client.post("/api/ingest/csv", files=csv_file(hdr)).status_code == 400


def test_header_aliases_and_duplicate_fact_ids(client):
    ok = "Date,Zone,Revenue,Cost,Units\n2026-12-01,Q1,10,4,2\n"
    assert client.post("/api/ingest/csv", files=csv_file(ok)).status_code == 200
    dup = ("fact_id,record_date,entity_id,revenue,operational_cost,units_processed\n"
           "A,2026-12-01,Q1,1,1,1\nA,2026-12-02,Q1,1,1,1\n")
    r = client.post("/api/ingest/csv", files=csv_file(dup))
    assert r.status_code == 400 and "duplicate fact_id" in r.json()["detail"]["errors"][0]


def test_append_does_not_clobber_entity_names(client):
    no_names = "record_date,entity_id,revenue,operational_cost,units_processed\n2026-12-05,ENT-01,10,4,2\n"
    assert client.post("/api/ingest/csv", files=csv_file(no_names)).status_code == 200
    ents = {e["entity_id"]: e["name"] for e in client.get("/api/analytics/meta").json()["entities"]}
    assert ents["ENT-01"] == "Zone North 89011"


def test_non_utf8_and_template(client):
    r = client.post("/api/ingest/csv", files={"file": ("x.csv", b"\xff\xfe\x00bad", "text/csv")})
    assert r.status_code == 400
    t = client.get("/api/ingest/template")
    assert t.status_code == 200 and t.text.startswith("record_date,entity_id")
    # the shipped template must itself be a valid upload
    assert client.post("/api/ingest/csv", files=csv_file(t.text)).status_code == 200
