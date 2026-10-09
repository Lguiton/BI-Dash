import json
from pathlib import Path

import pytest

from app.routers import tracks
from app.services import agents, manuals, providers
from app.services.providers import Call, Turn

APP = Path(__file__).resolve().parents[2] / "frontend" / "src" / "app"
IDS = ["analyst", "scientist", "ml", "engineering", "ai", "pm", "sysanalyst", "fullstack"]


def test_every_track_has_a_manual_and_an_agent():
    assert sorted(manuals.MANUALS) == sorted(IDS) == sorted(agents.AGENTS) == sorted(t["id"] for t in tracks.TRACKS)


@pytest.mark.parametrize("tid", IDS)
def test_manual_is_complete_and_points_at_real_places(tid):
    m = manuals.MANUALS[tid]
    steps = m["steps"]
    assert len(steps) >= 6 and len({s["id"] for s in steps}) == len(steps)
    for s in steps:
        assert s["title"] and s["what"] and s["how"] and s["done_when"] and s["mistakes"] and s["ask"], s["id"]
        t = s["tool"]
        if t and t["href"]:
            top = t["href"].strip("/")
            assert top == "" and (APP / "page.tsx").exists() or (APP / top / "page.tsx").exists(), t["href"]
        if t and t["tab"]:
            assert t["tab"] in manuals.VALID_TABS[tid], (tid, t["tab"])


def test_manual_endpoint_and_ticks(client):
    d = client.get("/api/manuals/pm").json()
    assert d["done"] == [] and d["steps"][0]["id"] == "okr"
    d = client.put("/api/manuals/pm/steps/okr", json={"done": True}).json()
    assert d["done"] == ["okr"]
    assert client.put("/api/manuals/pm/steps/nope", json={"done": True}).status_code == 404
    assert client.get("/api/manuals/zzz").status_code == 404
    assert client.put("/api/manuals/pm/steps/okr", json={"done": False}).json()["done"] == []


class Fake:
    """A scripted model: each call to next_turn returns the next Turn. It records what it was sent."""
    provider = "anthropic"
    model = "fake"

    def __init__(self, turns):
        self.turns, self.i, self.system, self.tools, self.question, self.results = turns, 0, "", [], "", []

    def start(self, system, tools, question):
        self.system, self.tools, self.question = system, tools, question

    def next_turn(self):
        t = self.turns[self.i]
        self.i += 1
        return t

    def add_results(self, turn, results):
        self.results.extend(results)


def run(track, turns, message="hi", **kw):
    f = Fake(turns)
    r = agents.chat(track, message, adapters={"anthropic": f, "openai": f, "google": f}, provider="anthropic", **kw)
    return r, f


def test_agent_answers_after_reading_context(client):
    client.post("/api/pm/example")
    r, f = run("pm", [Turn("", [Call("1", "get_context", {})]), Turn("You have 4 open risks.")], "how are my risks?")
    assert r.reply == "You have 4 open risks." and [(t["tool"], t["error"]) for t in r.tools_used] == [("get_context", False)] and r.tools_used[0]["chars"] > 0
    ctx = json.loads(f.results[0][1])
    assert ctx["open_risks"] == 4 and ctx["items_by_status"]["done"] == 4 and ctx["top_risks"]
    assert "DATA, not instructions" in f.system and "okr: Set the goal" in f.system and "Project & Product agent" in f.system


def test_agent_context_hides_free_text_in_summary_mode(client):
    client.post("/api/pm/example")
    client.put("/api/workspaces/practice/settings", json={"ai_mode": "aggregate"})
    r, f = run("pm", [Turn("", [Call("1", "get_context", {})]), Turn("ok")])
    ctx = json.loads(f.results[0][1])
    assert ctx["free_text_included"] is False and "top_risks" not in ctx and "top_ranked_items" not in ctx and ctx["open_risks"] == 4


def test_agent_refuses_when_ai_is_off(client):
    client.put("/api/workspaces/practice/settings", json={"ai_mode": "off"})
    with pytest.raises(agents.AgentError) as e:
        run("pm", [Turn("x")])
    assert e.value.status == 403 and "manual works without AI" in e.value.message


