import math

import pytest

from app.services import sysanalysis as sa
from tests.conftest import csv_file


def test_mm1_by_hand():
    r = sa.mm1(8, 10)
    assert (r["utilization"], r["avg_in_system"], r["avg_in_queue"], r["avg_time_in_system"], r["avg_wait"]) == (0.8, 4.0, 3.2, 0.5, 0.4)
    assert sa.mm1(10, 10)["stable"] is False


def test_erlang_c_by_hand_and_consistency():
    r = sa.erlang_c(1, 1, 2)                       # worked by hand: C = 1/3, Wq = 1/3
    assert r["p_wait"] == round(1 / 3, 3) and r["avg_wait"] == round(1 / 3, 4) and r["utilization"] == 0.5
    one = sa.erlang_c(8, 10, 1)                    # one server must match M/M/1
    assert one["avg_wait"] == sa.mm1(8, 10)["avg_wait"] and one["p_wait"] == 0.8
    assert math.isclose(sa.erlang_c(5, 1, 7)["avg_in_system"], 5 * sa.erlang_c(5, 1, 7)["avg_time_in_system"], rel_tol=1e-3)   # Little's law


def test_servers_needed_for_target():
    need = sa.queue(10, 1, 11, target_wait=0.05)["servers_for_target_wait"]
    assert need > 11
    assert sa.erlang_c(10, 1, need)["avg_wait"] <= 0.05 < sa.erlang_c(10, 1, need - 1)["avg_wait"]      # the smallest crew that meets it


def test_availability_numbers():
    a = sa.availability(99.9, 30, 20)
    assert a["error_budget_minutes"] == 43.2 and a["remaining_minutes"] == 23.2 and a["burn_pct"] == 46.3
    assert {x["period"]: x["downtime_minutes"] for x in a["allowed_downtime"]}["per year"] == 525.6
    assert sa.availability(99.9, parts=[99.9, 99.5], mode="serial")["composite"]["availability_pct"] == round(100 * 0.999 * 0.995, 5)
    par = sa.availability(99.9, parts=[99, 99], mode="parallel")["composite"]
    assert par["availability_pct"] == 99.99 and par["meets_slo"]
    with pytest.raises(sa.SaError):
        sa.availability(100)


def test_cost_benefit_by_hand():
    r = sa.cost_benefit(1000, 500, 100, 3, 10)
    assert r["annual_net"] == 400 and r["npv"] == round(400 * (1 / 1.1 + 1 / 1.21 + 1 / 1.331) - 1000, 2)
    assert r["payback_years"] == 2.5 and r["roi_pct"] == 20.0 and 9 < r["irr_pct"] < 10 and "Doesn't pay back" in r["verdict"]
    good = sa.cost_benefit(1000, 600, 100, 3, 10)
    assert good["npv"] > 0 and good["irr_pct"] > 10 and good["discounted_payback_years"] < 3


def test_capacity_by_hand():
    r = sa.capacity(50, 100, 10)
    assert r["months_to_full"] == round(math.log(2) / math.log(1.1), 1) == 7.3
    assert sa.capacity(90, 100, 5)["months_to_threshold"] == 0 and sa.capacity(10, 100, 0)["months_to_full"] is None


def test_calculator_endpoints_validate(client):
    assert client.get("/api/sysanalyst/calc/queue", params={"arrival_rate": 8, "service_rate": 10}).json()["avg_wait"] == 0.4
    assert client.get("/api/sysanalyst/calc/queue", params={"arrival_rate": -1, "service_rate": 10}).status_code == 422
    assert client.get("/api/sysanalyst/calc/availability", params={"slo": 100}).status_code == 400
    assert client.get("/api/sysanalyst/calc/availability", params={"parts": "abc"}).status_code == 400
    assert client.get("/api/sysanalyst/calc/cost-benefit", params={"initial": 1000, "annual_benefit": 600, "annual_cost": 100}).json()["npv"] > 0
    assert client.get("/api/sysanalyst/calc/capacity", params={"load": 50, "capacity": 100, "growth": 10}).json()["months_to_full"] == 7.3


