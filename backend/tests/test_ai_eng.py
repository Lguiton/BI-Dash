import pytest
from app.services import ai_eng_lab as a


def test_tokens_fit_chunks():
    t = a.estimate_tokens("word " * 400)
    assert 400 <= t["estimated_tokens"] <= 700 and t["range"][0] < t["estimated_tokens"] < t["range"][1]
    assert a.estimate_tokens("if (x) { y = 1; }" * 50)["estimated_tokens"] > a.estimate_tokens("a" * 850)["estimated_tokens"] * 0.9
    assert a.context_fit(7500, 8000, 1000)["fits"] is False
    f = a.context_fit(1000, 8000, 1000)
    assert f["fits"] and f["left"] > 0
    assert any("middle" in n for n in a.context_fit(6000, 8000, 100, 5)["notes"])
    c = a.chunk_plan(10000, 300, 40, 3, 100, 3)
    assert c["chunks"] == 39 and c["tokens_per_question"] == 3 * 300 + 40 + 200 and c["input_cost_per_month"] > 0
    with pytest.raises(a.AieError):
        a.chunk_plan(1000, 100, 100)


def test_rag_eval():
    r = a.reference()
    e = a.rag_eval(r["example_docs"], r["example_cases"])
    assert e["answerable"] == 4 and e["unanswerable"] == 1 and all(s["hit_rate"] == 1.0 for s in e["sizes"])
    # a question with no wording in common should be missed
    e2 = a.rag_eval(r["example_docs"], [{"question": "give me my money back", "expected": ["5 business days"]}])
    assert e2["sizes"][0]["hit_rate"] == 0 and any("synonym" in n for n in e2["notes"])
    with pytest.raises(a.AieError):
        a.rag_eval([], r["example_cases"])
    with pytest.raises(a.AieError):
        a.rag_eval(r["example_docs"], [{"question": ""}])


def test_tool_safety():
    r = a.reference()
    t = a.tool_safety(r["example_tools"])
    assert t["private_untrusted_external_all_present"] and t["verdict"] == "high risk"
    assert any(f["tool"] == "delete_file" and f["level"] == "bad" for f in t["findings"])
    safe = a.tool_safety([{"name": "search", "reads_untrusted": True}, {"name": "notes", "writes": True, "confirm": True, "limit": True}])
    assert safe["verdict"] == "reasonable" and not safe["private_untrusted_external_all_present"]
    with pytest.raises(a.AieError):
        a.tool_safety([{"name": "x"}, {"name": "x"}])


def test_prompts_and_compare(client):
    a.prompt_save("support bot", "You are helpful.\nBe brief.", "first")
    a.prompt_save("support bot", "You are helpful.\nBe brief.\nCite the policy.", "added cite")
    with pytest.raises(a.AieError):
        a.prompt_save("support bot", "You are helpful.\nBe brief.\nCite the policy.")
    assert [v["v"] for v in a.prompts()["prompts"][0]["versions"]] == [1, 2]
    d = a.prompt_diff("support bot", 1, 2)
    assert d["lines_added"] == 1 and "+Cite the policy." in d["diff"]
    with pytest.raises(a.AieError):
        a.prompt_get("support bot", 9)
    with pytest.raises(a.AieError):
        a.prompt_save("bad/name", "x")
    cases = [{"id": "r", "must_include": ["5 days"]}, {"id": "u", "must_include": ["don't know"], "max_chars": 50}]
    c = a.compare_versions(cases, {"r": "within 5 days", "u": "I don't know"}, {"r": "soon", "u": "I don't know"})
    assert c["regressions"] == ["r"] and c["a_passed"] == 2 and c["b_passed"] == 1 and "worse" in c["verdict"]
    assert a.prompt_delete("support bot")["deleted"] == "support bot" and a.prompts()["prompts"] == []


def test_cost():
    base = a.cost_plan(1000, 2000, 500, 3, 15)
    assert base["base"] == pytest.approx(30 * 1000 * (2000 / 1e6 * 3 + 500 / 1e6 * 15))
    both = a.cost_plan(1000, 2000, 500, 3, 15, 50, 90, 40, 0.25, 1.25)
    assert both["with_both"] < both["with_cache"] < both["base"] and both["with_both"] < both["with_routing"]
    with pytest.raises(a.AieError):
        a.cost_plan(1000, 2000, 500, 3, 15, 0, 90, 40)


