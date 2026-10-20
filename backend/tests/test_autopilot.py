"""Autopilot: upload a file, every fitting analysis runs, nothing is written."""
import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import autopilot

c = TestClient(app)


def _ab_csv(n=2000, pa=0.10, pb=0.16):
    import random
    r = random.Random(1)
    rows = ["visitor_id,group,converted,order_value"]
    for i in range(n):
        g = "control" if i % 2 == 0 else "variant"
        conv = 1 if r.random() < (pa if g == "control" else pb) else 0
        rows.append(f"V{i},{g},{conv},{conv * round(20 + r.random() * 30, 2)}")
    return "\n".join(rows).encode()


def _by_id(rep):
    return {s["id"]: s for s in rep["steps"]}


def test_ab_test_runs_and_finds_a_real_gap():
    rep = autopilot.run("ab.csv", _ab_csv(), "does the variant raise conversion?")
    s = _by_id(rep)["ab_test"]
    assert s["status"] == "ran"
    t = s["result"]["tests"][0]
    assert t["b_rate_pct"] > t["a_rate_pct"] and "likely" in t["verdict"]


def test_no_clear_gap_is_said_plainly_with_sample_size():
    rep = autopilot.run("ab.csv", _ab_csv(800, 0.09, 0.11))
    s = _by_id(rep)["ab_test"]
    assert "No clear difference" in s["plain"] and s["result"]["sample_size_per_group"] > 800


def test_models_beat_baseline_and_leaky_column_is_removed():
    import random
    r = random.Random(2)
    rows = ["customer_id,tenure,tickets,churned,cancel_flag"]
    for i in range(300):
        t, k = r.randint(1, 60), r.randint(0, 8)
        ch = 1 if (k * 8 - t + r.randint(-15, 15)) > 5 else 0
        rows.append(f"C{i},{t},{k},{ch},{ch}")
    rep = autopilot.run("churn.csv", "\n".join(rows).encode(), "predict churned")
    s = _by_id(rep)["ml"]
    assert s["status"] == "ran" and "cancel_flag" in s["result"]["inputs_dropped"]
    assert s["result"]["leaderboard"][0]["score"] <= 0.55


def test_ml_is_skipped_without_a_clear_outcome_and_never_blocks_other_steps():
    rep = autopilot.run("orders.csv", b"region,sales\nN,10\nS,20\nN,30\nS,15\nN,12\nS,40\n")
    ids = _by_id(rep)
    assert ids["ml"]["status"] == "skipped" and ids["profile"]["status"] == "ran"
    assert rep["counts"]["failed"] == 0


def test_security_log_and_pcap_routes():
    log = b"\n".join(f"Oct 10 02:50:{i:02d} web1 sshd[5]: Failed password for root from 203.0.113.50 port 400 ssh2".encode() for i in range(30))
    log += b"\nOct 10 02:59:00 web1 sshd[9]: Accepted password for deploy from 203.0.113.50 port 401 ssh2\n"
    rep = autopilot.run("auth.log", log)
    assert rep["kind"] == "security_log" and _by_id(rep)["seclog"]["status"] == "ran"


def test_empty_and_old_excel_are_refused():
    with pytest.raises(autopilot.AutoError):
        autopilot.run("x.csv", b"   ")
    with pytest.raises(autopilot.AutoError):
        autopilot.run("x.xls", b"abc")


def test_endpoint_uploads_a_file_and_does_not_change_tables():
    before = c.get("/api/datasets").json() if c.get("/api/datasets").status_code == 200 else None
    r = c.post("/api/autopilot/run", files={"file": ("ab.csv", io.BytesIO(_ab_csv()), "text/csv")}, data={"concern": "conversion?", "field": "scientist"})
    assert r.status_code == 200 and r.json()["counts"]["ran"] >= 3 and "Nothing was saved" in r.json()["disclaimer"]
    after = c.get("/api/datasets").json() if c.get("/api/datasets").status_code == 200 else None
    assert before == after
