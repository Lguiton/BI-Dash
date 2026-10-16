from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import comms, ai_policy


class _Turn:
    def __init__(self, text):
        self.text, self.calls, self.input_tokens, self.output_tokens = text, [], 10, 20


class _Fake:
    model = "fake"
    seen = ""

    def start(self, system, tools, q):
        _Fake.seen = q

    def next_turn(self):
        return _Turn("Hi, thanks for writing. [next step]")

    def add_results(self, r):
        pass


def test_templates_are_free_and_fill_names():
    t = comms.template("quote_followup", "Dana Lopez", "Router setup")
    assert t.startswith("Hi Dana,") and "Router setup" in t
    for k in comms.KINDS:
        assert "{" not in comms.template(k, "A B", "x", "y")


def test_draft_without_ai_needs_no_key():
    c = TestClient(app)
    r = c.post("/api/comms/draft", json={"kind": "job_done", "name": "Sam Cole"}).json()
    assert r["ai"] is None and "Sam" in r["template"]
    assert c.post("/api/comms/draft", json={"kind": "nope"}).status_code == 400


def test_ai_draft_scrubs_and_labels(monkeypatch):
    monkeypatch.setattr(ai_policy, "describe", lambda: {"mode": "full"})
    def fake(s, p, e, pr, a):
        _Fake.seen = p
        return {"text": "Hi. [next step]", "provider": "fake", "input_tokens": 5, "output_tokens": 7}
    monkeypatch.setattr(comms.llm_router, "complete", fake)
    r = comms.draft("reply", "My password is hunter2 and my number is 702-555-0100", None, "Dana", True)
    assert r["ai"]["tokens"] == 12 and "Nothing is sent" in r["note"]
    assert "hunter2" not in _Fake.seen and "702-555" not in _Fake.seen


def test_ai_off_refuses_ai_but_not_template(monkeypatch):
    monkeypatch.setattr(ai_policy, "describe", lambda: {"mode": "off"})
    with pytest.raises(comms.CommsError) as e:
        comms.draft("reply", "hi", None, "A", True)
    assert e.value.status == 403
    assert comms.draft("reply", "hi", None, "A", False)["template"]


def test_week_list_finds_stale_quote_and_past_client():
    from app.services import clients as cl, leads
    c = cl.add_client({"name": "Old Pal"})
    j = cl.add_job({"client_id": c["id"], "title": "Printer fix", "status": "done"})
    d = cl._load()
    for x in d["jobs"]:
        if x["id"] == j["id"]:
            x["created"] = (date.today() - timedelta(days=90)).isoformat()
    cl._save(d)
    leads.add({"name": "New Lead", "status": "quoted", "what": "wifi"})
    w = comms.week(date.today() + timedelta(days=5))
    who = {p["who"]: p for p in w["people"]}
    assert who["Old Pal"]["kind"] == "checkin" and who["New Lead"]["kind"] == "quote_followup"
    assert TestClient(app).get("/api/comms/week").status_code == 200
