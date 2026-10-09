"""The practice-data generator must produce files the importer accepts (clean) or rejects clearly (messy)."""
import importlib.util
from datetime import date
from pathlib import Path

from conftest import csv_file

GEN = Path(__file__).resolve().parents[2] / "scripts" / "generate_sample_data.py"


def _load():
    spec = importlib.util.spec_from_file_location("gen", GEN)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _csv(rows, gen):
    import csv, io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=gen.HEADER)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def test_clean_generated_data_imports_and_has_findable_anomalies(client):
    gen = _load()
    rows = gen.generate(120, date(2026, 10, 6), seed=42)
    assert len(rows) == 120 * 10
    r = client.post("/api/ingest/csv", params={"mode": "replace"}, files=csv_file(_csv(rows, gen)))
    assert r.status_code == 200, r.text
    assert r.json()["rows_loaded"] == 1200 and r.json()["entities_created"] == 10
    # the generator's budget drift shows up: ENT-03 is built to run well over budget
    ents = {e["entity_id"]: e for e in client.get("/api/analytics/by-entity").json()}
    assert ents["ENT-03"]["vs_baseline_pct"] > 15
    assert abs(ents["ENT-02"]["vs_baseline_pct"]) < 6


def test_generator_is_deterministic():
    gen = _load()
    assert gen.generate(30, date(2026, 10, 6), 1) == gen.generate(30, date(2026, 10, 6), 1)
    assert gen.generate(30, date(2026, 10, 6), 1) != gen.generate(30, date(2026, 10, 6), 2)


def test_messy_data_is_rejected_with_line_numbers(client):
    gen = _load()
    rows = gen.make_messy(gen.generate(60, date(2026, 10, 6), 42), 42)
    r = client.post("/api/ingest/csv", files=csv_file(_csv(rows, gen)))
    assert r.status_code == 400
    d = r.json()["detail"]
    assert d["errors"] and all(e.startswith("Line ") for e in d["errors"][:5])
    assert client.get("/api/analytics/summary").json()["record_count"] == 6  # nothing imported


def test_views_exist_and_work(client):
    from app.services.db import fetch_all, get_cursor
    with get_cursor() as cur:
        dd = fetch_all(cur, "SELECT * FROM dim_date ORDER BY date_key")
        flat = fetch_all(cur, "SELECT * FROM v_operations_flat")
    assert len(dd) == 6 and dd[0]["day_name"] == "Thursday" and dd[0]["is_weekend"] is False  # 2026-10-01
    assert dd[2]["is_weekend"] is True  # 2026-10-03 is a Saturday
    assert len(flat) == 6 and {"profit", "margin", "month_name", "entity_name"} <= set(flat[0])
