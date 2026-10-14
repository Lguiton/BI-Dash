import asyncio
import importlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["BI_OFFLINE"] = "1"   # tests must always use the offline stub, even if backend/.env has real keys


def mod(name):
    return importlib.import_module(name)


def test_structured_output_validates_and_retries(monkeypatch):
    so = mod("01_structured_output")
    t = so.extract(so.NOTES[0])
    assert t.severity == 4 and t.revenue_at_risk_usd == 1200 and t.entity == "Zone West Central"
    calls = iter(['{"entity": "x", "issue": "y", "severity": 9, "revenue_at_risk_usd": 1}',   # invalid: severity > 5
                  '```json\n{"entity": "x", "issue": "y", "severity": 2, "revenue_at_risk_usd": 1}\n```'])
    monkeypatch.setattr(so, "complete", lambda s, p: next(calls))
    assert so.extract("anything").severity == 2          # second attempt accepted, fence stripped


def test_structured_output_gives_up(monkeypatch):
    so = mod("01_structured_output")
    monkeypatch.setattr(so, "complete", lambda s, p: "not json")
    with pytest.raises(ValueError):
        so.extract("x", max_tries=2)


def test_rag_retrieves_relevant_doc_and_admits_ignorance():
    rag = mod("02_rag")
    r = rag.Retriever(rag.load_chunks())
    out = rag.answer("How is margin calculated?", r)
    assert out["citations"] and "[1]" in out["answer"]
    assert "I don't know" in rag.answer("What is the capital of France?", r)["answer"]


def test_eval_catches_average_of_ratios():
    ev = mod("03_evals")
    res = {r["q"]: r["ok"] for r in ev.run_eval()}
    assert res["Overall profit margin?"] is False and res["Total revenue?"] is True


def test_eval_scores_a_perfect_model():
    ev = mod("03_evals")
    gold = {c["q"]: c["sql"] for c in ev.GOLDEN}
    assert all(r["ok"] for r in ev.run_eval(lambda q: gold[q]))


def test_eval_guardrail_blocks_destructive_sql():
    ev = mod("03_evals")
    res = ev.run_eval(lambda q: "DROP TABLE operations")
    assert not any(r["ok"] for r in res) and all("guardrail" in r["why"] for r in res)


@pytest.mark.parametrize("sql,ok", [
    ("SELECT 1", True), ("with a as (select 1) select * from a", True),
    ("DROP TABLE operations", False), ("SELECT 1; DROP TABLE x", False),
    ("COPY operations TO 'x.csv'", False), ("PRAGMA database_list", False),
    ("WITH a AS (SELECT 1) DELETE FROM operations", False), ("", False),
])
def test_select_only(sql, ok):
    from data import is_select_only
    assert is_select_only(sql) is ok


def test_injection_gate():
    pi = mod("05_prompt_injection")
    assert pi.gate_tool_call("send_email", {})[0] is False
    assert pi.gate_tool_call("run_select", {"sql": "SELECT 1"})[0] is True
    assert pi.gate_tool_call("run_select", {"sql": "DROP TABLE a"})[0] is False
    wrapped = pi.wrap_untrusted("hi\x00‮ there " + "x" * 500)
    assert "\x00" not in wrapped and "‮" not in wrapped and "<untrusted_data>" in wrapped and len(wrapped) < 400


def test_mcp_server_tools():
    pytest.importorskip("mcp")
    srv = mod("04_mcp_server")
    names = {t.name for t in asyncio.run(srv.mcp.list_tools())}
    assert {"describe_schema", "run_select", "kpi_summary"} <= names
    assert "Rejected" in srv.run_select("DROP TABLE operations")
    assert "count" in srv.run_select("SELECT count(*) AS count FROM operations")
    assert "margin=" in srv.kpi_summary()


def test_llm_routing_and_fallback(monkeypatch):
    llm = mod("llm")
    monkeypatch.delenv("BI_OFFLINE", raising=False)
    for k in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert llm.available() == [] and llm.complete("s", "unmatched prompt") == "I can't answer that offline."
    for k in ("GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.setenv(k, "fake")
    seen = []
    def fake_call(p, s, prompt, mt=800):
        seen.append(p)
        if p == "google":
            raise RuntimeError("rate limited")
        return f"from {p}"
    monkeypatch.setattr(llm, "call", fake_call)
    assert llm.complete("s", "p") == "from openai" and seen == ["google", "openai"] and llm.last_provider == "openai"
    seen.clear()
    assert llm.complete("s", "p", kind="complex") == "from anthropic" and seen == ["anthropic"]
    assert llm.complete("s", "p", provider="openai") == "from openai"


def test_llm_all_fail(monkeypatch):
    llm = mod("llm")
    monkeypatch.delenv("BI_OFFLINE", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    monkeypatch.setattr(llm, "call", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    with pytest.raises(RuntimeError):
        llm.complete("s", "p")
