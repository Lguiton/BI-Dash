import random
from datetime import date, timedelta

import pytest

from app.services.forecast import forecast_series
from app.services.recommendations import build_recommendations
from conftest import csv_file


def series(n, base=100, slope=2.0, weekend=1.4, noise=0.0, seed=1, start=date(2026, 1, 1)):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        d = start + timedelta(days=i)
        v = (base + slope * i) * (weekend if d.weekday() >= 5 else 1.0) * (1 + rng.gauss(0, noise))
        out.append((d, v))
    return out


def test_recovers_trend_and_weekly_pattern():
    f = forecast_series(series(70), horizon=14)
    assert f["available"] and "seasonality" in f["method"]
    truth = dict(series(84))  # known future values (noise-free)
    for p in f["points"]:
        actual = truth[date.fromisoformat(p["date"])]
        assert p["forecast"] == pytest.approx(actual, rel=0.03)
    assert f["backtest"]["mape_pct"] < 3
    # trend is for an "average day" (weekday factors average 1.0): true slope 2 x mean(1,1,1,1,1,1.4,1.4)
    assert f["trend_per_day"] == pytest.approx(2.0 * (5 + 2 * 1.4) / 7, rel=0.02)


def test_interval_widens_with_noise_and_contains_most_actuals():
    noisy = series(120, noise=0.10, seed=3)
    f = forecast_series(noisy[:100], horizon=20)
    quiet = forecast_series(series(100), horizon=20)
    assert f["residual_sd"] > quiet["residual_sd"] * 5
    inside = sum(1 for p, (_, v) in zip(f["points"], noisy[100:120]) if p["lower"] <= v <= p["upper"])
    assert inside >= 15  # ~95% nominal; allow slack on 20 points
    assert all(p["lower"] <= p["forecast"] <= p["upper"] for p in f["points"])


def test_too_little_data():
    f = forecast_series(series(10))
    assert f["available"] is False and "14" in f["reason"]


def test_short_series_skips_seasonality_and_backtest():
    f = forecast_series(series(16, weekend=1.0), horizon=3)
    assert f["available"] and f["backtest"] is None


def test_forecast_never_negative():
    falling = [(date(2026, 1, 1) + timedelta(days=i), max(1.0, 100 - 6 * i)) for i in range(20)]
    assert all(p["forecast"] >= 0 and p["lower"] >= 0 for p in forecast_series(falling, 30)["points"])


def test_recommendations_arithmetic():
    ents = [
        {"entity_id": "A", "entity_name": "Alpha", "category": "X", "revenue": 10000, "records": 20, "margin_pct": 60.0,
         "avg_cost_per_record": 180.0, "baseline_target": 140.0},
        {"entity_id": "B", "entity_name": "Beta", "category": "X", "revenue": 8000, "records": 20, "margin_pct": 40.0,
         "avg_cost_per_record": 100.0, "baseline_target": 100.0},
    ]
    wk = [{"entity_id": "A", "is_weekend": False, "records": 14, "avg_revenue": 400.0},
          {"entity_id": "A", "is_weekend": True, "records": 6, "avg_revenue": 600.0}]
    recs = {r["kind"]: r for r in build_recommendations(ents, wk)}
    assert recs["cost_control"]["impact_usd"] == (180 - 140) * 20  # 800
    assert recs["margin_gap"]["entity"] == "Beta" and recs["margin_gap"]["impact_usd"] == pytest.approx(8000 * 0.20)
    assert recs["capacity"]["impact_usd"] == pytest.approx(0.10 * 14 * (600 - 400))
    assert all("basis" in r for r in recs.values())


def test_endpoints_cover_all_four_types(client):
    from test_sample_data import _load
    import csv, io
    gen = _load()
    rows = gen.generate(120, date(2026, 10, 6), 42)
    buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=gen.HEADER); w.writeheader(); w.writerows(rows)
    assert client.post("/api/ingest/csv", params={"mode": "replace"}, files=csv_file(buf.getvalue())).status_code == 200
    ins = client.get("/api/analytics/insights").json()["insights"]
    types = {i["analytics_type"] for i in ins}
    assert types == {"descriptive", "diagnostic", "predictive", "prescriptive"}, types
    fc = client.get("/api/analytics/forecast", params={"horizon": 10}).json()
    assert fc["available"] and len(fc["points"]) == 10 and fc["backtest"]["mape_pct"] < 25
    recs = client.get("/api/analytics/recommendations").json()["recommendations"]
    assert recs and recs[0]["impact_usd"] >= recs[-1]["impact_usd"]
    assert client.get("/api/analytics/forecast", params={"horizon": 500}).status_code == 422
    # demo data (6 days) can't be forecast, and says why
    client.post("/api/ingest/csv", params={"mode": "replace"}, files=csv_file(
        "record_date,entity_id,revenue,operational_cost,units_processed\n2026-01-01,A,10,5,1\n"))
    assert client.get("/api/analytics/forecast").json()["available"] is False
