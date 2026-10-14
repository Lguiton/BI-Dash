import json

import duckdb
import pytest

from app.services import agents, sysdesign as sd


def test_capacity_math():
    c = sd.capacity({"users": 1000, "active_pct": 50, "actions_per_user_day": 86.4, "peak_factor": 4, "new_records_per_day": 1000, "record_kb": 10, "retention_months": 12})
    assert c["dau"] == 500 and c["requests_per_day"] == 43200 and c["avg_rps"] == 0.5 and c["peak_rps"] == 2.0
    assert c["storage_gb"] == pytest.approx(3.65 * 1.5, abs=0.01)
    assert c["cost_at_10x"]["total"] > c["cost"]["total"]
    with pytest.raises(sd.DesignError):
        sd.capacity({"users": -3})
    with pytest.raises(sd.DesignError):
        sd.capacity({"uptime": "100"})


def test_design_ddl_runs_and_parts_follow_needs():
    for kind in sd.KINDS:
        d = sd.design({"kind": kind, "needs": ["auth", "payments", "email", "files", "realtime", "search"], "entities": "jobs, parts"})
        con = duckdb.connect(":memory:")
        for stmt in d["ddl"].split(";\n\n"):
            con.execute(stmt.strip().rstrip(";"))
        ids = {c["id"] for c in d["components"]}
        assert {"auth", "files", "ws", "search", "pay", "mail"} <= ids
        assert all(e["from"] in ids | {"client"} and e["to"] in ids for e in d["edges"])
    small = sd.design({"kind": "booking", "users": 1})
    assert "cache" not in {c["id"] for c in small["components"]}


def test_review_tradeoffs_practice():
    r = sd.review({"kind": "booking", "uptime": "99.99", "users": 20, "needs": ["payments"], "budget_month": 1})
    t = {f["title"] for f in r["findings"]}
    assert {"Backups are only useful if restored", "Payments", "Several users but no sign-in listed", "Over budget"} <= t
    assert r["findings"][0]["severity"] == "high"
    assert len(sd.tradeoffs({})["cards"]) == 6
    g = sd.grade("url_shortener", "I would generate a base62 code from a counter, put a cache in front because reads dominate, use a table with a primary key, a 302 redirect, rate limit abuse, and 12 per second so 3 TB storage.")
    assert g["score"] == 100
    with pytest.raises(sd.DesignError):
        sd.grade("chat", "too short")
    assert "checklist" in sd.practice("chat", True)


def test_api_and_agent_tool(client):
    assert client.post("/api/sysdesign/design", json={"kind": "inventory"}).status_code == 200
    assert client.post("/api/sysdesign/review", json={"kind": "chat", "users": 5}).json()["findings"]
    assert client.post("/api/sysdesign/capacity", json={"users": "x"}).status_code == 400
    assert client.get("/api/sysdesign/practice?kind=nope").status_code == 400
    assert "booking" in client.get("/api/sysdesign/options").json()["cases"]
    out = json.loads(sd.tool_result({"action": "design", "spec": {"kind": "booking"}}))
    assert out["tables"] and "capacity_summary" in out
    assert sd.TOOL_SYS_DESIGN in [agents._design_tool()]
