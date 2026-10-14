import io
import zipfile
from datetime import date

import pytest

from app.services import clients as cl


def test_flow_money_and_pack(client):
    c = client.post("/api/clients", json={"name": "Desert Auto"}).json()
    cid = c["id"]
    j = client.post("/api/clients/jobs/add", json={"client_id": cid, "title": "Dashboard", "quote": 900, "status": "active"}).json()
    assert client.post("/api/clients/time/add", json={"job_id": j["id"], "hours": 2.5}).status_code == 200
    client.post("/api/clients/time/add", json={"job_id": j["id"], "hours": 1.5, "billable": False})
    client.put("/api/clients/settings", json={"rate": 80})
    ov = client.get("/api/clients/overview").json()
    assert ov["unbilled_hours"] == 2.5 and ov["unbilled_amount"] == 200.0 and ov["jobs_active"] == 1
    inv = client.post("/api/clients/invoices/create", json={"client_id": cid, "extra": [{"desc": "Setup", "qty": 1, "rate": 50}]}).json()
    assert inv["total"] == 250.0 and inv["number"] == "INV-0001"
    assert client.post("/api/clients/invoices/create", json={"client_id": cid, "from_time": True}).status_code == 400
    assert client.get("/api/clients/overview").json()["unbilled_hours"] == 0
    assert client.delete(f"/api/clients/time/{1}").status_code == 409
    client.put(f"/api/clients/invoices/{inv['id']}", json={"status": "sent"})
    assert client.get("/api/clients/overview").json()["outstanding"] == 250.0
    assert "SAMPLE" in client.get(f"/api/clients/invoices/{inv['id']}/view").text
    client.put(f"/api/clients/invoices/{inv['id']}", json={"status": "paid"})
    ov = client.get("/api/clients/overview").json()
    assert ov["outstanding"] == 0 and ov["paid_this_month"] == 250.0
    client.put(f"/api/clients/invoices/{inv['id']}", json={"status": "void"})
    assert client.get("/api/clients/overview").json()["unbilled_hours"] == 2.5       # void gives the time back
    r = client.post(f"/api/clients/{cid}/pack", json={"notes": {"done": "Built a dashboard"}})
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert {"summary.md", "notes.md", "README.txt"} <= set(names) and not any(n.startswith("invoice_") for n in names)
    assert "Built a dashboard" in zipfile.ZipFile(io.BytesIO(r.content)).read("notes.md").decode()
    assert client.get(f"/api/clients/{cid}").json()["packs"]
    assert client.delete(f"/api/clients/{cid}").status_code == 200
    assert client.get(f"/api/clients/{cid}").status_code == 404


def test_validation_and_overdue(client):
    assert client.post("/api/clients", json={"name": " "}).status_code == 400
    cid = client.post("/api/clients", json={"name": "A"}).json()["id"]
    assert client.post("/api/clients/jobs/add", json={"client_id": cid, "title": "x", "due": "31/10"}).status_code == 400
    assert client.post("/api/clients/time/add", json={"job_id": 999, "hours": 1}).status_code == 404
    inv = client.post("/api/clients/invoices/create", json={"client_id": cid, "issued": "2026-01-01", "due": "2026-01-15", "extra": [{"desc": "Fix", "qty": 2, "rate": 10}]}).json()
    client.put(f"/api/clients/invoices/{inv['id']}", json={"status": "sent"})
    o = cl.overview(date(2026, 2, 1))
    assert o["overdue"][0]["days_late"] == 17 and o["overdue"][0]["total"] == 20.0
    client.post("/api/clients/followups/add", json={"client_id": cid, "note": "Chase", "due": "2026-01-20"})
    assert cl.overview(date(2026, 2, 1))["followups_due"][0]["client"] == "A"
    client.delete(f"/api/clients/{cid}")
