import pytest

from app.services import portfolio, quizzes


def _case(**k):
    return {"track": "itsupport", "title": "Fixed a stuck print queue", "problem": "Nobody could print.", "actions": "Cleared the spooler.", "result": "Printing resumed.", "skills": "Windows services", **k}


def test_empty_portfolio_claims_nothing(client):
    p = portfolio.build()
    assert p["active"] == 0 and p["steps_done"] == 0 and p["cases"] == 0
    md = portfolio.markdown()
    assert "No activity yet" in md and "Practised" not in md


def test_portfolio_reflects_steps_quiz_and_cases(client):
    client.put("/api/manuals/itsupport/steps/tickets", json={"done": True})
    qs = quizzes.QUIZZES["itsupport"]
    client.post("/api/quizzes/itsupport", json={"answers": [q["answer"] for q in qs]})
    assert client.post("/api/portfolio/cases", json=_case()).status_code == 200
    p = client.get("/api/portfolio").json()
    t = next(x for x in p["tracks"] if x["track"] == "itsupport")
    assert t["active"] and t["steps_done"] == 1 and t["quiz"]["passed"] and t["review"]["seen"] == len(qs) and len(t["cases"]) == 1
    assert p["active"] == 1 and p["quizzes_passed"] == 1
    md = client.get("/api/portfolio/markdown").text
    assert "Fixed a stuck print queue" in md and "passed" in md and "own record" in md


def test_markdown_escapes_formatting_characters(client):
    client.post("/api/portfolio/cases", json=_case(title="Found <script> & *bold* #1", result="done | ok"))
    md = portfolio.markdown("itsupport")
    assert "<script>" not in md and "\\<script\\>" in md and "\\*bold\\*" in md


def test_case_validation_and_limits(client):
    for bad in (_case(title=""), _case(problem="", actions="", result=""), _case(track="nope")):
        assert client.post("/api/portfolio/cases", json=bad).status_code == 400
    assert client.post("/api/portfolio/cases", json=_case(problem="x" * 2000)).status_code == 400
    assert client.get("/api/portfolio/markdown?track=nope").status_code == 404
    assert client.get("/api/portfolio/prompts/nope").status_code == 404


def test_update_and_delete(client):
    c = client.post("/api/portfolio/cases", json=_case()).json()
    u = client.put(f"/api/portfolio/cases/{c['id']}", json=_case(title="New title")).json()
    assert u["title"] == "New title" and u["id"] == c["id"]
    assert client.delete(f"/api/portfolio/cases/{c['id']}").status_code == 200
    assert client.delete(f"/api/portfolio/cases/{c['id']}").status_code == 404
    assert client.put("/api/portfolio/cases/zzz", json=_case()).status_code == 404


def test_case_cap(client, monkeypatch):
    monkeypatch.setattr(portfolio, "MAX_CASES", 2)
    for _ in range(2):
        assert client.post("/api/portfolio/cases", json=_case()).status_code == 200
    assert client.post("/api/portfolio/cases", json=_case()).status_code == 400


def test_prompts_come_from_ticked_steps(client):
    assert client.get("/api/portfolio/prompts/itsupport").json()["prompts"] == []
    client.put("/api/manuals/itsupport/steps/tickets", json={"done": True})
    assert len(client.get("/api/portfolio/prompts/itsupport").json()["prompts"]) == 1
