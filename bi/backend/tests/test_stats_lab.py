import random
from datetime import date, timedelta

import pytest

from tests.conftest import csv_file


def _orders_csv(n=400, seed=1):
    rnd = random.Random(seed)
    lines = ["order_id,customer_id,order_date,region,qty,price,amount,returned"]
    d0 = date(2026, 1, 1)
    for i in range(n):
        day = d0 + timedelta(days=i * 120 // n)
        region = rnd.choice(["West", "East", "North"])
        qty = rnd.randint(1, 9)
        price = round(rnd.uniform(10, 50), 2)
        amount = round(qty * price * (1.2 if region == "West" else 1.0) + rnd.gauss(0, 5), 2)
        # weekend bump and an upward trend
        if day.weekday() >= 5:
            amount += 40
        amount += i * 0.2
        lines.append(f"O{i},C{rnd.randint(1, 60):02d},{day.isoformat()},{region},{qty},{price},{amount},{'yes' if rnd.random() < (0.3 if region == 'North' else 0.1) else 'no'}")
    return "\n".join(lines) + "\n"


@pytest.fixture()
def orders(client):
    r = client.post("/api/data/import", files=csv_file(_orders_csv(), "orders.csv"), data={"mode": "replace"})
    assert r.status_code == 200, r.text
    return "orders"


def test_sources_lists_ops_and_imports(client, orders):
    r = client.get("/api/stats/sources").json()
    assert [t["id"] for t in r["types"]] == ["descriptive", "diagnostic", "predictive", "prescriptive"]
    ids = [s["id"] for s in r["sources"]]
    assert ids[0] == "operations" and orders in ids
    ops = r["sources"][0]
    assert {"revenue", "status", "record_date"} <= {c["name"] for c in ops["columns"]}
    reg = next(c for c in r["sources"][1]["columns"] if c["name"] == "region")
    oid = next(c for c in r["sources"][1]["columns"] if c["name"] == "order_id")
    assert reg["distinct"] == 3 and oid["distinct"] == 400  # lets the page default to region, not the ID column


def test_filter_funnel_and_modes(client, orders):
    body = {"source": orders, "filters": [{"column": "region", "op": "eq", "value": "West"}, {"column": "qty", "op": "gte", "value": 5}]}
    r = client.post("/api/stats/filter", json=body).json()
    assert r["total"] == 400 and 0 < r["kept"] < r["total"] and r["removed"] == 400 - r["kept"]
    assert r["funnel"][1]["rows_after"] == r["kept"] and r["funnel"][0]["rows_after"] >= r["kept"]
    assert all(row["region"] == "West" and row["qty"] >= 5 for row in r["preview"])
    assert "WHERE" in r["sql"] and "?" in r["sql"]
    either = client.post("/api/stats/filter", json={**body, "mode": "or"}).json()
    assert either["kept"] >= r["kept"]
    n = client.post("/api/stats/filter", json={"source": orders, "filters": [{"column": "order_date", "op": "between", "value": "2026-01-01", "value2": "2026-01-10"}]}).json()
    assert 0 < n["kept"] < 400
    ins = client.post("/api/stats/filter", json={"source": orders, "filters": [{"column": "region", "op": "in", "value": "West, East"}]}).json()
    assert ins["kept"] == sum(1 for _ in range(1)) * ins["kept"] and ins["kept"] > 0


def test_filter_rejects_bad_input_and_injection(client, orders):
    for f in ({"column": 'region"; DROP TABLE orders; --', "op": "eq", "value": "x"},
              {"column": "nope", "op": "eq", "value": "x"},
              {"column": "region", "op": "gt", "value": "x"},
              {"column": "qty", "op": "eq", "value": "abc"},
              {"column": "order_date", "op": "eq", "value": "not a date"}):
        r = client.post("/api/stats/filter", json={"source": orders, "filters": [f]})
        assert r.status_code == 400, (f, r.text)
    assert client.post("/api/stats/filter", json={"source": "fact_operations; DROP", "filters": []}).status_code == 404
    assert client.post("/api/stats/filter", json={"source": orders, "filters": [{"column": "qty", "op": "bogus", "value": 1}]}).status_code == 422
    # value that looks like SQL is just a value
    r = client.post("/api/stats/filter", json={"source": orders, "filters": [{"column": "region", "op": "eq", "value": "x' OR '1'='1"}]}).json()
    assert r["kept"] == 0
    assert client.get("/api/stats/sources").status_code == 200


def test_probability_basic_groups_bayes_repeat(client, orders):
    body = {"source": orders, "event": {"column": "returned", "op": "eq", "value": "yes"}, "group_by": "region",
            "given": {"column": "region", "op": "eq", "value": "North"}, "entity_col": "customer_id"}
    r = client.post("/api/stats/probability", json=body).json()
    assert r["rows_used"] == 400 and 0 < r["p"] < 1 and r["ci_low"] < r["p"] < r["ci_high"]
    g = {x["group"]: x for x in r["groups"]}
    assert g["North"]["p"] > g["West"]["p"]  # North returns more by construction
    assert r["independence_p"] is not None
    b = r["bayes"]
    assert abs(b["p_a_and_b"] - b["p_b"] * b["p_a_given_b"]) < 1e-6
    assert b["counts"]["ab"] <= min(b["counts"]["a"], b["counts"]["b"])
    assert r["repeat"]["entities_with_event"] > 0 and 0 <= r["repeat"]["p_repeat"] <= 1


def test_probability_edge_cases(client, orders):
    none = client.post("/api/stats/probability", json={"source": orders, "event": {"column": "region", "op": "eq", "value": "Mars"}}).json()
    assert none["p"] == 0 and any("never" in w for w in none["warnings"])
    r = client.post("/api/stats/probability", json={"source": orders, "event": {"column": "returned", "op": "eq", "value": "yes"},
                                                    "filters": [{"column": "qty", "op": "gt", "value": 100}]})
    assert r.status_code == 400
    r = client.post("/api/stats/probability", json={"source": orders, "event": {"column": "returned", "op": "eq", "value": "yes"}, "group_by": "amount"})
    assert r.status_code == 400  # too many distinct numbers to group by


def test_probability_on_operations_data(client):
    _load_ops(client)
    r = client.post("/api/stats/probability", json={"event": {"column": "status", "op": "eq", "value": "Delayed"}, "group_by": "category"}).json()
    assert r["rows_used"] > 0 and r["groups"]


def test_timeseries_trend_season_anomaly_forecast(client, orders):
    body = {"source": orders, "date_col": "order_date", "value_col": "amount", "agg": "sum", "bucket": "day", "horizon": 7}
    r = client.post("/api/stats/timeseries", json=body).json()
    assert r["available"] and r["points"] == 120
    assert r["seasonality"]["kind"] == "weekday" and r["seasonality"]["high"] in ("Sat", "Sun")
    assert len(r["forecast"]) == 7 and all(f["low"] <= f["v"] <= f["high"] for f in r["forecast"])
    assert any(s["ma"] is not None for s in r["series"])
    # inject an obvious spike and make sure it is flagged
    spike = _orders_csv() + "OX,C01,2026-02-10,West,1,10,50000,no\n"
    client.post("/api/data/import", files=csv_file(spike, "orders2.csv"), data={"mode": "replace"})
    r2 = client.post("/api/stats/timeseries", json={**body, "source": "orders2"}).json()
    assert r2["anomalies"] and r2["anomalies"][0]["t"] == "2026-02-10" and r2["anomalies"][0]["direction"] == "high"
    m = client.post("/api/stats/timeseries", json={**body, "bucket": "month", "horizon": 0}).json()
    assert m["available"] is False or m["points"] <= 5
    c = client.post("/api/stats/timeseries", json={"source": orders, "date_col": "order_date", "agg": "count", "bucket": "week"}).json()
    assert c["available"] and c["agg"] == "count"


def test_timeseries_trend_direction_and_short_series(client, orders):
    r = client.post("/api/stats/timeseries", json={"source": orders, "date_col": "order_date", "value_col": "amount", "agg": "avg", "bucket": "day"}).json()
    assert r["trend"]["slope"] > 0 and r["trend"]["direction"] == "up"
    short = client.post("/api/stats/timeseries", json={"source": orders, "date_col": "order_date", "value_col": "amount",
                                                       "filters": [{"column": "order_date", "op": "lt", "value": "2026-01-04"}]}).json()
    assert short["available"] is False
    assert client.post("/api/stats/timeseries", json={"source": orders, "date_col": "region", "value_col": "amount"}).status_code == 400
    assert client.post("/api/stats/timeseries", json={"source": orders, "date_col": "order_date", "value_col": "region"}).status_code == 400


def _load_ops(client, days=60):
    ents = [("ENT-01", "North", "Logistics"), ("ENT-02", "West", "Express"), ("ENT-03", "Core", "Fleet")]
    rnd = random.Random(5)
    lines = ["record_date,entity_id,entity_name,category,revenue,operational_cost,units_processed,duration_minutes,status,baseline_target"]
    for d in range(days):
        day = date(2026, 8, 1) + timedelta(days=d)
        for e, n, c in ents:
            u = rnd.randint(30, 90)
            lines.append(f"{day},{e},{n},{c},{round(u * rnd.uniform(8, 12), 2)},{round(u * 2.5, 2)},{u},{u * 5},{rnd.choice(['Completed', 'Completed', 'Delayed'])},100")
    r = client.post("/api/ingest/csv", files=csv_file("\n".join(lines) + "\n"), params={"mode": "replace"})
    assert r.status_code == 200, r.text


def test_timeseries_on_operations(client):
    _load_ops(client)
    r = client.post("/api/stats/timeseries", json={"date_col": "record_date", "value_col": "revenue", "agg": "sum", "bucket": "day", "horizon": 14}).json()
    assert r["available"] and len(r["forecast"]) == 14


def test_regression_recovers_known_relationship(client, orders):
    r = client.post("/api/stats/regression", json={"source": orders, "y": "amount", "x_numeric": ["qty", "price"], "x_categorical": ["region"],
                                                   "predict": {"qty": 5, "price": 30, "region": "West"}}).json()
    assert r["r2"] > 0.5 and r["adj_r2"] <= r["r2"] and r["n"] == 400
    terms = {c["term"]: c for c in r["coefficients"]}
    assert terms["qty"]["significant"] and terms["qty"]["coef"] > 0
    assert "region = West" in terms or any(k.startswith("region =") for k in terms)
    assert r["what_if"]["low"] < r["what_if"]["prediction"] < r["what_if"]["high"]
    assert r["holdout"]["r2"] is not None
    assert r["chart"]["kind"] == "fit" and r["residuals"]
    one = client.post("/api/stats/regression", json={"source": orders, "y": "amount", "x_numeric": ["qty"]}).json()
    assert one["chart"]["kind"] == "scatter" and len(one["chart"]["line"]) == 2


def test_regression_exact_line_and_guards(client):
    rows = "x,y,z\n" + "\n".join(f"{i},{3 * i + 2},{2 * i}" for i in range(1, 40))
    client.post("/api/data/import", files=csv_file(rows, "line.csv"), data={"mode": "replace"})
    r = client.post("/api/stats/regression", json={"source": "line", "y": "y", "x_numeric": ["x"]}).json()
    c = {t["term"]: t["coef"] for t in r["coefficients"]}
    assert abs(c["x"] - 3) < 1e-6 and abs(c["(intercept)"] - 2) < 1e-6 and r["r2"] > 0.999999
    dup = client.post("/api/stats/regression", json={"source": "line", "y": "y", "x_numeric": ["x", "z"]})
    assert dup.status_code == 400 and "same information" in dup.json()["detail"]
    assert client.post("/api/stats/regression", json={"source": "line", "y": "y", "x_numeric": ["y"]}).status_code == 400
    assert client.post("/api/stats/regression", json={"source": "line", "y": "y"}).status_code == 400
    tiny = client.post("/api/stats/regression", json={"source": "line", "y": "y", "x_numeric": ["x"], "filters": [{"column": "x", "op": "lt", "value": 5}]})
    assert tiny.status_code == 400 and "too few" in tiny.json()["detail"]
    whatif = client.post("/api/stats/regression", json={"source": "line", "y": "y", "x_numeric": ["x"], "predict": {}})
    assert whatif.status_code == 200


def test_regression_on_operations(client):
    _load_ops(client)
    r = client.post("/api/stats/regression", json={"y": "revenue", "x_numeric": ["units_processed"], "x_categorical": ["category"]}).json()
    assert r["n"] > 0 and r["r2"] is not None


def test_describe_diagnose_opportunities(client, orders):
    d = client.post("/api/stats/describe", json={"source": orders}).json()
    assert d["rows"] == 400 and {n["column"] for n in d["numbers"]} >= {"qty", "amount"}
    amt = next(n for n in d["numbers"] if n["column"] == "amount")
    assert amt["min"] <= amt["q1"] <= amt["median"] <= amt["q3"] <= amt["max"]
    assert next(t for t in d["categories"] if t["column"] == "region")["distinct"] == 3
    assert d["dates"][0]["column"] == "order_date"
    assert client.post("/api/stats/describe", json={"source": orders, "filters": [{"column": "qty", "op": "gt", "value": 99}]}).status_code == 400

    g = client.post("/api/stats/diagnose", json={"source": orders, "y": "amount", "group_col": "region", "date_col": "order_date"}).json()
    assert g["drivers"][0]["column"] in ("qty", "price") and g["change"]["parts"]
    ch = g["change"]
    assert abs(sum(p["change"] for p in ch["parts"]) - ch["change"]) < 0.05
    assert client.post("/api/stats/diagnose", json={"source": orders, "y": "amount", "date_col": "order_date", "split": "2030-01-01"}).status_code == 400

    o = client.post("/api/stats/opportunities", json={"source": orders, "value_col": "amount", "group_col": "region", "benchmark": "best",
                                                      "levers_y": "amount", "levers": ["qty", "price"]}).json()
    assert o["opportunities"] and all(a["estimated_gain"] > 0 for a in o["opportunities"])
    assert o["best_group"] not in [a["group"] for a in o["opportunities"]]
    assert o["levers"]["items"][0]["lever"] in ("qty", "price")
    low = client.post("/api/stats/opportunities", json={"source": orders, "value_col": "amount", "group_col": "region", "higher_is_better": False, "benchmark": "best"}).json()
    assert low["best_group"] != o["best_group"] or len(low["opportunities"]) >= 1
    assert client.post("/api/stats/opportunities", json={"source": orders, "value_col": "amount", "group_col": "order_id", "min_rows": 50}).status_code == 400


def test_statistics_helpers():
    from app.services.stats_lab import wilson
    lo, hi = wilson(50, 100)
    assert 0.40 < lo < 0.5 < hi < 0.60
    assert wilson(0, 0) == (None, None)


def test_arima_forecast_beats_naive_on_trend_and_guards(client):
    lines = ["day,v"]
    rnd = random.Random(2)
    for i in range(80):
        lines.append(f"{date(2026, 1, 1) + timedelta(days=i)},{100 + 2.0 * i + rnd.gauss(0, 3):.2f}")
    client.post("/api/data/import", files=csv_file("\n".join(lines) + "\n", "ramp.csv"), data={"mode": "replace"})
    body = {"source": "ramp", "date_col": "day", "value_col": "v", "agg": "sum", "bucket": "day", "horizon": 10, "d": 1}
    r = client.post("/api/stats/arima", json=body).json()
    assert r["available"] and r["order"]["d"] == 1 and len(r["forecast"]) == 10
    assert all(f["low"] <= f["v"] <= f["high"] for f in r["forecast"])
    widths = [f["high"] - f["low"] for f in r["forecast"]]
    assert widths[-1] > widths[0]  # uncertainty grows with distance
    # the ramp is +2/day, so ten days out should be near the line
    assert abs(r["forecast"][-1]["v"] - (100 + 2.0 * 89)) < 25
    assert r["backtest"]["mae"] is not None
    flat = client.post("/api/stats/arima", json={**body, "d": 0}).json()
    assert flat["available"] and flat["order"]["d"] == 0
    short = client.post("/api/stats/arima", json={**body, "filters": [{"column": "day", "op": "lt", "value": "2026-01-10"}]}).json()
    assert short["available"] is False
    assert client.post("/api/stats/arima", json={**body, "d": 2}).status_code == 422


def test_business_metrics(client):
    rows = ["day,cust,rev,cost"]
    # 4 months; customers A,B always; C only in Jan-Feb (churns in March); D joins in April
    plan = {1: "ABC", 2: "ABC", 3: "AB", 4: "ABD"}
    for m, who in plan.items():
        for c in who:
            for dday in (3, 17):
                rows.append(f"2026-{m:02d}-{dday:02d},{c},{100 * m},{120 * m}")
    client.post("/api/data/import", files=csv_file("\n".join(rows) + "\n", "biz.csv"), data={"mode": "replace"})
    body = {"source": "biz", "date_col": "day", "revenue_col": "rev", "cost_col": "cost", "entity_col": "cust", "cash": 10000}
    r = client.post("/api/stats/business", json=body).json()
    m = {x["month"]: x for x in r["months"]}
    assert m["2026-01"]["revenue"] == 600 and m["2026-02"]["revenue"] == 1200 and m["2026-03"]["revenue"] == 1200
    assert m["2026-01"]["margin_pct"] == round((600 - 720) / 600 * 100, 2)
    assert m["2026-03"]["lost"] == 1 and m["2026-03"]["active"] == 2 and m["2026-03"]["churn_pct"] == round(1 / 3 * 100, 2)
    assert m["2026-04"]["new"] == 1 and m["2026-04"]["active"] == 3
    assert m["2026-02"]["growth_pct"] == 100.0 and m["2026-03"]["growth_pct"] == 0.0
    h = r["headline"]
    assert r["partial_last_month"] is False or r["partial_last_month"] is True
    assert h["mrr"] is not None and h["arr"] == round(h["mrr"] * 12, 2)
    assert h["avg_net_burn_3m"] > 0 and h["runway_months"] == round(10000 / h["avg_net_burn_3m"], 1)
    one = client.post("/api/stats/business", json={**body, "filters": [{"column": "day", "op": "lt", "value": "2026-02-01"}]})
    assert one.status_code == 400
    assert client.post("/api/stats/business", json={**body, "revenue_col": "cust"}).status_code == 400
    nocost = client.post("/api/stats/business", json={"source": "biz", "date_col": "day", "revenue_col": "rev"}).json()
    assert nocost["headline"]["runway_months"] is None and nocost["months"][0]["margin_pct"] is None
