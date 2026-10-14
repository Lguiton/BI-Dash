import math
from datetime import date, timedelta

import pytest

from app.services import biz_models, biz_packs, ds_tools as ds
from app.services.db import get_cursor


@pytest.fixture()
def tbl(client):
    with get_cursor() as cur:
        cur.execute("CREATE OR REPLACE TABLE dstest (d DATE, amt DOUBLE, qty DOUBLE, grp VARCHAR)")
        d0 = date(2026, 1, 1)
        rows = [(d0 + timedelta(days=i), 100 + 20 * (1 if (d0 + timedelta(days=i)).weekday() >= 5 else 0) + (i % 3), 5 + (i % 4), "a" if i % 2 else "b") for i in range(150)]
        cur.executemany("INSERT INTO dstest VALUES (?,?,?,?)", rows)
    return "dstest"


def test_forecast_weekly_pattern(tbl):
    r = ds.forecast(tbl, "d", "amt", "sum", "day", 14)
    assert r["windows_tested"] >= 1 and len(r["forecast"]) == 14
    assert r["method_used"] != "naive"          # weekend bump is learnable
    assert all(p["low"] <= p["forecast"] <= p["high"] for p in r["forecast"])
    assert r["backtest"][0]["mae"] <= r["backtest"][-1]["mae"]
    assert "caution" in r and "range_note" in r


def test_forecast_errors(tbl):
    with pytest.raises(ds.DsError):
        ds.forecast(tbl, "amt", "amt")
    with pytest.raises(ds.DsError):
        ds.forecast(tbl, "d", "grp")
    with pytest.raises(ds.DsError):
        ds.forecast(tbl, "d", "amt", horizon=500)
    with pytest.raises(ds.DsError):
        ds.forecast(tbl, "d", "amt", freq="month")      # 5 months only


def test_segments(client):
    import random
    random.seed(1)
    with get_cursor() as cur:
        cur.execute("CREATE OR REPLACE TABLE segtest (spend DOUBLE, visits DOUBLE)")
        rows = [(random.gauss(20, 3), random.gauss(2, .5)) for _ in range(80)] + [(random.gauss(200, 10), random.gauss(12, 1)) for _ in range(40)]
        cur.executemany("INSERT INTO segtest VALUES (?,?)", rows)
    r = ds.segments("segtest", ["spend", "visits"])
    assert r["k"] == 2 and r["separation"] == "clear"
    assert r["segments"][0]["rows"] == 80 and "low" in r["segments"][0]["name"].lower()
    with pytest.raises(ds.DsError):
        ds.segments("segtest", ["spend"])
    with pytest.raises(ds.DsError):
        ds.segments("segtest", ["spend", "nope"])


def test_model_card_and_drift(client):
    from app.services import ml_studio
    biz_packs.install_sample("repair-jobs")
    cols = [c["name"] for c in __import__("app.services.analyst_tools", fromlist=["x"]).columns("repair-jobs")]
    num = [c for c in cols if c in biz_packs.find("repair-jobs")["nums"]]
    rep = ml_studio.build("repair-jobs", num[0], None, "auto")
    h = ds.model_card(rep["id"], owner="Lamarcus <b>x</b>")
    assert "Model card" in h and "SAMPLE DATA" in h and "<b>x</b>" not in h
    with pytest.raises(ds.DsError):
        ds.model_card("nope-id")
    d = ds.drift(rep["id"], 30)
    assert d["status"] in ("ok", "watch", "retrain") and d["older"]["rows"] > 20
    with pytest.raises(ds.DsError):
        ds.drift("nope-id")
