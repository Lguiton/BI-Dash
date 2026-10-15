"""Field guess and one-line job start."""
from app.services import jobfield


def test_prefix_wins_then_keywords():
    assert jobfield.guess("Networking: Fix office Wi-Fi dropping") == "network"
    assert jobfield.guess("Data analyst: Weekly sales dashboard") == "analyst"
    assert jobfield.guess("IT repair: Laptop tune-up") == "itsupport"
    assert jobfield.guess("Cybersecurity: phishing check") == "security"
    assert jobfield.guess("Engineering: Size a power supply") == "cpe"
    assert jobfield.guess("Fix the printer for Silver State") == "itsupport"
    assert jobfield.guess("zzz qqq") is None


def test_quick_start_creates_client_job_and_timer_item(client):
    r = client.post("/api/jobs/quick-start", json={"title": "Fix office Wi-Fi dropping", "client": "Sunrise Dental"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["field"]["key"] == "network" and b["field"]["href"] == "/tracks/network"
    assert b["job"]["status"] == "active" and b["work_item"]["job_id"] == b["job"]["id"]
    # same client name again reuses the client
    client.post("/api/jobs/quick-start", json={"title": "Laptop tune-up", "client": "sunrise dental"})
    assert len([c for c in client.get("/api/clients").json()["clients"] if c["name"].lower() == "sunrise dental"]) == 1
    jobs = client.get("/api/clients/open-jobs").json()["jobs"]
    assert {j["field"]["key"] for j in jobs} == {"network", "itsupport"}
    ov = client.get(f"/api/jobs/{b['job']['id']}").json()
    assert ov["job"]["field_info"]["label"] == "Networking"


def test_quick_start_validation_and_field_change(client):
    assert client.post("/api/jobs/quick-start", json={"title": "", "client": "X"}).status_code == 400
    assert client.post("/api/jobs/quick-start", json={"title": "Job", "client": ""}).status_code == 400
    assert client.post("/api/jobs/quick-start", json={"title": "Job", "client": "X", "field": "bogus"}).status_code == 400
    j = client.post("/api/jobs/quick-start", json={"title": "Odd thing", "client": "X", "field": "security"}).json()["job"]
    assert client.put(f"/api/clients/jobs/{j['id']}", json={"field": "network"}).status_code == 200
    assert client.get(f"/api/jobs/{j['id']}").json()["job"]["field_info"]["key"] == "network"
    assert client.put(f"/api/clients/jobs/{j['id']}", json={"field": "bogus"}).status_code == 400
    assert any(f["key"] == "pm" for f in client.get("/api/jobs/fields/list").json()["fields"])
