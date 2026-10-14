import json

import numpy as np
import pytest

from app.services import biz_agents, biz_models, biz_packs
from app.services.db import get_cursor
from app.services.providers import Call, Turn


@pytest.fixture()
def signal_table(client):
    """A table where y really depends on x1 and group, plus noise: a model should find it."""
    rng = np.random.default_rng(1)
    with get_cursor() as cur:
        cur.execute("CREATE TABLE sig (record_date DATE, x1 DOUBLE, x2 DOUBLE, grp VARCHAR, y DOUBLE, label VARCHAR)")
        rows = []
        for i in range(400):
            x1, x2 = rng.normal(), rng.normal()
            g = "a" if i % 3 else "b"
            y = 5 * x1 + (4 if g == "b" else 0) + rng.normal() * 0.5
            rows.append([f"2026-01-{1 + i % 28:02d}", x1, x2, g, y, "hi" if y > 1 else "lo"])
        cur.executemany("INSERT INTO sig VALUES (?,?,?,?,?,?)", rows)
    return "sig"


def test_finds_real_signal_and_saves(client, signal_table):
    r = biz_models.build("sig", "y", ["x1", "x2", "grp"])
    assert r["task"] == "regression" and r["useful"] and r["importance"][0]["input"] in ("x1", "grp")
    assert "x2" not in [i["input"] for i in r["importance"][:2]]
    assert "time-ordered" in r["split"]
    p = biz_models.predict(r["id"], [{"record_date": "2026-02-01", "x1": 1.0, "x2": 0.0, "grp": "b"}, {"record_date": "2026-02-01", "x1": 1.0, "x2": 0.0, "grp": "a"}])
    assert p["predictions"][0] > p["predictions"][1] + 2          # group b adds about 4
    assert r["id"] in [m["id"] for m in biz_models.list_models()]
    c = biz_models.build("sig", "label", ["x1", "x2", "grp"])
    assert c["task"] == "classification" and c["useful"]


def test_copy_of_the_answer_is_left_out(client, signal_table):
    with get_cursor() as cur:
        cur.execute("ALTER TABLE sig ADD COLUMN y_x2 DOUBLE")
        cur.execute("UPDATE sig SET y_x2 = y * 2 + 1")
    r = biz_models.build("sig", "y")
    assert "y_x2" not in r["inputs"] and any("y_x2" in n and "copy of the answer" in n for n in r["notes"])
    forced = biz_models.build("sig", "y", ["x1", "y_x2"])
    assert "y_x2" in forced["inputs"] and any("y_x2" in n for n in forced["notes"])


def test_random_sample_data_is_reported_honestly(client):
    biz_packs.install_sample("logi-finance")
    r = biz_models.build("logi-finance", "earnings")
    assert not r["useful"] and r["importance"] == [] and "don't rely" in r["verdict"]


def test_errors_and_safety(client, signal_table):
    with pytest.raises(biz_models.ModelError, match="isn't a column"):
        biz_models.build("sig", "nope")
    with pytest.raises(biz_models.ModelError, match="No table"):
        biz_models.build("not_a_table", "y")
    with pytest.raises(biz_models.ModelError):
        biz_models.build("sig; DROP TABLE sig", "y")
    with pytest.raises(biz_models.ModelError, match="No such model"):
        biz_models.get("../../etc/passwd")
    with pytest.raises(biz_models.ModelError, match="Missing"):
        r = biz_models.build("sig", "y")
        biz_models.predict(r["id"], [{"x1": 1}])
    with pytest.raises(biz_models.ModelError, match="no data"):
        biz_models.build("retail-sales", "revenue")
    assert biz_models.delete(r["id"]) == {"deleted": r["id"]}


