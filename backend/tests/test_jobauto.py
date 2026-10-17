from fastapi.testclient import TestClient

from app.main import app
from app.services import agents, jobauto

c = TestClient(app)


class R:
    def __init__(self, t): self.reply = t


def test_agent_works_each_open_step_as_draft(monkeypatch):
    j = c.post("/api/jobs/quick-start", json={"title": "Fix slow Wi-Fi", "client": "Auto Test (practice)", "field": "network"}).json()
    jid = j["job"]["id"] if "job" in j else j["id"]
    calls = []
    monkeypatch.setattr(jobauto.ai_policy, "describe", lambda: {"mode": "full", "allowed": True})
    monkeypatch.setattr(jobauto.agents, "chat", lambda *a, **k: (calls.append(a), R("do this"))[1])
    r = c.post(f"/api/jobs/{jid}/auto", json={"instructions": "start with the router"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "pending" and d["steps"] == len(calls) >= 1 and "STEP 1" in d["text"]
    assert calls[0][0] == "network" and calls[0][-1] == jid
    items = [i for i in c.get("/api/worklog").json()["items"] if i["job_id"] == jid]
    assert items and all(i["status"] != "done" for i in items)   # never marks steps done
    assert f"auto:{jid}" in c.get("/api/auto/prep/drafts").json()["drafts"]


def test_off_blocks(monkeypatch):
    monkeypatch.setattr(jobauto.ai_policy, "describe", lambda: {"mode": "off", "allowed": False})
    assert c.post("/api/jobs/1/auto", json={}).status_code == 403
