from pathlib import Path

import pytest

from app.services import mlops_lab as m

ROOT = Path(__file__).resolve().parents[2]
FEATS = ["category", "weekday", "units_processed", "duration_minutes"]


@pytest.fixture()
def big(client, load_clean, tmp_path, monkeypatch):
    pytest.importorskip("sklearn")
    monkeypatch.setenv("BI_MODELS_DIR", str(tmp_path / "models"))
    return load_clean()


def _reg(c, name="rev", model="ridge", note="first"):
    r = c.post("/api/models", json={"name": name, "task": "revenue", "model": model, "features": FEATS, "note": note})
    assert r.status_code == 200
    return r.json()["version"]


def test_gate_promote_flow(big):
    v1 = _reg(big)
    g = big.post("/api/mlops/gate", json={"name": "rev", "version": v1, "min_gain": 0.0}).json()
    assert {c["id"] for c in g["checks"]} >= {"loads", "scored", "beats", "note"}
    assert g["passed"] and g["challenger_alias_set"]
    # no promotion without a confirmation
    assert big.post("/api/mlops/promote", json={"name": "rev", "min_gain": 0.0}).status_code == 400
    p = big.post("/api/mlops/promote", json={"name": "rev", "confirm": True, "min_gain": 0.0}).json()
    assert p["champion"] == v1 and p["replaced"] is None
    refs = big.get("/api/mlops").json()
    assert refs["aliases"]["rev"] == {"champion": v1} and refs["slips"] and refs["not_built"]
    # a second version challenges the champion
    v2 = _reg(big, model="random_forest", note="forest")
    assert big.post("/api/mlops/gate", json={"name": "rev", "version": v2, "min_gain": 0.0}).json()["challenger_alias_set"] in (True, False)
    if big.get("/api/mlops/compare?name=rev&min_gain=0").status_code == 200:
        c = big.get("/api/mlops/compare?name=rev&min_gain=0").json()
        assert c["champion"] == v1 and c["decision"] in ("promote", "hold")
        s = big.post("/api/mlops/shadow", json={"name": "rev", "rows": 20})
        assert s.status_code == 200 and "limit" in s.json() and s.json()["rows"] == 20
    # roll back by hand
    assert big.post("/api/mlops/rollback", json={"name": "rev", "version": v1}).status_code == 400
    assert big.post("/api/mlops/rollback", json={"name": "rev", "version": v1, "confirm": True}).json()["champion"] == v1


def test_gate_blocks_weak_model_and_missing_challenger(big):
    v = _reg(big, note="")
    pr = big.get(f"/api/models/rev/card?version={v}").json()["primary"]
    g = big.post("/api/mlops/gate", json={"name": "rev", "version": v, "min_gain": 1.0}).json()
    beats = next(c for c in g["checks"] if c["id"] == "beats")
    assert beats["ok"] == (pr["model"] >= pr["baseline"] + 1.0)
    if not beats["ok"]:
        assert not g["passed"] and not g["challenger_alias_set"]
    # a missing note is only a warning, never a block
    assert next(c for c in g["checks"] if c["id"] == "note")["level"] == "warn"
    if not g["passed"]:
        assert big.get("/api/mlops/compare?name=rev").status_code == 409
    assert big.post("/api/mlops/shadow", json={"name": "rev"}).status_code == 409      # no champion yet either way
    assert big.get("/api/mlops/compare?name=other").status_code == 409


def test_load_test_and_retrain(big):
    v = _reg(big)
    r = big.post("/api/mlops/load", json={"name": "rev", "requests": 10, "p95_ms": 60000}).json()
    assert r["requests_done"] == 10 and r["p50_ms"] <= r["p95_ms"] <= r["p99_ms"] and r["meets_latency"] and r["error_pct"] == 0 and "no network" in r["limit"]
    strict = big.post("/api/mlops/load", json={"name": "rev", "requests": 5, "p95_ms": 0.1}).json()
    assert strict["verdict"] == "misses the target"
    assert big.post("/api/mlops/load", json={"name": "rev", "requests": 100000}).status_code == 400
    assert big.get("/api/mlops/retrain?name=rev").json()["status"] == "no model"
    big.put(f"/api/models/rev/versions/{v}/stage", json={"stage": "production"})
    assert big.get("/api/mlops/retrain?name=rev").json()["status"] == "no data"
    big.get("/api/models/rev/drift")
    out = big.get("/api/mlops/retrain?name=rev").json()
    assert out["status"] in ("stable", "watch", "investigate") and out["limit"]


def test_split_and_rollout():
    s = m.traffic_split(2000, 10)
    assert s["challenger_requests"] + s["champion_requests"] == 2000 and s["expected_range_pct"][0] <= s["observed_pct"] <= s["expected_range_pct"][1]
    assert m.traffic_split(2000, 10) == s            # the same ids always get the same model
    assert m.traffic_split(100, 0)["challenger_requests"] == 0
    p = m.rollout_plan([5, 50, 100], 100, 1, 3)
    assert [x["challenger_pct"] for x in p["steps"]] == [5, 50, 100] and len(p["compare"]) == 3
    for bad in ([50, 5, 100], [5, 50], [], [0, 100]):
        with pytest.raises(m.MlopsError):
            m.rollout_plan(bad)


def test_llm_plan():
    base = m.llm_plan({})
    assert base["stack"][0]["step"].startswith("Prompt") and len(base["stack"]) == 1 and base["hosting"]["choice"] == "Hosted API"
    rag = m.llm_plan({"private_knowledge": True, "knowledge_changes": True})
    assert any("RAG" in s["step"] for s in rag["stack"]) and rag["retrieval_store"]["choice"] == "Vector database"
    ft = m.llm_plan({"needs_style": True, "labeled_examples": 5000, "requests_per_day": 100000})
    assert any("Fine-tune" in s["step"] for s in ft["stack"])
    few = m.llm_plan({"needs_style": True, "labeled_examples": 50})
    assert not any("Fine-tune" in s["step"] for s in few["stack"]) and any("examples" in s["why"] for s in few["stack"])
    own = m.llm_plan({"data_cannot_leave": True})
    assert own["hosting"]["choice"] == "Self-hosted open model" and any("GPU" in r for r in own["hosting"]["reasons"])
    assert not any("Pre-train" in s["step"] for s in m.llm_plan({"corpus_tokens": 1e11})["stack"])   # needs the unique-domain answer too
    assert any("Pre-train" in s["step"] for s in m.llm_plan({"corpus_tokens": 1e11, "unique_domain": True})["stack"])
    with pytest.raises(m.MlopsError):
        m.llm_plan({"labeled_examples": "lots"})


def test_feedback(client):
    for k in ("thumbs_up", "thumbs_up", "thumbs_down", "escalated"):
        assert client.post("/api/mlops/feedback", json={"kind": k, "prompt": "support bot", "version": 2}).status_code == 200
    s = client.get("/api/mlops/feedback").json()
    g = s["groups"][0]
    assert s["total"] == 4 and g["good"] == 2 and g["bad"] == 2 and g["helpful_pct"] == 50 and not g["enough"] and "hint" in g["note"]
    assert client.post("/api/mlops/feedback", json={"kind": "love"}).status_code == 400
    assert client.delete("/api/mlops/feedback").json()["cleared"] and client.get("/api/mlops/feedback").json()["total"] == 0
