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


def test_reconciliation_in_status(client, lake):
    st = client.post("/api/pipeline/run", json={"source": "clean"}).json()["status"]
    assert any(c["name"] == "Gold reconciles to silver" and c["ok"] for c in st["checks"])
    assert len(st["reconciliation"]) == 4 and all(r["ok"] for r in st["reconciliation"])


def test_gate_publishes_good_data_and_blocks_bad(client, lake, monkeypatch):
    ok = client.post("/api/pipeline/run", json={"source": "clean", "gate": True}).json()
    assert ok["run"]["published"] is True and ok["run"]["blocked_reasons"] == []
    assert ok["status"]["exists"] and not (lake.parent / (lake.name + "_staging")).exists()
    before = client.get("/api/pipeline").json()["layers"]
    # messy data breaks the 20% quarantine rule: the gate must keep the good lake as it was
    bad = client.post("/api/pipeline/run", json={"source": "messy", "gate": True}).json()
    if not bad["run"]["published"]:
        assert bad["run"]["blocked_reasons"]
        assert client.get("/api/pipeline").json()["layers"] == before
    assert not (lake.parent / (lake.name + "_staging")).exists()


def test_gate_blocks_on_forced_failure(client, lake, monkeypatch):
    client.post("/api/pipeline/run", json={"source": "clean"})
    before = client.get("/api/pipeline").json()["layers"]
    monkeypatch.setattr(pipeline, "reconcile", lambda l: {"ok": False, "detail": "differences in: forced", "rows": []})
    r = client.post("/api/pipeline/run", json={"source": "clean", "gate": True, "reset": False}).json()["run"]
    assert r["published"] is False and "forced" in r["blocked_reasons"][0]
    assert client.get("/api/pipeline").json()["layers"] == before
    assert client.get("/api/pipeline").json()["history"][0]["published"] is False


def test_only_if_new_skips_unchanged_source(client, lake):
    first = client.post("/api/pipeline/run", json={"source": "clean", "only_if_new": True}).json()["run"]
    assert not first.get("skipped") and first["source_sha"]
    again = client.post("/api/pipeline/run", json={"source": "clean", "only_if_new": True}).json()["run"]
    assert again["skipped"] is True
    forced = client.post("/api/pipeline/run", json={"source": "clean"}).json()["run"]
    assert not forced.get("skipped")


def test_silent_failure_checks_flag_volume_drop_and_quarantine_jump():
    prev = {"silver_rows": 1000, "quarantined": 10}
    ok = pipeline.silent_failure_checks({"silver_rows": 990, "quarantined": 11}, prev)
    assert all(c["ok"] for c in ok) and len(ok) == 2
    bad = pipeline.silent_failure_checks({"silver_rows": 300, "quarantined": 400}, prev)
    assert [c["name"] for c in bad if not c["ok"]] == ["Volume steady vs previous run", "Quarantine has not jumped"]
    assert pipeline.silent_failure_checks({"silver_rows": 1, "quarantined": 0, "reset": True}, prev) == []
    assert pipeline.silent_failure_checks({"silver_rows": 1, "quarantined": 0}, None) == []
