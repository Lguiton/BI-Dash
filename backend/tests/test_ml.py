import pytest

pytest.importorskip("sklearn")
pytest.importorskip("pandas")


@pytest.fixture()
def big(client):
    """Load a year of generated sample data so there is enough to learn from."""
    import subprocess, sys, pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    csv = root / "data_samples" / "operations_clean.csv"
    if not csv.exists():
        subprocess.run([sys.executable, str(root / "scripts" / "generate_sample_data.py")], check=True)
    r = client.post("/api/ingest/csv?mode=replace", files={"file": ("d.csv", csv.read_bytes(), "text/csv")})
    assert r.status_code == 200
    return client


def test_options(client):
    o = client.get("/api/ml/options").json()
    assert {t["id"] for t in o["tasks"]} == {"revenue", "profit", "not_completed"}
    assert "random_forest" in {m["id"] for m in o["models"]["regression"]}


def test_not_enough_data_message(client):
    r = client.post("/api/ml/train", json={"task": "revenue", "model": "linear", "features": ["units_processed"]})
    assert r.status_code == 400 and "rows" in r.json()["detail"]


def test_regression_beats_baseline_and_splits_by_time(big):
    r = big.post("/api/ml/train", json={"task": "revenue", "model": "ridge", "features": ["units_processed", "category", "weekday"]})
    assert r.status_code == 200
    d = r.json()
    assert d["metrics"]["r2"] > 0.9 and d["metrics"]["mae"] < d["baseline"]["mae"]
    sp = d["split"]
    assert sp["train_range"][1] < sp["test_range"][0]          # train entirely before test: no shuffling, no leakage across time
    assert sp["train_rows"] + sp["test_rows"] == 3650
    assert d["importance"][0]["feature"] == "units_processed"
    assert len(d["cv"]["scores"]) == 4 and 0 < len(d["sample"]) <= 305


def test_classification_imbalance_lessons(big):
    base = {"task": "not_completed", "model": "logistic", "features": ["units_processed", "duration_minutes", "category"]}
    d = big.post("/api/ml/train", json=base).json()
    assert d["kind"] == "classification" and d["baseline"]["accuracy"] > 0.85       # always-'Completed' already scores high
    assert set(d["confusion"]) == {"tn", "fp", "fn", "tp"}
    assert sum(d["confusion"].values()) == d["split"]["test_rows"]
    bal = big.post("/api/ml/train", json={**base, "balance_classes": True}).json()
    assert bal["metrics"]["recall"] >= d["metrics"]["recall"]                          # balancing trades precision for recall
    low = big.post("/api/ml/train", json={**base, "threshold": 0.05}).json()
    assert low["metrics"]["recall"] >= d["metrics"]["recall"]


def test_validation(big):
    ok = {"task": "revenue", "model": "linear", "features": ["units_processed"]}
    assert big.post("/api/ml/train", json={**ok, "model": "logistic"}).status_code == 400      # classifier for a regression task
    assert big.post("/api/ml/train", json={**ok, "features": ["nope"]}).status_code == 400
    assert big.post("/api/ml/train", json={**ok, "features": []}).status_code == 422
    assert big.post("/api/ml/train", json={**ok, "test_fraction": 0.9}).status_code == 422
    assert big.post("/api/ml/train", json={**ok, "task": "weather"}).status_code == 422
