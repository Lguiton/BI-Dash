import pytest

from app.services import pipeline


@pytest.fixture()
def lake(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "LAKE", tmp_path / "lake")
    return tmp_path / "lake"


def test_not_run_yet(client, lake):
    j = client.get("/api/pipeline").json()
    assert j["exists"] is False and "hasn't run" in j["message"]


def test_run_then_monitor_and_rerun_is_idempotent(client, lake):
    r = client.post("/api/pipeline/run", json={"source": "clean"}).json()
    assert r["run"]["silver_rows"] > 3000 and r["run"]["quarantined"] == 0
    st = r["status"]
    layers = {l["layer"]: l["rows"] for l in st["layers"]}
    assert layers["bronze"] == layers["silver"] and layers["gold"] > 300 and st["watermark"]
    assert {c["name"] for c in st["checks"]} >= {"Freshness", "Silver has rows"}
    again = client.post("/api/pipeline/run", json={"source": "clean"}).json()
    assert again["run"]["silver_rows"] == r["run"]["silver_rows"]
    assert len(again["status"]["history"]) == 2 and again["status"]["history"][0]["at"] >= again["status"]["history"][1]["at"]


def test_messy_data_fills_quarantine(client, lake):
    r = client.post("/api/pipeline/run", json={"source": "messy", "reset": True}).json()["status"]
    assert r["quarantine_reasons"] and sum(x["rows"] for x in r["quarantine_reasons"]) == r["layers"][2]["rows"] > 0


def test_bad_source_rejected(client, lake):
    assert client.post("/api/pipeline/run", json={"source": "../../etc/passwd"}).status_code == 422
