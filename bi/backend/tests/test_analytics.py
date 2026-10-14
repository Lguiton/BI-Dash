import pytest

SEED_REV = 450 + 520 + 380 + 610 + 490 + 540  # 2990
SEED_COST = 112.5 + 130 + 95 + 180 + 115 + 125  # 757.5


def test_health(client):
    assert client.get("/health").json()["status"] == "healthy"


def test_summary_uses_weighted_margin(client):
    d = client.get("/api/analytics/summary").json()
    assert d["total_revenue"] == SEED_REV
    assert d["net_profit"] == pytest.approx(SEED_REV - SEED_COST)
    # weighted margin, NOT the average of per-row margins
    assert d["net_margin_pct"] == pytest.approx((SEED_REV - SEED_COST) / SEED_REV * 100, abs=0.01)
    rows = [(450, 112.5), (520, 130), (380, 95), (610, 180), (490, 115), (540, 125)]
    naive = sum((r - c) / r for r, c in rows) / len(rows) * 100
    assert abs(d["net_margin_pct"] - naive) > 0.01  # the two methods differ on this data
    assert d["previous"] is None and d["deltas"] is None  # no date range -> no previous period


def test_summary_empty_selection_is_safe(client):
    d = client.get("/api/analytics/summary", params={"entity_id": "NOPE"}).json()
    assert d["record_count"] == 0 and d["total_revenue"] == 0 and d["net_margin_pct"] is None


def test_filters(client):
    r = client.get("/api/analytics/summary", params={"entity_id": "ENT-01"}).json()
    assert r["record_count"] == 3 and r["total_revenue"] == 450 + 520 + 540
    r = client.get("/api/analytics/summary", params={"category": "Logistics"}).json()
    assert r["record_count"] == 4
    r = client.get("/api/analytics/summary", params={"date_from": "2026-10-03", "date_to": "2026-10-04"}).json()
    assert r["record_count"] == 2
    assert client.get("/api/analytics/summary", params={"status": "Cancelled"}).json()["record_count"] == 0


def test_bad_date_range_rejected(client):
    r = client.get("/api/analytics/summary", params={"date_from": "2026-10-05", "date_to": "2026-10-01"})
    assert r.status_code == 422


def test_previous_period_and_deltas(client):
    # Oct 4-6 vs the equal-length window Oct 1-3
    d = client.get("/api/analytics/summary", params={"date_from": "2026-10-04", "date_to": "2026-10-06"}).json()
    assert d["previous_range"] == {"date_from": "2026-10-01", "date_to": "2026-10-03"}
    assert d["total_revenue"] == 610 + 490 + 540
    assert d["previous"]["total_revenue"] == 450 + 520 + 380
    assert d["deltas"]["total_revenue"] == pytest.approx((1640 - 1350) / 1350 * 100, abs=0.01)


def test_timeseries_and_by_entity(client):
    ts = client.get("/api/analytics/timeseries").json()
    assert [t["date"] for t in ts] == [f"2026-10-0{i}" for i in range(1, 7)]
    ents = client.get("/api/analytics/by-entity").json()
    ent1 = next(e for e in ents if e["entity_id"] == "ENT-01")
    assert ent1["records"] == 3 and ent1["revenue"] == 1510
    assert ent1["baseline_target"] == 120.0
    # baseline_target is a cost budget: avg cost/record (367.5/3 = 122.5) vs 120
    assert ent1["avg_cost_per_record"] == 122.5
    assert ent1["vs_baseline_pct"] == pytest.approx((122.5 / 120 - 1) * 100, abs=0.1)
    ent2 = next(e for e in ents if e["entity_id"] == "ENT-02")
    assert ent2["vs_baseline_pct"] == 0.0  # exactly on budget (95 vs 95)
    ent3 = next(e for e in ents if e["entity_id"] == "ENT-03")
    assert ent3["vs_baseline_pct"] == pytest.approx(28.6, abs=0.1)


def test_records_pagination_sort_and_whitelist(client):
    r = client.get("/api/analytics/records", params={"limit": 2, "sort": "revenue", "order": "desc"}).json()
    assert r["total"] == 6 and len(r["rows"]) == 2 and r["rows"][0]["revenue"] == 610
    r2 = client.get("/api/analytics/records", params={"limit": 2, "offset": 4, "sort": "revenue", "order": "desc"}).json()
    assert len(r2["rows"]) == 2
    # unknown sort key must fall back safely, never reach SQL
    ok = client.get("/api/analytics/records", params={"sort": "revenue; DROP TABLE fact_operations"})
    assert ok.status_code == 200 and ok.json()["total"] == 6
    assert client.get("/api/analytics/records", params={"order": "sideways"}).status_code == 422


def test_export_csv(client):
    r = client.get("/api/analytics/records/export", params={"entity_id": "ENT-02"})
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("fact_id,record_date") and len(lines) == 2


def test_meta(client):
    m = client.get("/api/analytics/meta").json()
    assert m["min_date"] == "2026-10-01" and m["max_date"] == "2026-10-06"
    assert set(m["categories"]) == {"Logistics", "Express", "Fleet"}
    assert m["statuses"] == ["Completed"] and len(m["entities"]) == 4


def test_scatter_and_heatmap(client):
    sc = client.get("/api/analytics/scatter").json()
    assert sc["total"] == 6 and len(sc["points"]) == 6 and not sc["sampled"]
    assert {"revenue", "cost", "category", "entity_name"} <= set(sc["points"][0])
    assert len(client.get("/api/analytics/scatter", params={"entity_id": "ENT-01"}).json()["points"]) == 3
    hm = client.get("/api/analytics/heatmap").json()
    assert hm["days"][0] == "Mon" and len(hm["entities"]) == 4
    # 2026-10-01 is a Thursday: ENT-01's Thursday average is exactly that day's revenue (450)
    cell = next(c for c in hm["cells"] if c["entity_name"] == "Zone North 89011" and c["day"] == "Thu")
    assert cell["avg_revenue"] == 450.0 and cell["records"] == 1


def test_scatter_samples_large_selections_deterministically(client):
    import csv, io
    from datetime import date
    from conftest import csv_file
    from test_sample_data import _load
    gen = _load()
    rows = gen.generate(250, date(2026, 10, 6), 42)  # 2,500 rows > 2,000-point cap
    buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=gen.HEADER); w.writeheader(); w.writerows(rows)
    client.post("/api/ingest/csv", params={"mode": "replace"}, files=csv_file(buf.getvalue()))
    a = client.get("/api/analytics/scatter").json()
    b = client.get("/api/analytics/scatter").json()
    assert a["sampled"] and len(a["points"]) == 2000 and a["total"] == 2500 and a == b
