import pytest

TRACKS = ["analyst", "scientist", "ml", "engineering", "ai"]


@pytest.fixture()
def big(client):
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    r = client.post("/api/ingest/csv?mode=replace", files={"file": ("d.csv", (root / "data_samples" / "operations_clean.csv").read_bytes(), "text/csv")})
    assert r.status_code == 200
    return client


@pytest.mark.parametrize("tid", TRACKS)
def test_every_dashboard_loads_on_demo_data(client, tid, tmp_path, monkeypatch):
    from app.services import pipeline
    monkeypatch.setattr(pipeline, "LAKE", tmp_path / "lake")
    r = client.get(f"/api/tracks/{tid}/dashboard")
    assert r.status_code == 200 and r.json()["track"] == tid and r.json()["ideas"]


def test_unknown_track(client):
    assert client.get("/api/tracks/hacker/dashboard").status_code == 404


def test_analyst_numbers_match_sql(big):
    d = big.get("/api/tracks/analyst/dashboard").json()
    assert d["kpis"]["records"] == 3650 and 0 < d["kpis"]["margin_pct"] < 100
    assert d["over_budget"] == sorted(d["over_budget"], key=lambda r: -r["vs_budget_pct"])
    assert len(d["weekly_margin"]) == 26 and d["quality"]["total"] >= 9


def test_scientist_stats(big):
    d = big.get("/api/tracks/scientist/dashboard").json()
    w = d["weekend_test"]
    assert w["available"] and w["ci_low"] < w["diff"] < w["ci_high"] and 0 <= w["p_value"] <= 1 and w["weekend_days"] > 50
    seg = d["segments"]
    assert seg["available"] and sorted(e for s in seg["segments"] for e in s["entities"]) and len(seg["segments"]) == 3
    c = d["correlations"]
    assert c["available"] and all(abs(c["matrix"][i][i] - 1) < 1e-6 for i in range(4))


def test_ml_dashboard_logs_runs(big):
    assert big.get("/api/tracks/ml/dashboard").json()["total_runs"] == 0
    big.post("/api/ml/train", json={"task": "revenue", "model": "ridge", "features": ["units_processed", "category"]})
    big.post("/api/ml/train", json={"task": "revenue", "model": "linear", "features": ["units_processed"]})
    d = big.get("/api/tracks/ml/dashboard").json()
    assert d["total_runs"] == 2 and d["best"][0]["task"] == "revenue" and d["best"][0]["lift"] > 0


def test_ai_dashboard_counts_questions(client, monkeypatch):
    from tests.test_ai import FakeClient, reply, text
    from app.services import providers
    for k in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setitem(providers.ADAPTERS, "anthropic", lambda: providers.AnthropicAdapter(FakeClient([reply([text("Six.")])])))
    assert client.post("/api/ai/ask", json={"question": "how many records?"}).status_code == 200
    d = client.get("/api/tracks/ai/dashboard").json()
    assert d["log"]["totals"]["questions"] == 1 and d["log"]["recent"][0]["provider"] == "anthropic"


def test_progress_flow(client):
    p = client.get("/api/progress").json()
    assert p["overall_pct"] == 0 and len(p["tracks"]) == 5 and p["continue"]["track"] == "analyst"
    first = p["tracks"][0]["next"]["id"]
    assert client.put("/api/progress", json={"item": first, "done": True}).status_code == 200
    p = client.get("/api/progress").json()
    assert first in p["done"] and p["tracks"][0]["done"] == 1 and p["tracks"][0]["next"]["id"] != first
    assert p["continue"]["track"] == "analyst" and p["overall_pct"] > 0
    assert client.put("/api/progress", json={"item": first, "done": False}).status_code == 200
    assert client.get("/api/progress").json()["done"] == []
    for bad in ("nope:nothing", "../etc", "analyst:made-up-step"):
        assert client.put("/api/progress", json={"item": bad, "done": True}).status_code in (404, 422)
