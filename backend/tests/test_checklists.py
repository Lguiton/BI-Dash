"""Triage checklists: templates, starting one on a job, ticking items, notes."""
import pytest

from app.services import checklists as ck


@pytest.fixture
def job(client):
    c = client.post("/api/clients", json={"name": "Practice Co"}).json()
    return client.post("/api/clients/jobs/add", json={"client_id": c["id"], "title": "Slow database", "quote": 200}).json()["id"]


def test_templates_are_well_formed():
    for t in ck.TEMPLATES:
        assert t["title"] and t["field"] and t["when"] and t["source"]
        for s in t["sections"]:
            assert s["title"] and s["items"]
            for i in s["items"]:
                assert i["text"].strip()
        assert len(set(ck._item_ids(t))) == len(ck._item_ids(t))
    assert {t["id"] for t in ck.TEMPLATES} == {"slow-database", "network-rack", "big-file"}


def test_vendor_claims_not_used():
    text = " ".join(i["text"] + i["why"] for t in ck.TEMPLATES for s in t["sections"] for i in s["items"])
    for claim in ("70 percent", "5,600", "10x", "50 %", "50%", "10 times"):
        assert claim not in text


def test_listing(client):
    r = client.get("/api/checklists").json()
    assert [t["id"] for t in r["templates"]] == ["slow-database", "network-rack", "big-file"]
    assert all(t["total"] >= 10 for t in r["templates"])


def test_start_tick_notes_remove(client, job):
    assert client.get(f"/api/checklists/job/{job}").json()["lists"] == []
    v = client.post(f"/api/checklists/job/{job}/slow-database").json()
    assert v["done"] == 0 and v["total"] > 10
    again = client.post(f"/api/checklists/job/{job}/slow-database").json()
    assert again["started"] == v["started"]
    r = client.put(f"/api/checklists/job/{job}/slow-database", json={"checked": ["s2.1", "s1.1"], "notes": "disk 98% full. password: hunter2hunter2"}).json()
    assert r["checked"] == ["s1.1", "s2.1"] and r["done"] == 2
    assert "hunter2hunter2" not in r["notes"]
    assert client.get(f"/api/checklists/job/{job}").json()["lists"][0]["done"] == 2
    assert client.delete(f"/api/checklists/job/{job}/slow-database").status_code == 200
    assert client.delete(f"/api/checklists/job/{job}/slow-database").status_code == 404


def test_refusals(client, job):
    assert client.post(f"/api/checklists/job/{job}/nope").status_code == 404
    assert client.post("/api/checklists/job/99999/slow-database").status_code == 404
    assert client.put(f"/api/checklists/job/{job}/slow-database", json={"checked": []}).status_code == 404
    client.post(f"/api/checklists/job/{job}/slow-database")
    for bad in (["zzz"], "s1.1", [1], ["s9.9"]):
        assert client.put(f"/api/checklists/job/{job}/slow-database", json={"checked": bad}).status_code == 400


def test_lists_are_per_job_and_per_checklist(client, job):
    c = client.post("/api/clients", json={"name": "Other"}).json()
    j2 = client.post("/api/clients/jobs/add", json={"client_id": c["id"], "title": "Rack", "quote": 100}).json()["id"]
    client.post(f"/api/checklists/job/{job}/slow-database")
    client.post(f"/api/checklists/job/{j2}/network-rack")
    client.put(f"/api/checklists/job/{job}/slow-database", json={"checked": ["s1.1"]})
    assert [x["template_id"] for x in client.get(f"/api/checklists/job/{j2}").json()["lists"]] == ["network-rack"]
    assert client.get(f"/api/checklists/job/{j2}").json()["lists"][0]["done"] == 0
