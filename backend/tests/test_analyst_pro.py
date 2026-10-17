from fastapi.testclient import TestClient

from app.main import app
from app.services import agent_tools, analyst_pro

c = TestClient(app)
BOOK = [58, 58, 60, 53, 48, 68, 74, 86, 93, 99, 93, 82, 74, 65, 79, 55, 63, 87, 91, 95, 112, 120, 111, 95, 89, 84, 91, 79, 73, 97, 101, 111, 128, 140, 137, 111]


def post(path, **b):
    return c.post(f"/api/analystpro/{path}", json=b)


def test_forecast_gives_range_and_checks_itself():
    r = post("forecast", values=BOOK, season=12, horizon=2).json()
    assert r["seasonal"] and r["beats_repeat_last_value"]
    f = r["forecast"]
    assert abs(f[0]["forecast"] - 105.5) < 0.1 and abs(f[1]["forecast"] - 99.6) < 0.1
    assert f[0]["low"] < f[0]["forecast"] < f[0]["high"] and (f[1]["high"] - f[1]["low"]) > (f[0]["high"] - f[0]["low"])
    short = post("forecast", values=[10, 12, 13, 15, 16, 18, 19, 21], season=12, horizon=2).json()
    assert not short["seasonal"] and short["forecast"][0]["forecast"] > 21
    assert post("forecast", values=[1, 2], season=12).status_code == 400
    pasted = post("forecast", text="\n".join(map(str, BOOK)), season=12).json()
    assert pasted["points"] == 36


def test_cohort_funnel_pareto():
    r = post("cohort", text="a,2026-01-05\na,2026-02-01\nb,2026-01-10\nc,2026-02-03\nc,2026-03-02").json()
    assert r["cohorts"][0] == {"cohort": "2026-01", "size": 2, "retention_pct": [100.0, 50.0, 0.0]}
    assert post("cohort", text="a,notadate").status_code == 400 and post("cohort", text="").status_code == 400
    f = post("funnel", text="Visited,1000\nSigned up,300\nPaid,60").json()
    assert f["biggest_leak"]["between"] == "Signed up to Paid" and f["steps"][2]["overall_pct"] == 6.0
    assert "warning" in post("funnel", text="A,10\nB,20").json()
    p = post("calc/pareto", text="A,50\nB,30\nC,10\nD,10").json()
    assert p["vital_few"] == 2 and p["rows"][1]["cumulative_pct"] == 80.0


def test_cohort_from_a_table():
    from app.services import datasets
    datasets.import_rows(["cust", "d"], [["a", "2026-01-05"], ["a", "2026-02-01"], ["b", "2026-01-10"]], "tmp_cohort_t", "replace", source="test")
    try:
        r = post("cohort", table="tmp_cohort_t", id_col="cust", date_col="d").json()
        assert r["users"] == 2 and r["cohorts"][0]["retention_pct"][:2] == [100.0, 50.0]
        assert post("cohort", table="tmp_cohort_t", id_col="nope", date_col="d").status_code == 400
    finally:
        datasets.delete_table("tmp_cohort_t")


def test_finance_maths():
    assert post("calc/breakeven", fixed_costs=5000, price=25, variable_cost=10).json()["units_needed"] == 334
    assert post("calc/breakeven", fixed_costs=5000, price=10, variable_cost=10).status_code == 400
    u = post("calc/unit", monthly_revenue_per_customer=50, gross_margin_pct=80, monthly_churn_pct=5, cac=200).json()
    assert u["lifetime_value"] == 800.0 and u["ltv_to_cac"] == 4.0 and u["payback_months"] == 5.0
    assert post("calc/runway", cash=30000, monthly_costs=10000, monthly_income=4000).json()["runway_months"] == 5.0
    assert post("calc/runway", cash=1000, monthly_costs=100, monthly_income=500).json()["runway_months"] is None
    cc = post("calc/cycle", receivables=30000, revenue=365000, inventory=20000, cogs=200000, payables=10000).json()
    assert cc["days_sales_outstanding"] == 30.0 and abs(cc["cash_conversion_days"] - 48.25) < 0.06
    n = post("calc/npv", rate=10, cashflows="-10000, 3000, 4000, 5000").json()
    assert n["npv"] == -210.37 and 8.8 < n["irr_pct"] < 9.0
    m = post("calc/margin", revenue=1000, cogs=600, operating_costs=250).json()
    assert m["gross_margin_pct"] == 40.0 and m["operating_margin_pct"] == 15.0 and m["markup_pct"] == 66.7
    ab = post("calc/ab", a_visitors=1000, a_conversions=100, b_visitors=1000, b_conversions=130).json()
    assert abs(ab["p_value"] - 0.0355) < 0.001 and "likely" in ab["verdict"]
    assert post("calc/ab", a_visitors=10, a_conversions=20, b_visitors=10, b_conversions=1).status_code == 400
    assert post("calc/nope", x=1).status_code == 400


def test_recipes_run_and_star_and_reviews():
    rec = c.get("/api/analystpro/recipes").json()["recipes"]
    assert len(rec) == 10
    for r in rec:
        out = c.get(f"/api/analystpro/recipes/{r['id']}").json()
        assert out["rows"] and out["columns"]
    run = c.get("/api/analystpro/recipes/running").json()
    assert run["rows"][-1][2] == 10900
    assert c.get("/api/analystpro/recipes/zz").status_code == 404
    s = post("calc/star", columns="order_id, customer_id, order_date, product_name, amount, quantity, region").json()
    assert set(s["fact_measures"]) == {"amount", "quantity"} and "CREATE TABLE fact" in s["sql"] and "dim_customer" in s["sql"]
    assert post("calc/star", columns="a,b").status_code == 400
    d = post("calc/review", text="14 KPIs, a pie with 12 slices, dual axis, 3D bars, rainbow colors").json()
    assert len(d["findings"]) >= 4 and d["charts"]
    assert post("calc/review", text="x").status_code == 400
    mc = post("calc/metric", name="Active customers", formula="distinct paying customers in the month").json()
    assert "owner" in mc["missing"] and "METRIC: Active customers" in mc["text"]
    rq = post("calc/requirements", role="finance", audience="CFO").json()
    assert rq["questions"] and "CFO" in rq["document"]
    assert post("calc/requirements", role="nobody").status_code == 400
    assert len(c.get("/api/analystpro/dax").json()["rows"]) >= 10 and c.get("/api/analystpro/reference").json()["qa"]


def test_agent_tools():
    t, e = agent_tools.run_tool("analyst", {"tool": "forecast_range", "args": {"values": BOOK, "season": 12, "horizon": 1}})
    assert not e and "forecast" in t
    t, e = agent_tools.run_tool("analyst", {"tool": "funnel", "args": {"text": "A,100\nB,50"}})
    assert not e
    t, e = agent_tools.run_tool("scientist", {"tool": "unit_economics", "args": {"monthly_revenue_per_customer": 50, "gross_margin_pct": 80, "monthly_churn_pct": 5, "cac": 200}})
    assert not e and "lifetime_value" in t
    assert analyst_pro.reference()["rollout"]
