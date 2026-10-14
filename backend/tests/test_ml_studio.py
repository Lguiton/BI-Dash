import numpy as np
import pytest

from app.services import biz_models, biz_packs, ml_studio


def make_pack(client, rows=240):
    rng = np.random.default_rng(5)
    lines = ["date,hours,parts,device,price,late"]
    for i in range(rows):
        h = float(rng.uniform(0.5, 6))
        p = float(rng.uniform(0, 100))
        dev = ["Laptop", "Phone", "Router"][i % 3]
        price = 60 * h + 1.2 * p + (40 if dev == "Laptop" else 0) + rng.normal(0, 8)
        late = "yes" if h > 4 else "no"
        lines.append(f"2026-{1 + (i // 28) % 9:02d}-{1 + i % 28:02d},{h:.2f},{p:.1f},{dev},{price:.2f},{late}")
    r = biz_packs.create_custom("\n".join(lines), "Studio test", "date")
    return r["id"]


def test_regression_beats_baseline_and_ranks_honestly(client):
    pid = make_pack(client)
    r = ml_studio.build(pid, "price", None, "auto", {"models": ["baseline", "ridge", "forest", "boosting", "neural"], "seconds": 60})
    assert r["task"] == "regression" and r["useful"] is True
    names = [x["model"] for x in r["leaderboard"]]
    assert "Baseline (no learning)" in names and len(names) >= 4
    assert r["best"] != "Baseline (no learning)"
    assert r["detail"]["errors"]["median_abs_error"] is not None
    assert r["how_chosen"] and "time-ordered" in r["split"]
    top = [i["input"] for i in r["importance"]][:2]
    assert "hours" in top
    assert r["effects"] and r["effects"][0]["average_prediction"][0] < r["effects"][0]["average_prediction"][-1]


def test_classification_with_threshold_advice_and_tuning(client):
    pid = make_pack(client)
    r = ml_studio.build(pid, "late", ["hours", "parts", "device"], "auto", {"models": ["baseline", "logistic", "tree", "forest"], "tune": True, "fn_cost": 5, "fp_cost": 1, "seconds": 90})
    assert r["task"] == "classification" and r["useful"] is True
    th = r["detail"]["threshold"]
    assert th["positive_class"] == "yes" and 0.05 <= th["best_cutoff"] <= 0.95
    assert th["cost_at_best"] <= th["cost_at_0.5"]
    assert r["detail"]["confusion"]["labels"] == ["no", "yes"]
    assert r["tuning"]


def test_noise_target_is_reported_as_not_useful(client):
    rng = np.random.default_rng(1)
    lines = ["date,a,b,noise"] + [f"2026-0{1 + i % 9}-{1 + i % 27:02d},{rng.normal():.3f},{rng.normal():.3f},{rng.normal():.3f}" for i in range(200)]
    pid = biz_packs.create_custom("\n".join(lines), "Noise test", "date")["id"]
    r = ml_studio.build(pid, "noise", ["a", "b"], "auto", {"models": ["baseline", "ridge", "forest"], "seconds": 45})
    assert r["useful"] is False and "don't" in r["verdict"].lower()
    assert r["importance"] == []


def test_predict_explain_and_batch_score(client):
    pid = make_pack(client)
    r = ml_studio.build(pid, "late", ["hours", "parts", "device"], "classification", {"models": ["baseline", "logistic"], "seconds": 30})
    mid = r["id"]
    p = ml_studio.predict_proba(mid, [{"hours": 5.5, "parts": 10, "device": "Laptop"}, {"hours": 1.0, "parts": 10, "device": "Phone"}])
    assert p["predictions"] == ["yes", "no"] and p["probabilities"][0]["yes"] > 0.5
    ex = ml_studio.explain_row(mid, {"hours": 5.5, "parts": 10, "device": "Laptop"})
    assert ex["reasons"][0]["input"] == "hours" and ex["reasons"][0]["effect"] > 0
    out = ml_studio.batch_score(mid, "hours,parts,device\n5.5,10,Laptop\n1,5,Phone\n")
    assert out["rows"] == 2 and "probability_yes" in out["columns"]
    with pytest.raises(biz_models.ModelError):
        ml_studio.batch_score(mid, "hours,device\n1,Phone\n")
    assert any(m["id"] == mid for m in biz_models.list_models())


def test_errors(client):
    pid = make_pack(client, 60)
    with pytest.raises(biz_models.ModelError):
        ml_studio.build(pid, "nope", None, "auto", {})
    with pytest.raises(biz_models.ModelError):
        ml_studio.build(pid, "device", None, "regression", {})


def test_api(client):
    pid = make_pack(client)
    m = client.get("/api/ml-studio/menu").json()
    assert any(x["key"] == "boosting" for x in m["regression"])
    r = client.post("/api/ml-studio/build", json={"source": pid, "target": "late", "features": ["hours", "parts"], "models": ["baseline", "logistic"], "seconds": 30})
    assert r.status_code == 200
    mid = r.json()["id"]
    assert client.post(f"/api/ml-studio/{mid}/predict", json={"rows": [{"hours": 5, "parts": 1}]}).json()["predictions"] == ["yes"]
    assert client.post(f"/api/ml-studio/{mid}/explain", json={"row": {"hours": 5, "parts": 1}}).status_code == 200
    s = client.post(f"/api/ml-studio/{mid}/score.csv", json={"csv": "hours,parts\n5,1\n"})
    assert s.status_code == 200 and "prediction" in s.text
    assert client.post("/api/ml-studio/nope-x/predict", json={"rows": [{"a": 1}]}).status_code == 404
    assert client.post("/api/ml-studio/build", json={"source": pid, "target": "zzz"}).status_code == 400


def test_agent_can_build_and_run_language_jobs(client):
    from app.services import agents
    from app.services.providers import Call, Turn
    from tests.test_math_and_shortcuts import Fake
    pid = make_pack(client)
    f = Fake([Turn("", [Call("1", "ml_studio", {"action": "build", "source": pid, "target": "late", "features": ["hours", "parts"]})]),
              Turn("", [Call("2", "ml_studio", {"action": "language", "request": "common keywords", "data": "printer paper jam error\nwifi router dropping\nprinter toner empty\nrouter reset needed\nlaptop battery swollen"})]), Turn("Done.")])
    r = agents.chat("ml", "build me a model for late jobs", adapters={"anthropic": f, "openai": f, "google": f}, provider="anthropic")
    assert "ml_studio" in [t["name"] for t in f.tools] and "verdict" in str(f.results[0]) and "keywords" in str(f.results[1]) and r.reply == "Done."
    g = Fake([Turn("ok")])
    agents.chat("itsupport", "hi", adapters={"anthropic": g, "openai": g, "google": g}, provider="anthropic")
    assert "ml_studio" not in [t["name"] for t in g.tools]
