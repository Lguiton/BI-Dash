from app.services import bi_calc as bc, doc_reader as dr


def dax(client, measures, group_by=None, csv_text=None):
    return client.post("/api/bitools/dax", json={"measures": measures, "group_by": group_by or [], "csv_text": csv_text})


def test_dax_basic_and_group_totals_agree(client):
    tot = dax(client, [{"name": "T", "formula": "SUM(Sales[Amount])"}]).json()["rows"][0]["T"]
    g = dax(client, [{"name": "T", "formula": "SUM(Sales[Amount])"}], ["Country"]).json()["rows"]
    assert abs(sum(r["T"] for r in g) - tot) < 0.5


def test_dax_calculate_replaces_group_filter_and_measure_refs(client):
    ms = [{"name": "T", "formula": "SUM(Sales[Amount])"}, {"name": "USA", "formula": 'CALCULATE([T], Sales[Country] = "USA")'},
          {"name": "Share", "formula": "DIVIDE([USA],[T])"}]
    r = dax(client, ms, ["Country"]).json()
    usa = next(x for x in r["rows"] if x["Country"] == "USA")["T"]
    assert all(abs(x["USA"] - usa) < 0.01 for x in r["rows"])
    assert r["notes"]


def test_dax_errors_and_unsupported_are_helpful(client):
    r = dax(client, [{"name": "A", "formula": "TOTALYTD(SUM(Sales[Amount]), Sales[Date])"}])
    assert r.status_code == 400 and "TOTALYTD" in r.json()["detail"]
    assert dax(client, [{"name": "A", "formula": "SUM(Sales[Nope])"}]).status_code == 400
    assert dax(client, [{"name": "A", "formula": "[B]"}, {"name": "B", "formula": "[A]"}]).status_code == 400
    assert dax(client, [{"name": "A", "formula": "SUM(Sales[Amount]"}]).status_code == 400


def test_dax_custom_csv_and_reference(client):
    r = dax(client, [{"name": "S", "formula": "SUM(Data[x])"}], csv_text="x,g\n1,a\n2,b\n3,a\n").json()
    assert r["rows"][0]["S"] == 6
    ref = client.get("/api/bitools/dax/reference").json()
    assert ref["examples"] and ref["slips"] and "TOTALYTD" in str(ref["unsupported"])
    allm = [{"name": ex["name"], "formula": ex["dax"]} for ex in ref["examples"]]
    r = dax(client, allm)
    assert r.status_code == 200, r.json()


def test_forecast_picks_trend_method_for_steady_rise(client):
    r = client.post("/api/bitools/forecast", json={"values": bc.INFOGRAPHIC_SERIES, "horizon": 3}).json()
    assert r["best"] in ("holt_trend", "linear_trend")
    assert r["forecast"] == [40000.0, 42000.0, 44000.0]
    ma = next(m for m in r["methods"] if m["id"] == "moving_average_3")
    assert ma["rmse"] > 1000 and r["warnings"]


def test_forecast_inputs_validated(client):
    assert client.post("/api/bitools/forecast", json={"values": [1, 2, 3]}).status_code == 400
    assert client.post("/api/bitools/forecast", json={"values": "10, 12, 14, x, 18, 20, 22, 24, 26"}).status_code == 400
    assert client.post("/api/bitools/forecast", json={"values": "10 12 14 16 18 20 22 24 26 28", "horizon": 99}).status_code == 422
    assert client.get("/api/bitools/forecast/sample").json()["values"][0] == 20000


def test_variance_favourable_logic(client):
    rows = [{"item": "Sales", "kind": "revenue", "budget": 1000, "actual": 1200},
            {"item": "Rent", "kind": "cost", "budget": 500, "actual": 600},
            {"item": "Ads", "kind": "cost", "budget": 300, "actual": 200}]
    r = client.post("/api/bitools/variance", json={"rows": rows, "threshold_pct": 10}).json()
    by = {o["item"]: o for o in r["lines"]}
    assert by["Sales"]["favourable"] and not by["Rent"]["favourable"] and by["Ads"]["favourable"]
    assert client.post("/api/bitools/variance", json={"rows": [{"item": "x", "kind": "oops", "budget": 1, "actual": 1}]}).status_code == 400