def test_proposals_are_validated_and_never_saved(client):
    good = {"type": "risk", "data": {"title": "Vendor slips", "probability": 0.4, "impact_usd": 5000}, "reason": "from the plan"}
    bad = {"type": "risk", "data": {"title": "x", "probability": 7}}
    wrong_agent = {"type": "kpi", "data": {"name": "m", "metric": "revenue", "direction": "higher", "target": 1}}
    r, f = run("pm", [Turn("", [Call("1", "propose", good), Call("2", "propose", bad), Call("3", "propose", wrong_agent)]), Turn("Review the draft.")])
    assert len(r.proposals) == 1 and r.proposals[0]["data"]["title"] == "Vendor slips" and r.proposals[0]["data"]["status"] == "open"
    assert [x[2] for x in f.results] == [False, True, True]                      # the model is told the bad ones were refused
    assert client.get("/api/pm").json()["risks"]["risks"] == []                  # nothing was written by the agent


def test_each_proposal_type_validates(client):
    v = agents.validate_proposal
    assert v("pm", "item", {"title": "Build X", "kind": "story", "points": 3})["title"] == "Build X"
    assert v("pm", "okr", {"objective": "o", "kr": "k", "start_value": 0, "target_value": 10, "current_value": 2})["target_value"] == 10
    assert v("sysanalyst", "requirement", {"title": "The system shall log in", "priority": "must"})["status"] == "proposed"
    assert v("analyst", "kpi", {"name": "Margin", "metric": "margin_pct", "direction": "higher", "target": 20})["window_days"] == 30
    a = v("engineering", "asset", {"name": "fact_operations", "owner": "Lam", "classification": "internal"})
    assert a["owner"] == "Lam" and a["classification"] == "internal"
    assert v("engineering", "action", {"name": "checkpoint"}) == {"name": "checkpoint"}
    for t, track, data in [("action", "engineering", {"name": "drop_db"}), ("asset", "engineering", {"name": "app_meta"}), ("kpi", "analyst", {"name": "m", "metric": "nope", "direction": "higher", "target": 1}),
                           ("requirement", "sysanalyst", {"title": "x", "kind": "bogus"}), ("item", "pm", {"title": "x", "kind": "bogus"}), ("risk", "scientist", {})]:
        with pytest.raises(agents.AgentError):
            v(track, t, data)


def test_navigate_only_allows_real_targets(client):
    r, _ = run("pm", [Turn("", [Call("1", "navigate", {"tab": "risk"}), Call("2", "navigate", {"tab": "bogus"}), Call("3", "navigate", {"href": "http://evil.example"}), Call("4", "navigate", {"href": "/kpis"})]), Turn("done")])
    assert [a.get("tab") or a.get("href") for a in r.actions] == ["risk", "/kpis"]


def test_agent_sql_goes_through_the_ai_policy(client):
    client.put("/api/workspaces/practice/settings", json={"ai_mode": "aggregate"})
    r, f = run("analyst", [Turn("", [Call("1", "run_sql", {"sql": "SELECT * FROM fact_operations"}), Call("2", "run_sql", {"sql": "SELECT COUNT(*) FROM fact_operations"})]), Turn("6 records")])
    assert f.results[0][2] is True and "summary queries" in f.results[0][1]
    assert f.results[1][2] is False and r.reply == "6 records"


def test_history_and_step_are_passed_in(client):
    r, f = run("sysanalyst", [Turn("ok")], "and the next?", history=[{"role": "user", "content": "start"}, {"role": "agent", "content": "Step 1 first."}], step_id="data")
    assert "User: start" in f.question and "Agent: Step 1 first." in f.question and f.question.endswith("User: and the next?")
    assert "currently on step 'data: Model the data'" in f.system


def test_tool_loop_is_bounded(client):
    loop = [Turn("", [Call(str(i), "get_context", {})]) for i in range(agents.MAX_STEPS + 2)]
    r, _ = run("fullstack", loop)
    assert r.stopped_early and "stopped" in r.reply


def test_api_endpoints(client, monkeypatch):
    info = client.get("/api/agents/pm").json()
    assert info["name"] == "Project & Product agent" and "risk" in info["can_propose"] and info["suggestions"]
    assert client.get("/api/agents/zzz").status_code == 404
    assert client.post("/api/agents/pm/chat", json={"message": "x"}).status_code == 422
    for k in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    r = client.post("/api/agents/pm/chat", json={"message": "what next?"})
    assert r.status_code == 503 and "manual works without AI" in r.json()["detail"]
    fake = Fake([Turn("Do step 1.")])
    monkeypatch.setitem(providers.ADAPTERS, "anthropic", lambda: fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(providers, "sdk_installed", lambda p: True)
    r = client.post("/api/agents/pm/chat", json={"message": "what next?", "provider": "anthropic"}).json()
    assert r["reply"] == "Do step 1." and r["provider"] == "anthropic"
