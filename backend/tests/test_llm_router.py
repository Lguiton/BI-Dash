"""Routing, fallback and the three vendor adapters, all with fakes (no network, no keys, no cost)."""
from types import SimpleNamespace as NS

import pytest

from app.services import ai_agent, llm_router, providers
from app.services.ai_agent import AiError

KEYS = ("GOOGLE_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    for p in ("GOOGLE", "OPENAI", "ANTHROPIC"):
        monkeypatch.delenv(f"BI_LIMIT_{p}", raising=False)
    llm_router.reset_usage()
    yield
    llm_router.reset_usage()


def all_keys(mp):
    for k in ("GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        mp.setenv(k, "fake")


class Stub:
    """A scripted adapter: replies with `text`, or raises AiError-producing ProviderError."""
    def __init__(self, provider, text="", fail=None):
        self.provider, self.model, self._text, self._fail = provider, f"{provider}-model", text, fail
    def start(self, *a): pass
    def next_turn(self):
        if self._fail:
            raise providers.ProviderError(self._fail, 429)
        return providers.Turn(self._text, [], False, 7, 3)
    def add_results(self, *a): pass


def stubs(**kw): return {p: Stub(p, text=f"answer from {p}", fail=kw.get(p)) for p in ("google", "openai", "anthropic")}


# ---- classification and plan ----
@pytest.mark.parametrize("q,kind", [
    ("How many records are there?", "simple"), ("Which entity earns the most?", "simple"),
    ("Write python code to compute margin", "complex"), ("Why did revenue drop in March?", "complex"),
    ("Is there a seasonal trend?", "complex"), ("x" * 300, "complex"),
])
def test_classify(q, kind):
    assert llm_router.classify(q)[0] == kind
    assert llm_router.classify("hello", "complex")[0] == "complex"


def test_plan_order_and_skips(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "x"); monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    p = llm_router.plan("How many records?")
    assert p["order"] == ["google", "anthropic"] and p["skipped"][0]["provider"] == "openai" and "OPENAI_API_KEY" in p["skipped"][0]["why"]
    assert llm_router.plan("Write python code for this")["order"] == ["anthropic", "google"]
    assert llm_router.plan("hi there", provider="openai")["order"] == ["openai"]


def test_gemini_alias_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert providers.api_key("google") == "x" and "google" in llm_router.status()["ready"]


# ---- routing, caps, fallback ----
def test_simple_goes_to_google_and_complex_to_claude(monkeypatch):
    all_keys(monkeypatch)
    r = llm_router.ask("How many records?", adapters=stubs())
    assert (r.provider, r.answer) == ("google", "answer from google") and r.route["kind"] == "simple"
    r = llm_router.ask("Explain why margins fell", adapters=stubs())
    assert r.provider == "anthropic" and r.route["kind"] == "complex"


def test_fallback_when_provider_fails(monkeypatch):
    all_keys(monkeypatch)
    r = llm_router.ask("How many records?", adapters=stubs(google="Google Gemini is rate limiting requests"))
    assert r.provider == "openai"
    assert [(a["provider"], a["ok"]) for a in r.attempts] == [("google", False), ("openai", True)]
    r = llm_router.ask("How many records?", adapters=stubs(google="x", openai="y"))
    assert r.provider == "anthropic"


def test_all_providers_failing(monkeypatch):
    all_keys(monkeypatch)
    with pytest.raises(AiError) as e:
        llm_router.ask("How many records?", adapters=stubs(google="a", openai="b", anthropic="c"))
    assert e.value.status == 429 and "google" in str(e.value) and "anthropic" in str(e.value)


def test_daily_cap_spreads_load(monkeypatch):
    all_keys(monkeypatch)
    monkeypatch.setenv("BI_LIMIT_GOOGLE", "2")
    got = [llm_router.ask("How many records?", adapters=stubs()).provider for _ in range(4)]
    assert got == ["google", "google", "openai", "openai"]
    assert llm_router.used_today("google") == 2
    monkeypatch.setenv("BI_LIMIT_OPENAI", "2")
    assert llm_router.ask("How many records?", adapters=stubs()).provider == "anthropic"


def test_nothing_configured(monkeypatch):
    with pytest.raises(AiError) as e:
        llm_router.ask("How many records?", adapters=stubs())
    assert e.value.status == 503 and "backend/.env" in str(e.value)


# ---- the three real adapters, driven by SDK-shaped fakes ----
def run_agent(adapter):
    return ai_agent.ask("How many records?", adapter=adapter)


def test_openai_adapter_round_trip(client):
    sent = []
    def create(**kw):
        sent.append(kw)
        if len(sent) == 1:
            tc = NS(id="call_1", type="function", function=NS(name="run_sql", arguments='{"sql": "SELECT COUNT(*) FROM fact_operations"}'))
            return NS(choices=[NS(message=NS(content=None, tool_calls=[tc]), finish_reason="tool_calls")], usage=NS(prompt_tokens=11, completion_tokens=4))
        return NS(choices=[NS(message=NS(content="Six records.", tool_calls=None), finish_reason="stop")], usage=NS(prompt_tokens=20, completion_tokens=5))
    fake = NS(chat=NS(completions=NS(create=create)))
    r = run_agent(providers.OpenAIAdapter(fake, model="m"))
    assert r.answer == "Six records." and r.provider == "openai" and (r.input_tokens, r.output_tokens) == (31, 9)
    assert r.steps[0].tool == "run_sql" and '"rows": [[6]]' in r.steps[0].output
    first, second = sent
    assert first["tools"][0]["type"] == "function" and first["messages"][0]["role"] == "system"
    assert second["messages"][-1] == {"role": "tool", "tool_call_id": "call_1", "content": r.steps[0].output}
    assert second["messages"][-2]["tool_calls"][0]["function"]["name"] == "run_sql"


def test_openai_bad_tool_arguments_do_not_crash(client):
    def create(**kw):
        if not hasattr(create, "done"):
            create.done = True
            tc = NS(id="c", type="function", function=NS(name="run_sql", arguments="{not json"))
            return NS(choices=[NS(message=NS(content=None, tool_calls=[tc]), finish_reason="tool_calls")], usage=None)
        return NS(choices=[NS(message=NS(content="sorry", tool_calls=None), finish_reason="stop")], usage=None)
    r = run_agent(providers.OpenAIAdapter(NS(chat=NS(completions=NS(create=create)))))
    assert r.steps[0].is_error and r.answer == "sorry"


def test_gemini_adapter_round_trip(client):
    genai_types = pytest.importorskip("google.genai.types")
    T = genai_types
    calls = []
    def gen(model, contents, config):
        calls.append((model, list(contents), config))
        if len(calls) == 1:
            part = T.Part(function_call=T.FunctionCall(name="run_sql", args={"sql": "SELECT COUNT(*) FROM fact_operations"}))
            parts, usage = [part], T.GenerateContentResponseUsageMetadata(prompt_token_count=9, candidates_token_count=2)
        else:
            parts, usage = [T.Part(text="Six records.")], T.GenerateContentResponseUsageMetadata(prompt_token_count=15, candidates_token_count=3)
        return T.GenerateContentResponse(candidates=[T.Candidate(content=T.Content(role="model", parts=parts), finish_reason="STOP")], usage_metadata=usage)
    fake = NS(models=NS(generate_content=gen))
    r = run_agent(providers.GeminiAdapter(fake, model="m"))
    assert r.answer == "Six records." and r.provider == "google" and (r.input_tokens, r.output_tokens) == (24, 5)
    assert r.steps[0].tool == "run_sql" and '"rows": [[6]]' in r.steps[0].output
    contents = calls[1][1]
    assert [c.role for c in contents] == ["user", "model", "user"]
    assert contents[-1].parts[0].function_response.name == "run_sql"
    decls = calls[0][2].tools[0].function_declarations
    assert {d.name for d in decls} == {"get_schema", "run_sql"} and [d for d in decls if d.name == "get_schema"][0].parameters is None
    assert calls[0][2].automatic_function_calling.disable is True


def test_provider_errors_are_translated():
    class RateLimitError(Exception): ...
    class AuthenticationError(Exception): ...
    class ClientError(Exception):
        code = 404
    assert providers.translate("openai", RateLimitError()).status == 429
    assert providers.translate("anthropic", AuthenticationError()).status == 401
    e = providers.translate("google", ClientError())
    assert e.status == 400 and "BI_GOOGLE_MODEL" in str(e)
    assert providers.translate("google", RuntimeError()).status == 502