def test_scenario_break_even_and_sensitivity(client):
    r = client.post("/api/bitools/scenario", json={"price": 100, "volume": 800, "unit_cost": 60, "fixed_cost": 20000}).json()
    assert r["break_even_units"] == 500
    assert client.post("/api/bitools/scenario", json={"price": -1, "volume": 1, "unit_cost": 1}).status_code == 400


def test_dist_fit_and_calc(client):
    import random
    random.seed(3)
    both = [random.gauss(10, 1) for _ in range(80)] + [random.gauss(30, 1) for _ in range(80)]
    r = client.post("/api/bitools/dist/fit", json={"values": both}).json()
    assert "bimodal" in str(r).lower()
    n = client.post("/api/bitools/dist/calc", json={"kind": "normal", "params": {"mean": 0, "sd": 1}, "x": 1.96}).json()
    assert abs(n["at"]["cdf"] - 0.975) < 0.001
    assert client.post("/api/bitools/dist/calc", json={"kind": "normal", "params": {"mean": 0, "sd": -1}, "x": 0}).status_code == 400
    assert client.post("/api/bitools/dist/calc", json={"kind": "binomial", "params": {"n": 10, "p": 2}, "x": 3}).status_code == 400
    assert client.get("/api/bitools/dist/reference").json()


def test_doc_invoice_checks_pass_and_catch_a_wrong_total(client):
    good = client.post("/api/bitools/doc", json={"text": dr.SAMPLES["invoice"], "csv": True}).json()
    assert good["kind"] == "invoice" and good["fields"]["total"] == 496.78 and all(c["ok"] for c in good["checks"]) and good["csv"].startswith("description")
    bad = client.post("/api/bitools/doc", json={"text": dr.SAMPLES["invoice"].replace("496.78", "469.78")}).json()
    assert bad["needs_review"] and any(not c["ok"] for c in bad["checks"])


def test_doc_statement_rollforward_and_ambiguous_dates(client):
    r = client.post("/api/bitools/doc", json={"text": dr.SAMPLES["statement"]}).json()
    assert r["kind"] == "statement" and all(c["ok"] for c in r["checks"]) and any("day/month" in w for w in r["warnings"])
    bad = client.post("/api/bitools/doc", json={"text": dr.SAMPLES["statement"].replace("2,213.60\nClosing", "9.00\nClosing")}).json()
    assert any(not c["ok"] for c in bad["checks"])


def test_doc_duplicate_empty_and_csv_injection(client):
    r = client.post("/api/bitools/doc", json={"text": dr.SAMPLES["invoice"]}).json()
    again = client.post("/api/bitools/doc", json={"text": dr.SAMPLES["invoice"], "seen": [r["duplicate_key"]]}).json()
    assert again["duplicate"]
    assert client.post("/api/bitools/doc", json={"text": "   "}).status_code == 400
    assert client.post("/api/bitools/doc", json={"text": "hello", "kind": "bogus"}).status_code == 400
    assert dr._safe("=HYPERLINK(1)") == "'=HYPERLINK(1)" and dr._safe("Plain") == "Plain"
    evil = {"rows": [{"description": "=cmd|' /C calc'!A0", "amount": 1.0}]}
    assert "'=cmd" in dr.to_csv(evil)


def test_dax_bare_table_name_only_valid_in_countrows(client):
    assert dax(client, [{"name": "N", "formula": "COUNTROWS(Sales)"}]).json()["rows"][0]["N"] == 360
    assert dax(client, [{"name": "N", "formula": "COUNTROWS(Other)"}]).status_code == 400
    assert dax(client, [{"name": "N", "formula": "Sales + 1"}]).status_code == 400
