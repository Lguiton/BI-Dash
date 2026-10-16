import pytest

from app.services import agent_debate, ai_policy, providers
from app.services.providers import Call, Turn


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    monkeypatch.setattr(ai_policy, "describe", lambda: {"mode": "full", "allowed": True, "workspace": "practice", "blocked_columns": []})
    for k in ("ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.setenv(k, "x")
    monkeypatch.setattr(providers, "sdk_installed", lambda p: True)


class A:
    """As an agent (tools given) it calls one tool then answers; as a plain completion (no tools) it returns `plain`."""
    def __init__(self, name, answer, plain="JUDGED REPORT", fail=False):
        self.provider = self.model = name
        self.answer, self.plain, self.fail, self.tools, self.n, self.prompt = answer, plain, fail, [], 0, ""

    def start(self, system, tools, q):
        self.tools, self.n, self.prompt = tools, 0, q
        if self.fail:
            raise providers.ProviderError("boom", 500)

    def next_turn(self):
        self.n += 1
        if not self.tools:
            return Turn(self.plain)
        return Turn("", calls=[Call("c", "use_tool", {"tool": "subnet", "args": {"cidr": "10.0.0.0/24"}})]) if self.n == 1 else Turn(self.answer)

    def add_results(self, *a):
        pass


def team(**o):
    d = {"google": A("google", "G says 254 hosts"), "openai": A("openai", "O says 256 hosts"), "anthropic": A("anthropic", "never an agent here")}
    d.update(o)
    return d


def test_every_dashboard_has_agent_tools():
    from app.services import agent_tools, agents
    assert set(agent_tools.BY_TRACK) == set(agents.AGENTS)


def test_off_by_default_cap_and_judge_report(client):
    with pytest.raises(agent_debate.DebateError) as e:
        agent_debate.run("network", "How many hosts in 10.0.0.0/24?", [], None, team())
    assert e.value.status == 403
    agent_debate.update_config({"enabled": True, "daily_cap": 1})
    t = team()
    r = agent_debate.run("network", "How many hosts in 10.0.0.0/24?", [], None, t)
    assert r["judge"] == "Claude" and r["report"] == "JUDGED REPORT" and len(r["answers"]) == 2 and [a["label"] for a in r["answers"]] == ["Gemini", "OpenAI"]
    assert all("dashboard tool: subnet" in a["tools"] for a in r["answers"])         # each agent used the tool
    jp = t["anthropic"].prompt
    assert "G says 254" in jp and "O says 256" in jp and "never an agent" not in jp and "Tools it ran: dashboard tool: subnet" in jp
    with pytest.raises(agent_debate.DebateError) as e2:
        agent_debate.run("network", "again please", [], None, team())
    assert e2.value.status == 429


def test_failures_and_single_answer(client):
    agent_debate.update_config({"enabled": True, "daily_cap": 5})
    r = agent_debate.run("network", "How many hosts?", [], None, team(google=A("google", "", fail=True)))
    assert len(r["answers"]) == 1 and any("Gemini" in f for f in r["failed"]) and r["judge"] == "" and "not a debate" in r["report"]
    with pytest.raises(agent_debate.DebateError) as e:
        agent_debate.run("network", "How many hosts?", [], None, team(google=A("google", "", fail=True), openai=A("openai", "", fail=True)))
    assert e.value.status == 502


def test_judge_falls_back_and_report_is_queued_and_api_works(client):
    agent_debate.update_config({"enabled": True, "daily_cap": 5})
    r = agent_debate.run("network", "How many hosts?", [], None, team(anthropic=A("anthropic", "C", plain=""), openai=A("openai", "O says 256 hosts", plain="OPENAI JUDGED")))
    assert r["judge"] in ("OpenAI", "Gemini") or "unjudged" in r["report"]
    assert any(x["key"] == r["key"] for x in client.get("/api/auto/queue").json()["queue"])
    assert client.get("/api/debate/status").json()["enabled"] is True
    assert client.put("/api/debate/config", json={"daily_cap": 99}).status_code == 400
    assert client.post("/api/agents/nope/debate", json={"message": "hello there"}).status_code == 404
    client.put("/api/debate/config", json={"enabled": False})
    assert client.post("/api/agents/network/debate", json={"message": "hello there"}).status_code == 403