def test_model_endpoints(client):
    biz_packs.install_sample("saas-sales")
    r = client.post("/api/biz-packs/saas-sales/model", json={"target": "deal_value"})
    assert r.status_code == 200
    mid = r.json()["id"]
    assert client.get(f"/api/biz-models/{mid}").json()["target"] == "deal_value"
    assert client.get("/api/biz-models").json()["models"][0]["id"] == mid
    assert client.post("/api/biz-packs/saas-sales/model", json={"target": "zzz"}).status_code == 400
    assert client.delete(f"/api/biz-models/{mid}").status_code == 200
    assert client.get(f"/api/biz-models/{mid}").status_code == 404


class Fake:
    provider, model = "anthropic", "fake"

    def __init__(self, turns):
        self.turns, self.i, self.system, self.results = turns, 0, "", []

    def start(self, system, tools, question):
        self.system, self.tools = system, tools

    def next_turn(self):
        t = self.turns[self.i]
        self.i += 1
        return t

    def add_results(self, turn, results):
        self.results.extend(results)


def ask(pid, turns, msg="build a model"):
    f = Fake(turns)
    return biz_agents.chat(pid, msg, adapters={"anthropic": f, "openai": f, "google": f}, provider="anthropic"), f


def test_assistant_builds_a_model_and_reads_dashboard(client):
    biz_packs.install_sample("logi-finance")
    r, f = ask("logi-finance", [Turn("", [Call("1", "get_dashboard", {}), Call("2", "build_model", {"target": "earnings"})]), Turn("It did not beat the baseline.")])
    assert [t["tool"] for t in r.tools_used] == ["get_dashboard", "build_model"] and not any(t["error"] for t in r.tools_used)
    assert "Finance Analyst" in f.system and "biz_logi_finance" in f.system and "Net per hour" in f.system
    out = json.loads(f.results[1][1])
    assert out["useful"] is False and r.actions and "not useful" in r.actions[0]["label"]
    assert any(m["target"] == "earnings" for m in biz_models.list_models())


def test_assistant_tool_errors_and_policy(client):
    biz_packs.install_sample("saas-sales")
    r, _ = ask("saas-sales", [Turn("", [Call("1", "build_model", {"target": "nope"}), Call("2", "run_sql", {"sql": "DROP TABLE biz_saas_sales"}), Call("3", "delete_everything", {})]), Turn("ok")])
    assert [t["error"] for t in r.tools_used] == [True, True, True]
    assert biz_packs.installed("saas-sales") > 0                       # nothing was dropped
    assert client.get("/api/biz-packs/saas-sales/assistant").json()["role"] == "Sales Analyst"
    assert client.get("/api/biz-packs/nope/assistant").status_code == 404


def test_routing_google_first_claude_for_calculation(client, monkeypatch):
    from app.services import llm_router
    monkeypatch.setenv("GOOGLE_API_KEY", "x"); monkeypatch.setenv("GEMINI_API_KEY", "x"); monkeypatch.setenv("ANTHROPIC_API_KEY", "x"); monkeypatch.setenv("OPENAI_API_KEY", "x")
    st = {r["id"]: r for r in llm_router.status()["providers"]}
    for p in st.values():
        monkeypatch.setitem(p, "configured", True)
    monkeypatch.setattr(llm_router, "status", lambda: {"providers": [{**v, "configured": v["id"] != "ollama", "sdk_installed": True, "used_today": 0, "daily_limit": 99} for v in st.values()]})
    plan = lambda m: llm_router.plan(m, "auto", "auto", biz_agents.BIZ_ORDER, biz_agents.CALC_HINTS)  # noqa: E731
    assert plan("How many deliveries today?")["order"] == ["google", "anthropic"]
    assert plan("Summarize the trend this week")["order"] == ["google", "anthropic"]
    assert plan("Build a model to predict earnings")["order"] == ["anthropic", "google"]
    assert plan("Forecast next month")["order"] == ["anthropic", "google"]
    assert plan("What if fuel costs rise 20%?")["order"] == ["anthropic", "google"]
    assert "openai" not in plan("anything")["order"]


