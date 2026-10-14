from app.services.insights import build_insights, modified_z_scores, pct_change
from conftest import csv_file


def test_modified_z_flags_outlier_in_short_series():
    z = modified_z_scores([100, 102, 98, 101, 99, 400])
    assert z[-1] > 3.5 and all(abs(v) < 3.5 for v in z[:-1])


def test_modified_z_constant_series_is_zero():
    assert modified_z_scores([5, 5, 5, 5, 5]) == [0.0] * 5


def test_pct_change_edges():
    assert pct_change(110, 100) == 10.0
    assert pct_change(5, 0) is None and pct_change(None, 3) is None


def _daily(profits):
    return [{"date": f"2026-01-{i + 1:02d}", "revenue": 200.0, "cost": 200.0 - p, "profit": float(p)}
            for i, p in enumerate(profits)]


def test_build_insights_reports_anomaly():
    kpis = {"record_count": 6, "total_revenue": 1200, "net_profit": 500, "net_margin_pct": 41.7}
    ins = build_insights(kpis, None, _daily([100, 102, 98, 101, 99, 10]), [])
    assert any(i["type"] == "anomaly" and i["date"] == "2026-01-06" and i["severity"] == "warning" for i in ins)


def test_build_insights_empty_and_quiet():
    assert build_insights({"record_count": 0}, None, [], [])[0]["title"] == "No data in this view"
    kpis = {"record_count": 6, "total_revenue": 1200, "net_profit": 600, "net_margin_pct": 50.0}
    ins = build_insights(kpis, None, _daily([100] * 6), [])
    assert ins[0]["title"] == "Nothing unusual detected"


def test_endpoint_end_to_end(client):
    rows = "record_date,entity_id,entity_name,category,revenue,operational_cost,units_processed\n"
    for i in range(1, 15):
        profit_cost = 100 if i != 10 else 190  # day 10 is a bad day
        rows += f"2026-11-{i:02d},A,Alpha,X,200,{profit_cost},10\n"
        rows += f"2026-11-{i:02d},B,Beta,X,100,95,10\n"
    assert client.post("/api/ingest/csv", params={"mode": "replace"}, files=csv_file(rows)).status_code == 200
    j = client.get("/api/analytics/insights", params={"date_from": "2026-11-08", "date_to": "2026-11-14"}).json()
    types = {i["type"] for i in j["insights"]}
    assert "anomaly" in types
    assert any("2026-11-10" in i["title"] for i in j["insights"] if i["type"] == "anomaly")
    assert "entity_low_margin" in types or "entity_top" in types


def test_over_budget_insight():
    kpis = {"record_count": 6, "total_revenue": 1200, "net_profit": 600, "net_margin_pct": 50.0}
    ents = [
        {"entity_id": "A", "entity_name": "Alpha", "revenue": 600, "profit": 300, "margin_pct": 50.0,
         "avg_cost_per_record": 180.0, "baseline_target": 140.0, "vs_baseline_pct": 28.6},
        {"entity_id": "B", "entity_name": "Beta", "revenue": 600, "profit": 300, "margin_pct": 50.0,
         "avg_cost_per_record": 101.0, "baseline_target": 100.0, "vs_baseline_pct": 1.0},
    ]
    ins = build_insights(kpis, None, _daily([100] * 6), ents)
    over = [i for i in ins if i["type"] == "over_budget"]
    assert len(over) == 1 and "Alpha" in over[0]["title"] and "28.6%" in over[0]["title"]
