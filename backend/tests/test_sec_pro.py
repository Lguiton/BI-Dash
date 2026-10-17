from fastapi.testclient import TestClient

from app.main import app
from app.services import agent_tools, sec_pro

c = TestClient(app)


def test_cvss_known_scores():
    assert sec_pro.cvss("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")["score"] == 9.8
    assert sec_pro.cvss("CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N")["score"] == 6.1
    assert sec_pro.cvss("AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H")["score"] == 7.8
    assert sec_pro.cvss("AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N")["severity"] == "None"
    assert c.post("/api/secpro/cvss", json={"AV": "N", "AC": "L", "PR": "N", "UI": "N", "S": "U", "C": "H", "I": "H", "A": "H"}).json()["severity"] == "Critical"
    assert c.post("/api/secpro/cvss", json={"vector": "AV:Z"}).status_code == 400


def test_risk_math():
    r = c.post("/api/secpro/ale", json={"asset_value": 10000, "exposure_pct": 50, "incidents_per_year": 2, "control_cost_per_year": 1000, "risk_reduction_pct": 80}).json()
    assert r["single_loss"] == 5000 and r["annual_loss_expectancy"] == 10000 and r["annual_saving"] == 8000 and r["worth_it"] is True
    assert c.post("/api/secpro/ale", json={"asset_value": -1, "exposure_pct": 5, "incidents_per_year": 1}).status_code == 400
    assert c.post("/api/secpro/risk", json={"likelihood": "likely", "impact": "major"}).json()["level"] == "High"
    assert c.post("/api/secpro/risk", json={"likelihood": "x", "impact": "y"}).status_code == 400


def test_scope_timeline_rule_checklist():
    s = c.post("/api/secpro/scope", json={"client": "Practice Co", "systems": "10.0.0.5"}).json()
    assert "Practice Co" in s["text"] and "authorization" in s["text"].lower() and "illegal" in s["warning"]
    t = c.post("/api/secpro/timeline", json={"text": "Oct 16 15:00:00 b second\n2026-10-16 14:00:00 a first"}).json()
    assert t["events"][0]["line"].endswith("a first") and t["count"] == 2
    assert c.post("/api/secpro/timeline", json={"text": "one line"}).status_code == 400
    r = c.post("/api/secpro/rule", json={"rule": 'alert tcp $HOME_NET any -> $EXTERNAL_NET 443 (msg:"Test"; content:"abc"; sid:1000001; rev:1;)'}).json()
    assert r["action"] == "alert" and any(o["keyword"] == "sid" for o in r["options"])
    assert c.post("/api/secpro/rule", json={"rule": "garbage"}).status_code == 400
    for k in ("hipaa", "soc2", "pci", "continuity"):
        assert c.get(f"/api/secpro/checklist/{k}").json()["sections"]
    assert c.get("/api/secpro/checklist/zzz").status_code == 400
    assert len(c.get("/api/secpro/reference").json()["owasp"]) == 10


def test_agent_tools():
    t, e = agent_tools.run_tool("security", {"tool": "cvss", "args": {"vector": "AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}})
    assert not e and "9.8" in t
    t, e = agent_tools.run_tool("security", {"tool": "risk_ale", "args": {"asset_value": 1000, "exposure_pct": 10, "incidents_per_year": 1}})
    assert not e
    t, e = agent_tools.run_tool("security", {"tool": "rule_explain", "args": {"rule": 'alert tcp any any -> any 80 (msg:"x"; content:"y"; sid:1;)'}})
    assert not e