def test_ollama_is_the_last_resort_and_adapter_speaks_its_protocol(monkeypatch):
    from app.services import llm_router, providers
    monkeypatch.setenv("BI_OLLAMA_MODEL", "llama3.1")
    base = {r["id"]: r for r in llm_router.status()["providers"]}
    assert base["ollama"]["configured"] and base["ollama"]["role"].startswith("local")
    monkeypatch.setattr(llm_router, "status", lambda: {"providers": [{**v, "configured": v["id"] in ("ollama", "google"), "sdk_installed": True, "used_today": 0, "daily_limit": 99} for v in base.values()]})
    assert llm_router.plan("hi", "auto", "auto", biz_agents.BIZ_ORDER, biz_agents.CALC_HINTS)["order"] == ["google", "ollama"]
    sent = []
    replies = [{"message": {"content": "", "tool_calls": [{"function": {"name": "get_dashboard", "arguments": {"days": 7}}}]}, "prompt_eval_count": 5, "eval_count": 2},
               {"message": {"content": "Net is up."}, "done_reason": "stop", "prompt_eval_count": 9, "eval_count": 4}]

    def fake_post(path, body):
        sent.append((path, body))
        return replies[len(sent) - 1]
    ad = providers.OllamaAdapter(client=fake_post)
    ad.start("sys", [biz_agents.TOOL_DASH], "q")
    t = ad.next_turn()
    assert t.calls[0].name == "get_dashboard" and t.calls[0].args == {"days": 7} and sent[0][0] == "/api/chat" and sent[0][1]["tools"][0]["function"]["name"] == "get_dashboard"
    ad.add_results(t, [(t.calls[0], "{}", False)])
    t2 = ad.next_turn()
    assert t2.text == "Net is up." and sent[1][1]["messages"][-1]["role"] == "tool" and (t2.input_tokens, t2.output_tokens) == (9, 4)


def test_dashboard_alerts_only_in_real_and_respect_limit(client, monkeypatch):
    from app.services import alerts, biz_packs, workspaces
    biz_packs.install_sample("snf-billing")
    biz_packs.install_sample("retail-sales")
    assert biz_packs.wrong_way(30, 1)                                    # the sample has numbers moving the wrong way
    assert not [a for a in alerts.current() if a["id"].startswith("biz:")]  # Practice: no alerts from made-up data
    monkeypatch.setattr(workspaces, "active", lambda: "real")
    got = [a for a in alerts.current() if a["id"].startswith("biz:")]
    assert got and all(a["href"] == "/packs" for a in got)
    alerts.save_config({"biz_change_pct": 100})
    assert not [a for a in alerts.current() if a["id"].startswith("biz:")]
    with pytest.raises(alerts.AlertError):
        alerts.save_config({"biz_change_pct": 0})


def test_cfo_persona_on_dashboards_and_analytics_tracks_only(client):
    from app.services import agents
    client.post("/api/biz-packs/retail-sales/sample")
    r, f = ask("retail-sales", [Turn("Hold.")], "where is money leaking?")
    assert "Analyst" in f.system and "CFO" not in f.system
    f2 = Fake([Turn("Hold.")])
    biz_agents.chat("retail-sales", "where is money leaking?", adapters={"anthropic": f2, "openai": f2, "google": f2}, provider="anthropic", persona="cfo")
    assert "Chief Financial Officer (CFO)" in f2.system and "spend / hold / cut" in f2.system
    assert "cfo" in client.get("/api/biz-packs/retail-sales/assistant").json()["personas"]
    f3 = Fake([Turn("ok")])
    agents.chat("scientist", "is this worth the spend?", adapters={"anthropic": f3, "openai": f3, "google": f3}, provider="anthropic", persona="cfo")
    assert "Chief Financial Officer" in f3.system
    with pytest.raises(agents.AgentError):
        agents.chat("cpe", "hi there", provider="anthropic", persona="cfo")