def test_requirements_traceability(client):
    assert client.post("/api/sysanalyst/requirements", json={"title": ""}).status_code == 400
    assert client.post("/api/sysanalyst/requirements", json={"title": "x", "priority": "urgent"}).status_code == 400
    a = client.post("/api/sysanalyst/requirements", json={"title": "A", "status": "built", "acceptance": "ok", "priority": "must"}).json()
    b = client.post("/api/sysanalyst/requirements", json={"title": "B", "status": "tested", "acceptance": "ok", "test_ref": "tests/x.py"}).json()
    client.post("/api/sysanalyst/requirements", json={"title": "C", "status": "proposed", "priority": "must"})
    assert (a["code"], b["code"]) == ("REQ-001", "REQ-002")
    t = client.get("/api/sysanalyst").json()["traceability"]
    assert t["test_coverage_pct"] == 50.0
    problems = {(g["code"], g["problem"]) for g in t["gaps"]}
    assert ("REQ-001", "built but no test is linked") in problems and ("REQ-003", "a must-have that is still only proposed") in problems
    assert client.put(f"/api/sysanalyst/requirements/{a['id']}", json={**a, "test_ref": "tests/y.py"}).json()["test_ref"] == "tests/y.py"
    assert client.delete(f"/api/sysanalyst/requirements/{b['id']}").status_code == 200
    client.post("/api/workspaces/active", json={"name": "real"})
    assert client.get("/api/sysanalyst").json()["requirements"] == []
    assert client.post("/api/sysanalyst/requirements/example").status_code == 409


def test_example_requirements_reference_real_tests(client):
    import pathlib
    assert client.post("/api/sysanalyst/requirements/example").json()["loaded"] == 10
    root = pathlib.Path(__file__).resolve().parents[1]
    for r in client.get("/api/sysanalyst").json()["requirements"]:
        if r["test_ref"]:
            f, _, fn = r["test_ref"].partition("::")
            assert (root / f).is_file(), f
            if fn:
                assert f"def {fn}(" in (root / f).read_text(), r["test_ref"]


def test_feasibility(client):
    f = client.put("/api/sysanalyst/feasibility", json={"technical": {"score": 5, "weight": 2}, "economic": {"score": 4}, "legal": {"score": 2}, "operational": {"score": 4}, "schedule": {"score": 4}}).json()
    assert f["weighted_score"] == round((5 * 2 + 4 + 2 + 4 + 4) / 6, 2) and f["weakest"] == "Legal" and f["verdict"] == "Feasible with changes"
    assert client.put("/api/sysanalyst/feasibility", json={"legal": {"score": 9}}).status_code == 400


def test_dictionary_and_erd(client):
    client.post("/api/data/import", files=csv_file("a,b\n1,x\n2,\n", "t.csv"))
    d = client.get("/api/sysanalyst/dictionary").json()
    names = {t["name"]: t for t in d["tables"]}
    assert {"fact_operations", "dim_entities", "t"} <= set(names) and names["fact_operations"]["rows"] == 6
    cols = {c["name"]: c for c in names["t"]["columns"]}
    assert cols["b"]["null_pct"] == 50.0 and cols["a"]["distinct"] == 2
    assert next(c for c in names["dim_entities"]["columns"] if c["name"] == "entity_id")["key"] == "PRIMARY KEY"
    assert d["relationships"][0]["valid"] and "erDiagram" in d["mermaid"] and "dim_entities ||--o{ fact_operations" in d["mermaid"]


def test_process_analysis(client):
    p = client.get("/api/sysanalyst/process").json()
    assert p["available"] and p["duration"]["avg"] == round(sum([240, 260, 210, 300, 250, 270]) / 6, 1)
    assert p["littles_law"]["arrivals_per_day"] == 1.0 and p["queue_inputs"]["service_minutes"] == p["duration"]["avg"]
    client.post("/api/workspaces/active", json={"name": "real"})
    assert client.get("/api/sysanalyst/process").json()["available"] is False
