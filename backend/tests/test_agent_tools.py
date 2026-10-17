import json

import pytest

from app.services import agent_tools, agents, ai_policy, clients, jobpage, providers
from app.services.providers import Call, Turn


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    monkeypatch.setattr(ai_policy, "describe", lambda: {"mode": "full", "allowed": True, "workspace": "practice", "blocked_columns": []})
    for k in ("ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.setenv(k, "x")
    monkeypatch.setattr(providers, "sdk_installed", lambda p: True)


class Scripted:
    """First turn asks for tools, second turn answers. Records what it was given and what came back."""
    def __init__(self, calls):
        self.provider = self.model = "anthropic"
        self.calls, self.n, self.tools, self.results, self.system = calls, 0, [], [], ""

    def start(self, system, tools, q):
        self.system, self.tools = system, tools

    def next_turn(self):
        self.n += 1
        return Turn("", calls=[Call(f"c{i}", n, a) for i, (n, a) in enumerate(self.calls)]) if self.n == 1 else Turn("done")

    def add_results(self, turn, results):
        self.results = [(c.name, out, err) for c, out, err in results]


def test_networking_agent_runs_the_subnet_and_transfer_calculators_locally(client):
    a = Scripted([("use_tool", {"tool": "subnet", "args": {"cidr": "192.168.10.0/24"}}), ("use_tool", {"tool": "transfer_time", "args": {"size_gb": 100, "mbps": 1000}}), ("use_tool", {"tool": "dns", "args": {"host": "example.com"}})])
    r = agents.chat("network", "How big is 192.168.10.0/24 and how long to move 100 GB?", [], None, "anthropic", {"anthropic": a})
    names = [t["name"] for t in a.tools]
    assert "use_tool" in names and "get_job" not in names
    enum = next(t for t in a.tools if t["name"] == "use_tool")["input_schema"]["properties"]["tool"]["enum"]
    assert "dns" not in enum and "tcp" not in enum and "subnet" in enum              # nothing that reaches another computer
    out = {n: (o, e) for n, o, e in a.results}
    assert any("254" in o and not e for n, o, e in a.results[:1]) and not a.results[1][2]
    assert a.results[2][2] is True and "Unknown tool" in a.results[2][1]
    assert any(t["tool"] == "use_tool" for t in r.tools_used) and r.reply == "done"


def test_each_field_gets_its_own_tools(client):
    assert set(agent_tools.BY_TRACK) == set(agents.AGENTS)                 # every dashboard's agent has tools
    assert "raid" not in agent_tools.BY_TRACK["network"] and "subnet" not in agent_tools.BY_TRACK["itsupport"]
    assert "raid" in agent_tools.BY_TRACK["itsupport"] and "analyze_logs" in agent_tools.BY_TRACK["security"] and "forecast" in agent_tools.BY_TRACK["analyst"]
    a = Scripted([])
    agents.chat("pm", "hello there", [], None, "anthropic", {"anthropic": a})
    names = {t["name"]: t for t in a.tools}
    assert "use_tool" in names and "pm_overview" in names["use_tool"]["input_schema"]["properties"]["tool"]["enum"]
    s, err = agent_tools.run_tool("network", {"tool": "raid", "args": {}})
    assert err and "Unknown tool" in s                                        # a field cannot use another field's tool
    s, err = agent_tools.run_tool("network", {"tool": "subnet", "args": {}})
    assert err and "Missing argument" in s
    s, err = agent_tools.run_tool("itsupport", {"tool": "capacity", "args": {"used_gb": 400, "total_gb": 500, "growth_gb_per_month": 10}})
    assert not err and json.loads(s)
    s, err = agent_tools.run_tool("analyst", {"tool": "forecast", "args": {"values": [10, 12, 13, 15, 16, 18, 19, 21, 22, 24], "horizon": 3}})
    assert not err and "forecast" in s.lower()
    s, err = agent_tools.run_tool("security", {"tool": "analyze_logs", "args": {"text": "Oct 12 10:00:01 host sshd[1]: Failed password for root from 203.0.113.9 port 22 ssh2"}})
    assert not err


def test_agent_reads_the_pinned_job_with_practice_files_but_not_the_answer(client):
    c = clients.add_client({"name": "(practice) Red Rock"})
    cid = c.get("id") or c["client"]["id"]
    jid = jobpage.quick_start("Data analyst: Weekly sales dashboard", client_id=cid)["job"]["id"]
    a = Scripted([("get_job", {})])
    agents.chat("analyst", "Help me with this job", [], None, "anthropic", {"anthropic": a}, job_id=jid)
    assert "get_job" in [t["name"] for t in a.tools] and "Call get_job" in a.system
    text = a.results[0][1]
    assert "Weekly sales dashboard" in text and "sales_6_weeks.csv" in text and "Exact duplicate rows: 2" in text
    assert "Top item by revenue" not in text and not a.results[0][2]
    b = Scripted([])
    agents.chat("analyst", "Help me with this job", [], None, "anthropic", {"anthropic": b}, job_id=99999)       # an unknown job adds no job tool
    assert "get_job" not in [t["name"] for t in b.tools]
    assert agent_tools.job_for_agent(None)[1] is True


def test_chat_endpoint_accepts_job_id(client):
    r = client.post("/api/agents/network/chat", json={"message": "hello there", "job_id": 5})
    assert r.status_code != 422


def test_network_agent_scope_includes_wifi():
    from app.services import agents
    assert "Wi-Fi" in agents.AGENTS["network"]["focus"] and "access points" in agents.AGENTS["network"]["focus"]
    assert "Anything listed in your focus is inside your discipline" in agents.SYSTEM


def test_repair_guide_tool_for_cpe_and_it():
    from app.services import agent_tools, agents
    for t in ("cpe", "itsupport"):
        assert "repair_guide" in agent_tools.BY_TRACK[t]
    text, err = agent_tools.run_tool("cpe", {"tool": "repair_guide", "args": {"q": "computer will not turn on"}})
    assert not err and "steps" in text and "Computer will not turn on" in text
    text, err = agent_tools.run_tool("itsupport", {"tool": "repair_guide", "args": {"q": ""}})
    assert err
    assert "technician" in agents.AGENTS["cpe"]["focus"] and "repair_guide" in agents.AGENTS["cpe"]["focus"]
