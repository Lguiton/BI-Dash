import pytest

from app.services import ai_agent, ai_policy, sql_lab


def _set(client, ws, **kw):
    assert client.put(f"/api/workspaces/{ws}/settings", json=kw).status_code == 200


def test_real_defaults_to_off_and_blocks_the_endpoint(client):
    client.post("/api/workspaces/active", json={"name": "real"})
    st = client.get("/api/ai/status").json()["policy"]
    assert st["mode"] == "off" and st["allowed"] is False
    r = client.post("/api/ai/ask", json={"question": "what is revenue?"})
    assert r.status_code == 403
    assert any(e["action"] == "ai_ask" and not e["ok"] for e in client.get("/api/audit").json()["entries"])


def test_practice_is_full_by_default(client):
    assert client.get("/api/ai/status").json()["policy"]["mode"] == "full"


def test_blocked_columns_hidden_and_rejected(client):
    _set(client, "practice", blocked_columns=["Revenue", "name"])
    schema = ai_agent._tool_get_schema()
    assert "revenue" not in schema.lower().split("fact_operations")[1].split("\n")[0]
    out, err = ai_agent._run_tool("run_sql", {"sql": "SELECT SUM(revenue) FROM fact_operations"})
    assert err and "blocked" in out
    out, err = ai_agent._run_tool("run_sql", {"sql": "SELECT * FROM fact_operations"})
    assert err and "blocked" in out.lower()
    out, err = ai_agent._run_tool("run_sql", {"sql": "SELECT f FROM fact_operations f"})
    assert err
    out, err = ai_agent._run_tool("run_sql", {"sql": "SELECT COUNT(*) AS n FROM fact_operations"})
    assert not err
    out, err = ai_agent._run_tool("show_chart", {"sql": "SELECT record_date AS d, revenue AS r FROM fact_operations", "kind": "line", "x": "d", "y": "r", "title": "t"})
    assert err


def test_aggregate_mode_requires_summaries_and_caps_rows(client):
    _set(client, "practice", ai_mode="aggregate")
    out, err = ai_agent._run_tool("run_sql", {"sql": "SELECT * FROM fact_operations"})
    assert err and "summary" in out
    out, err = ai_agent._run_tool("run_sql", {"sql": "SELECT entity_id, SUM(revenue) AS r FROM fact_operations GROUP BY 1"})
    assert not err


def test_off_mode_blocks_tools_too(client):
    _set(client, "practice", ai_mode="off")
    out, err = ai_agent._run_tool("run_sql", {"sql": "SELECT 1"})
    assert err and "switched off" in out
