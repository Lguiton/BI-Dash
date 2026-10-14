from datetime import date, timedelta

import pytest

from app.services import pm

T = date(2026, 6, 15)       # a Monday


def d(n):
    return (T + timedelta(days=n)).isoformat()


@pytest.fixture()
def api(client, monkeypatch):
    monkeypatch.setattr(pm, "today", lambda: T)
    return client


def add(api, **kw):
    r = api.post("/api/pm/items", json=kw)
    assert r.status_code == 200, r.text
    return r.json()


def test_rice_and_wsjf_by_hand(api):
    a = add(api, title="A", reach=100, impact=2, confidence=0.8, effort=4, points=2, value=8, time_crit=5, risk_red=3, moscow="must")
    b = add(api, title="B", reach=50, impact=3, confidence=1, effort=1, points=4, value=2, time_crit=2, risk_red=2, moscow="could")
    add(api, title="C")                             # unscored
    p = api.get("/api/pm", params={"as_of": d(0)}).json()["prioritization"]
    rows = {r["id"]: r for r in p["rows"]}
    assert rows[a["id"]]["rice"] == 40.0            # 100*2*0.8/4
    assert rows[b["id"]]["rice"] == 150.0           # 50*3*1/1
    assert rows[b["id"]]["rice_rank"] == 1 and rows[a["id"]]["rice_rank"] == 2
    assert rows[a["id"]]["wsjf"] == 8.0             # (8+5+3)/2
    assert rows[b["id"]]["wsjf"] == 1.5             # 6/4
    assert p["unscored"] == 1 and p["moscow"]["must"]["points"] == 2 and p["moscow_unclassified"] == 1


def test_critical_path_by_hand(api):
    # A(3) -> B(2) -> D(4);  A -> C(6) -> D.   Path A,C,D = 13 days; B has 4 days of float.
    a = add(api, title="A", kind="task", duration_days=3)
    b = add(api, title="B", kind="task", duration_days=2, deps=[a["id"]])
    c = add(api, title="C", kind="task", duration_days=6, deps=[a["id"]])
    dd = add(api, title="D", kind="task", duration_days=4, deps=[b["id"], c["id"]])
    s = api.get("/api/pm", params={"as_of": d(0)}).json()["schedule"]
    assert s["available"] and s["duration_days"] == 13
    rows = {r["id"]: r for r in s["rows"]}
    assert [rows[x["id"]]["critical"] for x in (a, b, c, dd)] == [True, False, True, True]
    assert rows[b["id"]]["float"] == 4 and rows[b["id"]]["es"] == 3 and rows[dd["id"]]["es"] == 9


def test_dependency_cycle_is_reported_not_crashed(api):
    a = add(api, title="A", kind="task", duration_days=1)
    b = add(api, title="B", kind="task", duration_days=1, deps=[a["id"]])
    api.patch(f"/api/pm/items/{a['id']}", json={"deps": [b["id"]]})
    s = api.get("/api/pm").json()["schedule"]
    assert s["available"] is False and "loop" in s["reason"]
    assert api.patch(f"/api/pm/items/{a['id']}", json={"deps": [a["id"]]}).status_code == 400


def test_earned_value_by_hand(api):
    # BAC 1000. A (400, 10 days from -10) is done. B (600, 20 days from -10) is half way through its plan.
    add(api, title="A", planned_cost=400, start_date=d(-10), duration_days=10, status="done", actual_cost=500)
    add(api, title="B", planned_cost=600, start_date=d(-10), duration_days=20, status="doing", actual_cost=250)
    e = api.get("/api/pm", params={"as_of": d(0)}).json()["earned_value"]
    assert e["bac"] == 1000 and e["pv"] == 700.0           # 400 + 600*0.5
    assert e["ev"] == 400 and e["ac"] == 750
    assert e["cpi"] == round(400 / 750, 3) and e["spi"] == round(400 / 700, 3)
    assert e["eac"] == round(1000 / (400 / 750), 2) and e["cv"] == -350 and e["sv"] == -300
    assert e["tcpi"] == round((1000 - 400) / (1000 - 750), 3)


def test_velocity_burndown_and_forecast(api):
    s1 = api.post("/api/pm/sprints", json={"name": "S1", "start_date": d(-28), "end_date": d(-15)}).json()["id"]
    s2 = api.post("/api/pm/sprints", json={"name": "S2", "start_date": d(-14), "end_date": d(-1)}).json()["id"]
    s3 = api.post("/api/pm/sprints", json={"name": "S3", "start_date": d(-2), "end_date": d(11)}).json()["id"]
    add(api, title="a", points=8, sprint_id=s1, status="done", started_at=d(-27), done_at=d(-20))
    add(api, title="b", points=2, sprint_id=s1)                              # carried over, not done
    add(api, title="c", points=10, sprint_id=s2, status="done", started_at=d(-13), done_at=d(-5))
    add(api, title="d", points=6, sprint_id=s3, status="done", started_at=d(-2), done_at=d(-1))
    add(api, title="e", points=4, sprint_id=s3, status="doing", started_at=d(-1))
    add(api, title="f", points=8, status="backlog")
    sp = api.get("/api/pm", params={"as_of": d(0)}).json()["sprint"]
    assert sp["velocity"]["history"] == [8, 10] and sp["velocity"]["avg_last3"] == 9.0
    bd = sp["burndown"]
    assert bd["sprint"] == "S3" and bd["committed"] == 10 and bd["remaining"] == 4
    assert bd["points"][0]["ideal"] == 10 and bd["points"][-1]["ideal"] == 0 and bd["points"][-1]["actual"] is None
    assert sp["forecast"]["remaining_points"] == 4 + 2 + 8 and sp["forecast"]["likely"]["sprints"] == round(14 / 9, 1)


