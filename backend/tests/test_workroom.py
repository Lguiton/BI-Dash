import io
import time

from fastapi.testclient import TestClient

from app.main import app
from app.services import agents, workroom

c = TestClient(app)


class R:
    def __init__(self, t): self.reply = t


def _patch(monkeypatch, calls):
    monkeypatch.setattr(workroom.ai_policy, "describe", lambda: {"mode": "full", "allowed": True})
    monkeypatch.setattr(workroom.agents, "chat", lambda *a, **k: (calls.append((a, k)), R("Result with numbers: 42"))[1])


def test_paste_a_client_issue_starts_a_job_and_agents_do_every_step_but_never_tick(monkeypatch):
    calls = []
    _patch(monkeypatch, calls)
    b = c.post("/api/workroom/begin", json={"request": "Subject: Is the new checkout button better?\nHi, we ran an A/B test on our checkout button. Please tell us if the variant works.\n- Dana Reyes", "client": "Room Test (practice)"})
    assert b.status_code == 200, b.text
    jid = b.json()["job_id"]
    assert b.json()["steps"]
    csv = b"visitor_id,group,converted\n" + b"\n".join(f"V{i},{'control' if i % 2 == 0 else 'variant'},{1 if (i % 10 == 0 or (i % 2 and i % 7 == 0)) else 0}".encode() for i in range(600))
    r = c.post(f"/api/workroom/{jid}/run", data={"instructions": "be plain"}, files={"file": ("ab.csv", io.BytesIO(csv), "text/csv")})
    assert r.status_code == 200
    for _ in range(100):
        v = c.get(f"/api/workroom/{jid}").json()
        if v["run"]["state"] != "running":
            break
        time.sleep(0.1)
    assert v["run"]["state"] == "done", v["run"]
    assert all(s["agent"] and s["agent"]["status"] == "ready" for s in v["steps"]), ([(s["id"], s["agent"] and s["agent"]["status"], s["agent"] and s["agent"].get("error")) for s in v["steps"]], v["run"])
    assert v["autopilot"]["counts"]["ran"] >= 2 and v["reply"]["text"]
    assert not any(s["done"] for s in v["steps"])                      # the owner's checklist stays the owner's
    assert "AUTOMATIC ANALYSIS" in calls[0][0][8] and "ab.csv" in calls[0][0][8]   # agents get the real test results
    t = c.put(f"/api/workroom/{jid}/steps/{v['steps'][0]['id']}", json={"done": True}).json()
    assert t["steps"][0]["done"] is True and t["steps"][0]["agent"]["status"] == "ready"


def test_build_or_fix_request_works_without_a_file(monkeypatch):
    calls = []
    _patch(monkeypatch, calls)
    jid = c.post("/api/workroom/begin", json={"request": "Build a small web form that saves customer feedback to a database", "client": "Room Test (practice)"}).json()["job_id"]
    v = workroom.run_job(jid, wait=True)
    assert workroom._RUNS[jid]["state"] == "done" and calls
    assert "Produce the actual result" in calls[0][0][1]


def test_off_blocks_and_short_text_refused(monkeypatch):
    monkeypatch.setattr(workroom.ai_policy, "describe", lambda: {"mode": "off", "allowed": False})
    assert c.post("/api/workroom/begin", json={"request": "hi"}).status_code == 400
    jid = c.post("/api/workroom/begin", json={"request": "Fix the slow office Wi-Fi please", "client": "Room Test (practice)"}).json()["job_id"]
    assert c.post(f"/api/workroom/{jid}/run").status_code == 403


def test_provider_failure_is_reported_not_hidden(monkeypatch):
    monkeypatch.setattr(workroom.ai_policy, "describe", lambda: {"mode": "full", "allowed": True})
    def boom(*a, **k): raise agents.AgentError("No key", 403)
    monkeypatch.setattr(workroom.agents, "chat", boom)
    jid = c.post("/api/workroom/begin", json={"request": "Fix the slow office Wi-Fi please", "client": "Room Test (practice)"}).json()["job_id"]
    workroom.run_job(jid, wait=True)
    v = c.get(f"/api/workroom/{jid}").json()
    assert v["run"]["state"] == "failed" and v["run"]["error"]
