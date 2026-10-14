import csv


def test_dataset_overview_has_five_careers(client):
    d = client.get("/api/dataset").json()
    assert d["rows"] > 0 and [c["id"] for c in d["careers"]] == ["analyst", "scientist", "ml", "engineering", "pm", "sysanalyst", "fullstack", "security", "network", "itsupport", "ai"]
    by = {c["id"]: c for c in d["careers"]}
    assert by["analyst"]["ready"] is True
    assert by["ml"]["ready"] is False        # 6 demo rows are too few for the ML Lab
    assert all(k["need"] and k["have"] for c in d["careers"] for k in c["checks"])


def test_uploaded_data_changes_readiness(client):
    rows = ["record_date,entity_id,revenue,operational_cost,units_processed"]
    import datetime as dt
    d0 = dt.date(2026, 1, 1)
    for i in range(60):
        for e in "ABCDE":
            rows.append(f"{d0 + dt.timedelta(days=i)},{e},{100 + i},40,5")
    r = client.post("/api/ingest/csv?mode=replace", files={"file": ("t.csv", "\n".join(rows), "text/csv")})
    assert r.status_code == 200, r.text
    by = {c["id"]: c for c in client.get("/api/dataset").json()["careers"]}
    assert by["ml"]["ready"] and by["scientist"]["ready"]


def test_pipeline_runs_on_uploaded_data(client, tmp_path, monkeypatch):
    from app.services import pipeline
    monkeypatch.setattr(pipeline, "UPLOADED_EXPORT", tmp_path / "land" / "up.csv")
    monkeypatch.setattr(pipeline, "LAKE", tmp_path / "lake")
    r = client.post("/api/pipeline/run", json={"source": "uploaded", "reset": True})
    assert r.status_code == 200, r.text
    run = r.json()["run"]
    n = client.get("/api/analytics/summary").json()["record_count"]
    assert run["source"] == "uploaded" and run["silver_rows"] + run["quarantined"] == n
    with (tmp_path / "land" / "up.csv").open() as fh:
        assert len(list(csv.DictReader(fh))) == n


def test_pipeline_uploaded_needs_data(client, tmp_path, monkeypatch):
    from app.services import pipeline
    monkeypatch.setattr(pipeline, "UPLOADED_EXPORT", tmp_path / "up.csv")
    monkeypatch.setattr(pipeline, "LAKE", tmp_path / "lake")
    from app.services.db import get_cursor
    with get_cursor() as cur:
        cur.execute("DELETE FROM fact_operations")
    assert client.post("/api/pipeline/run", json={"source": "uploaded"}).status_code == 400