def test_flow_cycle_time_and_littles_law(api):
    for n in range(4):
        add(api, title=f"w{n}", status="done", created_at=d(-20), started_at=d(-10 - n), done_at=d(-8 - n))       # cycle time is always 2
    add(api, title="in flight", status="doing", started_at=d(-1), created_at=d(-3))
    f = api.get("/api/pm", params={"as_of": d(0)}).json()["flow"]
    assert f["cycle_days"]["avg"] == 2.0 and f["lead_days"]["avg"] == 10.5 and f["wip"] == 1
    assert sum(w["done"] for w in f["throughput_weekly"]) == 4
    assert f["cfd"][-1]["done"] == 4 and f["cfd"][-1]["doing"] == 1 and len(f["cfd"]) == 30


def test_status_moves_stamp_dates_and_validate(api):
    it = add(api, title="x")
    moved = api.patch(f"/api/pm/items/{it['id']}", json={"status": "doing"}).json()
    assert moved["started_at"] == d(0) and moved["done_at"] is None
    done = api.patch(f"/api/pm/items/{it['id']}", json={"status": "done"}).json()
    assert done["done_at"] == d(0)
    back = api.patch(f"/api/pm/items/{it['id']}", json={"status": "doing"}).json()
    assert back["done_at"] is None
    for bad in ({"title": ""}, {"title": "t", "status": "nope"}, {"title": "t", "points": -1}, {"title": "t", "confidence": 5}, {"title": "t", "start_date": "tomorrow"}):
        assert api.post("/api/pm/items", json=bad).status_code == 400


def test_risks_okrs_and_workspace_isolation(api):
    api.post("/api/pm/risks", json={"title": "r1", "probability": 0.5, "impact_usd": 1000})
    api.post("/api/pm/risks", json={"title": "r2", "probability": 0.1, "impact_usd": 500, "status": "closed"})
    r = api.get("/api/pm").json()["risks"]
    assert r["exposure"] == 500.0 and r["open_count"] == 1
    assert api.post("/api/pm/risks", json={"title": "x", "probability": 1.5, "impact_usd": 1}).status_code == 400
    api.post("/api/pm/okrs", json={"objective": "O", "kr": "k1", "start_value": 0, "target_value": 10, "current_value": 5})
    api.post("/api/pm/okrs", json={"objective": "O", "kr": "k2", "start_value": 100, "target_value": 0, "current_value": 100})
    o = api.get("/api/pm").json()["okrs"]["objectives"][0]
    assert o["progress_pct"] == 25.0                       # (50% + 0%) / 2
    api.post("/api/workspaces/active", json={"name": "real"})
    p = api.get("/api/pm").json()
    assert p["empty"] and p["risks"]["open_count"] == 0 and p["okrs"]["objectives"] == []
    assert api.post("/api/pm/example").status_code == 409     # never fake data in Real


def test_example_project_loads_and_every_view_computes(api):
    assert api.post("/api/pm/example").status_code == 200
    assert api.post("/api/pm/example").status_code == 409
    o = api.get("/api/pm").json()
    assert o["schedule"]["available"] and o["earned_value"]["available"] and o["sprint"]["burndown"] and o["sprint"]["forecast"]
    assert o["flow"]["cycle_days"]["n"] >= 3 and o["risks"]["open_count"] == 4 and len(o["okrs"]["objectives"]) == 1
    item = o["items"][0]
    assert api.delete(f"/api/pm/items/{item['id']}").status_code == 200


def test_product_analytics_retention_by_hand(api):
    csv = ("record_date,entity_id,revenue,operational_cost,units_processed,status\n"
           "2026-01-05,A,10,1,1,Completed\n2026-01-20,B,10,1,1,Completed\n2026-02-03,A,10,1,1,Completed\n"
           "2026-03-02,A,10,1,1,Pending\n2026-02-10,C,10,1,1,Completed\n")
    from tests.conftest import csv_file
    assert api.post("/api/ingest/csv?mode=replace", files=csv_file(csv)).status_code in (200, 409)
    pa = api.get("/api/pm/product-analytics").json()
    jan = next(c for c in pa["cohorts"] if c["cohort"] == "2026-01")
    assert jan["size"] == 2 and jan["retention"][:3] == [100.0, 50.0, 50.0]      # A stays in Feb and Mar, B only in January
    assert {f["stage"]: f["n"] for f in pa["funnel"]} == {"Completed": 4, "Pending": 1}
