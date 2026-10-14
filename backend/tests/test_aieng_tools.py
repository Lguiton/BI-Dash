import pytest

from app.services import aieng_tools as ai

CASES = [{"id": "a", "prompt": "Refund policy?", "checks": [{"type": "contains", "value": "30 days"}, {"type": "not_contains", "value": "guarantee"}, {"type": "max_words", "value": "20"}]},
         {"id": "b", "prompt": "Hours?", "checks": [{"type": "regex", "value": r"\b9\b"}]}]


def test_eval_scoring_and_compare(client):
    s = ai.eval_save("Support bot", CASES, "You are a support bot.")
    r1 = ai.eval_score(s["id"], {"a": "Refunds within 30 days.", "b": "We open at 9."}, "v1")
    assert r1["pass_rate"] == 100 and r1["compare"] is None
    r2 = ai.eval_score(s["id"], {"a": "We guarantee refunds.", "b": "We open at 9."}, "v2")
    assert r2["pass_rate"] == 50 and r2["compare"]["regressed"] == ["a"] and "got worse" in r2["compare"]["says"]
    r3 = ai.eval_score(s["id"], {"b": "9"}, "v3")
    assert r3["results"][0]["failed"] == ["no answer was given"]
    assert ai.eval_list()[0]["runs"] == 3
    for bad in ([{"prompt": "x", "checks": []}], [{"prompt": "x", "checks": [{"type": "regex", "value": "(a+)+"}]}], [{"prompt": "x", "checks": [{"type": "magic", "value": "1"}]}], []):
        with pytest.raises(ai.AiError):
            ai.eval_save("bad", bad)
    ai.eval_delete(s["id"])
    with pytest.raises(ai.AiError):
        ai.eval_get(s["id"])


def test_live_run_uses_router(client, monkeypatch):
    s = ai.eval_save("Live", CASES[1:])
    monkeypatch.setattr(ai.llm_router, "complete", lambda system, prompt, **k: {"text": "Open at 9"})
    assert ai.eval_run_live(s["id"], "live")["pass_rate"] == 100

    def boom(*a, **k):
        raise RuntimeError("no key")
    monkeypatch.setattr(ai.llm_router, "complete", boom)
    with pytest.raises(ai.AiError) as e:
        ai.eval_run_live(s["id"])
    assert e.value.status == 503


def test_prompts_versions_diff(client):
    ai.prompt_save("Greeter", "Say hello.\nBe brief.", "first")
    with pytest.raises(ai.AiError):
        ai.prompt_save("Greeter", "Say hello.\nBe brief.")
    ai.prompt_save("Greeter", "Say hello.\nBe warm.", "warmer")
    d = ai.prompt_diff("Greeter", 1, 2)
    assert any(l.startswith("-Be brief") for l in d["diff"]) and any(l.startswith("+Be warm") for l in d["diff"])
    with pytest.raises(ai.AiError):
        ai.prompt_diff("Greeter", 1, 9)


def test_cost_and_docs(client):
    c = ai.cost(1000, 500, 200, "medium", retry_pct=0)
    assert abs(c["per_request"] - (500 * 3 + 200 * 15) / 1e6) < 1e-9 and c["per_month"] == round(c["per_request"] * 1000 * 30, 2)
    assert ai.cost(10, 100, 100, price_in=1, price_out=2)["prices_used"]["label"] == "your prices"
    with pytest.raises(ai.AiError):
        ai.cost(0, 1, 1)
    h = ai.risk_register("Bot <i>x</i>")
    assert "<i>x</i>" not in h and "hallucination" in h
    with pytest.raises(ai.AiError):
        ai.risk_register("x", [{"risk": "r", "likelihood": 9, "impact": 1}])
    s = ai.eval_save("S", CASES)
    ai.eval_score(s["id"], {"a": "30 days", "b": "9"})
    pack = ai.handoff({"name": "Bot <b>", "suite_id": s["id"], "tools": ["search <x>"]})
    assert "&lt;b&gt;" in pack and "100.0%" in pack and "&lt;x&gt;" in pack and "not filled in" in pack
