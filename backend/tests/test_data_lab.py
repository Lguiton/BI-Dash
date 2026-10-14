import pytest

from app.services import data_calc as dc, data_dbt as dd, data_flow as df, known_errors
from app.services.data_dbt import DataLabError


def test_dbt_order_tests_and_impact():
    r = dd.run(**dd.SAMPLE)
    assert r["order"] == ["stg_orders", "fct_customer_sales"]
    t = {x["test"]: x for x in r["tests"]}
    assert not t["stg_orders.order_id unique"]["passed"] and t["stg_orders.order_id unique"]["failing"] == 1
    assert t["stg_orders.amount not_null"]["failing"] == 1
    assert t["stg_orders.customer_id relationships(raw_customers.id)"]["failing"] == 2
    assert t["fct_customer_sales row_count_min(2)"]["passed"]
    assert r["downstream"]["raw_orders"] == ["fct_customer_sales", "stg_orders"]
    assert r["models"][1]["rows"] == 2 and "stg_orders" in r["models"][1]["compiled_sql"]


def test_dbt_errors_are_clear():
    for bad in ("-- model: a\nselect * from {{ ref('nope') }}", "-- model: a\nselect 1 from {{ ref('b') }}\n-- model: b\nselect 1 from {{ ref('a') }}",
                "-- model: a\ndrop table x", "-- model: a\nselect 1; select 2", "no header", "-- model: a\nselect {{ var('x') }}"):
        with pytest.raises(DataLabError):
            dd.run("", bad)
    with pytest.raises(DataLabError):
        dd.run("", "-- model: a\nselect 1 as x", "a.x sparkle")
    ok = dd.run("", "-- model: a\nselect 1 as x")
    assert ok["models"][0]["rows"] == 1


def test_dbt_cannot_read_files():
    with pytest.raises(DataLabError):
        dd.run("", "-- model: a\nselect * from read_csv('/etc/passwd')")


def test_formulas():
    r = dc.evaluate(dc.SAMPLE)
    v = {c["cell"]: c["value"] for c in r["cells"]}
    assert v["D4"] == 51 and v["E2"] == "small" and v["E3"] == 12 and v["E4"] == "#DIV/0!" and v["F1"] == "n/a"
    assert "E4" in r["errors"]
    c = dc.evaluate("A1: =B1+1\nB1: =A1+1")
    assert c["cycle"] and {x["value"] for x in c["cells"]} == {"#CIRC!"}
    x = {c["cell"]: c["value"] for c in dc.evaluate("A1: =0.1+0.2\nA2: =ROUND(A1,2)=0.3\nA3: =\"a\"&1&TRUE\nA4: =ROUND(2.5,0)\nA5: =COUNTIF(B1:B3,\">1\")\nA6: =SUMIF(B1:B3,\">1\",B1:B3)\nA7: =2^3^2\nA8: =-2^2\nB1: 1\nB2: 2\nB3: 5")["cells"]}
    assert x["A2"] is True and x["A3"] == "a1TRUE" and x["A4"] == 3 and x["A5"] == 2 and x["A6"] == 7 and x["A7"] == 64 and x["A8"] == 4
    assert dc.evaluate("A1: x\nB1: =A1+1\nC1: =SUM(A1:B1)")["cells"][1]["value"] == "#VALUE!"
    for bad in ("", "nonsense", "A1: 1\nA1: 2"):
        with pytest.raises(DataLabError):
            dc.evaluate(bad)


def test_dag():
    r = df.dag(**df.DAG_SAMPLE)
    assert r["total_minutes"] == 49 and r["ideal_minutes"] == 32 and r["all_ok"] and r["critical_path"][0] == "extract_b"
    f = df.dag("a | - | 5 | 3 | 1\nb | a | 2\nc | - | 4")
    assert f["status"] == {"a": "failed", "b": "upstream_failed", "c": "success"}
    assert df.dag("a | - | 5\nb | - | 5", 1)["total_minutes"] == 10 and df.dag("a | - | 5\nb | - | 5", 2)["total_minutes"] == 5
    for bad in ("a | b | 1\nb | a | 1", "a | z | 1", "a | - | 0", "a|-"):
        with pytest.raises(DataLabError):
            df.dag(bad)


def test_cron():
    assert df.cron("30 2 * * 1-5", "2026-03-06 12:00")["next_runs"][0] == "Mon 2026-03-09 02:30"
    r = df.cron("0 0 13 * 5", "2026-01-01")
    assert r["next_runs"][:3] == ["Fri 2026-01-02 00:00", "Fri 2026-01-09 00:00", "Tue 2026-01-13 00:00"] and r["notes"]
    assert df.cron("*/20 9-10 * jan,feb mon", "2026-01-01")["next_runs"][0] == "Mon 2026-01-05 09:00"
    for bad in ("* * *", "61 * * * *", "* * * * 9", "a b c d e"):
        with pytest.raises(DataLabError):
            df.cron(bad)


def test_stream():
    r = df.stream(**df.STREAM_SAMPLE)
    assert len(r["late_dropped"]) == 3 and r["idle_consumers"] == 1
    assert sum(p["events"] for p in r["partitions"]) == 9
    same = df.stream("1 a 1\n2 a 1\n3 a 1", 4, 1)
    assert sum(1 for p in same["partitions"] if p["events"]) == 1
    assert len(df.stream("1 a 1\n3 a 1\n20 a 1", 1, 1, 6, "session", 0, 4, 4)["windows"]) == 2
    assert not df.stream(**{**df.STREAM_SAMPLE, "lateness": 50})["late_dropped"]
    with pytest.raises(DataLabError):
        df.stream("1 a", 1, 1)


def test_endpoints_and_sources(client):
    ref = client.get("/api/datalab/reference").json()
    assert client.post("/api/datalab/dbt", json=ref["samples"]["dbt"]).json()["tests_failed"] == 4
    assert client.post("/api/datalab/formulas", json={"cells": ref["samples"]["calc"]}).status_code == 200
    assert client.post("/api/datalab/cron", json={"expression": "bad"}).status_code == 400
    for m in ("data_dbt", "data_calc", "data_flow"):
        assert m in known_errors.SOURCES