def test_routes(client):
    ref = client.get("/api/aieng").json()
    assert ref["checklist"] and ref["not_built"]
    assert client.post("/api/aieng/tokens", json={"text": "hello there"}).status_code == 200
    assert client.post("/api/aieng/fit", json={"prompt_tokens": 100, "window_tokens": 8000}).json()["fits"]
    assert client.post("/api/aieng/rag-eval", json={"docs": ref["example_docs"], "cases": ref["example_cases"]}).status_code == 200
    assert client.post("/api/aieng/tool-safety", json={"tools": ref["example_tools"]}).json()["score"] < 50
    assert client.post("/api/aieng/prompts", json={"name": "p1", "text": "hello"}).json()["version"] == 1
    assert client.post("/api/aieng/prompts", json={"name": "p1", "text": "hello"}).status_code == 400
    assert client.get("/api/aieng/prompts/p1/1").json()["text"] == "hello"
    assert client.delete("/api/aieng/prompts/p1").status_code == 200
    assert client.post("/api/aieng/cost", json={"requests_per_day": 10, "input_tokens": 100, "output_tokens": 50, "price_in_per_million": 1, "price_out_per_million": 2}).status_code == 200


# ------------------------------------------------------------------ live prompt tests (fake model)
class _Turn:
    def __init__(self, text):
        self.text, self.input_tokens, self.output_tokens = text, 10, 5


class _Fake:
    provider, model = "anthropic", "fake-model"

    def start(self, system, tools, question):
        self.system, self.question = system, question

    def next_turn(self):
        # a prompt that says "guarantee" makes the model over-promise: simulates a regression
        if "refund" in self.question.lower():
            return _Turn("Refunds are guaranteed instantly." if "OVERPROMISE" in self.system else "Refunds take 5 business days.")
        return _Turn("I don't know.")

    def add_results(self, turn, results):
        pass


def _fakes():
    f = _Fake()
    return {"anthropic": f, "openai": f, "google": f}


@pytest.fixture()
def keys(monkeypatch):
    from app.services import llm_router
    for k in ("GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.setenv(k, "x")
    llm_router.reset_usage()


def test_live_run_needs_confirm_and_finds_regression(client, keys):
    cases = a.reference()["example_prompt_cases"]
    a.prompt_save("bot", "Answer from the policy.", "v1")
    a.prompt_save("bot", "OVERPROMISE Answer from the policy.", "v2")
    plan = a.live_plan("bot", 1, 2, cases)
    assert plan["calls"] == 4 and plan["estimated_input_tokens"] > 0 and plan["warnings"]
    with pytest.raises(a.AieError):
        a.live_run("bot", 1, 2, cases, confirm=False, adapters=_fakes())
    r = a.live_run("bot", 1, 2, cases, confirm=True, adapters=_fakes())
    assert r["calls"] == 4 and r["regressions"] == ["refund"] and r["a_passed"] == 2 and r["b_passed"] == 1
    assert a.live_history()[0]["regressions"] == ["refund"]
    # single-version run
    s = a.live_run("bot", 1, None, cases, confirm=True, adapters=_fakes())
    assert s["calls"] == 2 and s["comparison"] is None
    with pytest.raises(a.AieError):
        a.live_plan("bot", 1, 2, [{"id": "x"}])
    with pytest.raises(a.AieError):
        a.live_plan("bot", 1, 9, cases)


def test_live_run_respects_ai_off_and_aborts(client, keys, monkeypatch):
    from app.services import ai_policy, ai_agent
    a.prompt_save("bot2", "Answer.", "v1")
    cases = a.reference()["example_prompt_cases"]
    monkeypatch.setattr(ai_policy, "describe", lambda: {"allowed": False})
    with pytest.raises(a.AieError) as e:
        a.live_run("bot2", 1, None, cases, confirm=True, adapters=_fakes())
    assert e.value.status == 403
    monkeypatch.setattr(ai_policy, "describe", lambda: {"allowed": True})

    class Boom(_Fake):
        def next_turn(self):
            raise ai_agent.AiError("no capacity", 503)
    b = Boom()
    r = a.live_run("bot2", 1, None, cases, confirm=True, adapters={"anthropic": b, "openai": b, "google": b})
    assert r["aborted"] and r["errors"]


def test_live_routes(client, keys):
    client.post("/api/aieng/prompts", json={"name": "rt", "text": "Answer."})
    cases = a.reference()["example_prompt_cases"]
    assert client.post("/api/aieng/live/plan", json={"name": "rt", "a": 1, "cases": cases}).json()["calls"] == 2
    r = client.post("/api/aieng/live/run", json={"name": "rt", "a": 1, "cases": cases, "confirm": False})
    assert r.status_code == 400 and "real model" in r.json()["detail"]
    assert client.get("/api/aieng/live/history").status_code == 200
