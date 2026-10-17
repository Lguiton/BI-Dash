from fastapi.testclient import TestClient

from app.main import app
from app.services import agent_tools, compliance

c = TestClient(app)


def test_library_lists_required_laws():
    ids = {e["id"] for e in c.get("/api/compliance").json()["laws"]}
    assert {"hipaa", "gdpr", "ccpa", "ftc-act", "safeguards", "pci", "nrs603a", "canspam"} <= ids
    j = c.get("/api/compliance").json()
    assert j["note"] and any(g["term"] == "PHI" for g in j["glossary"]) and any(g["term"] == "PII" for g in j["glossary"])


def test_every_entry_complete_with_official_https_links():
    for e in compliance.LAWS:
        r = c.get(f"/api/compliance/{e['id']}").json()
        assert r["duties"] and r["applies"] and r["freelancer"] and r["links"]
        assert all(k["url"].startswith("https://") for k in r["links"])


def test_unknown_404_and_search():
    assert c.get("/api/compliance/nope").status_code == 404
    assert c.get("/api/compliance/search?q=patient%20records").json()["results"][0]["id"] == "hipaa"
    assert c.get("/api/compliance/search?q=").json()["results"] == []


def test_agent_tool():
    txt, err = agent_tools.run_tool("security", {"tool": "compliance", "args": {"q": "breach notification 72 hours"}})
    assert not err and "GDPR" in txt
    txt, err = agent_tools.run_tool("cpe", {"tool": "compliance", "args": {"q": "x"}})
    assert err
    txt, err = agent_tools.run_tool("itsupport", {"tool": "compliance", "args": {"q": "HIPAA"}})
    assert not err and "HIPAA" in txt
