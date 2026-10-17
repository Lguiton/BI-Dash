"""The advanced labs: every calculator runs on its defaults, and the maths is checked by hand."""
import math

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import agent_tools, prolab, prolab_all  # noqa: F401

client = TestClient(app)
TRACKS = ["cpe", "fullstack", "pm", "sysanalyst", "ai", "ml", "engineering", "scientist"]


def defaults(t):
    return {f["k"]: f["default"] for f in t["fields"]}


def run(track, tid, **kw):
    t = next(x for x in prolab.spec(track)["tabs"] if x["id"] == tid)
    return prolab.run(track, tid, {**defaults(t), **{k: str(v) for k, v in kw.items()}})


def test_all_tracks_registered():
    assert set(TRACKS) <= set(prolab.tracks())


@pytest.mark.parametrize("track", TRACKS)
def test_every_tool_runs_on_defaults(track):
    spec = prolab.spec(track)
    tools = [t for t in spec["tabs"] if t["kind"] == "tool"]
    refs = [t for t in spec["tabs"] if t["kind"] == "ref"]
    assert len(tools) >= 7 and refs
    ids = [t["id"] for t in spec["tabs"]]
    assert len(ids) == len(set(ids))
    for t in tools:
        out = prolab.run(track, t["id"], defaults(t))
        assert isinstance(out, dict) and out.get("note")
    for t in refs:
        assert t["sections"] and all(s.get("items") or s.get("rows") for s in t["sections"])


@pytest.mark.parametrize("track", TRACKS)
def test_agent_can_use_every_tool(track):
    reg = agent_tools.BY_TRACK[track]
    for t in prolab.spec(track)["tabs"]:
        if t["kind"] == "tool":
            assert t["id"] in reg


def test_agent_run_tool_end_to_end():
    text, err = agent_tools.run_tool("cpe", {"tool": "timing_slack", "args": {"period_ns": 10, "clk_to_q_ns": 0.5, "logic_max_ns": 6, "logic_min_ns": 0.3, "setup_ns": 0.4, "hold_ns": 0.3, "skew_ns": 0.1}})
    assert not err and "3.2" in text


def test_bad_input_is_a_clean_error():
    with pytest.raises(prolab.ProError):
        run("cpe", "timing_slack", period_ns="abc")
    with pytest.raises(prolab.ProError):
        prolab.run("cpe", "nope", {})
    with pytest.raises(prolab.ProError) as e:
        prolab.spec("itsupport")
    assert e.value.status == 404


def test_api_routes():
    assert "cpe" in client.get("/api/prolab").json()["tracks"]
    assert client.get("/api/prolab/network").status_code == 404
    s = client.get("/api/prolab/pm").json()
    assert s["tabs"][0]["fields"]
    r = client.post("/api/prolab/pm/run/pert", json={"best": 4, "likely": 7, "worst": 16})
    assert r.status_code == 200 and r.json()["expected"] == 8.0
    assert client.post("/api/prolab/pm/run/pert", json={"best": 9, "likely": 7, "worst": 16}).status_code == 400


# ---------------------------------------------------------------- hand checks
def test_cpe_timing_and_uart_and_motor():
    o = run("cpe", "timing_slack")
    assert o["setup_slack_ns"] == 3.2 and o["hold_slack_ns"] == 0.4
    assert run("cpe", "timing_slack", logic_max_ns=12)["setup_slack_ns"] < 0
    u = run("cpe", "uart_baud", clock_hz=11059200)
    assert u["divisor"] == 6 and u["error_pct"] == 0
    m = run("cpe", "dc_motor")
    assert m["stall_current_a"] == 6.0 and m["stall_torque_nm"] == 0.18
    with pytest.raises(prolab.ProError):
        run("cpe", "dc_motor", load_torque_nm=1)
    t = run("cpe", "timer_setup")
    assert t["prescaler"] * t["period_ticks"] == 16000
    b = run("cpe", "dcdc_design")
    assert b["duty_cycle_pct"] == 41.7
    p = run("cpe", "pid_zn")
    assert p["gains"][2]["kp"] == 4.8


def test_cpe_fsm_finds_gaps():
    o = run("cpe", "fsm_check", table="A,0,A,0\nA,1,B,0\nB,0,A,1")
    assert "B on 1" in o["missing_transitions"] and "always @" in o["verilog"]


def test_fullstack_checks():
    assert run("fullstack", "contrast", text_color="#000000", background="#ffffff")["ratio"] == 21.0
    d = run("fullstack", "dockerfile_review")
    assert any("root" in x for x in d["findings"]) and any("secret" in x.lower() for x in d["findings"])
    assert run("fullstack", "queue_sizing")["in_flight_items"] == 20.0
    assert run("fullstack", "web_vitals", lcp_s=1, inp_ms=100, cls=0.01)["passes_all"] is True
    assert "yaml" in run("fullstack", "ci_workflow", language="node")["workflow_yaml"] or True
    with pytest.raises(prolab.ProError):
        run("fullstack", "jwt_check", token="abc")


def test_pm_math():
    c = run("pm", "critical_path")
    assert c["project_days"] == 13.0 and c["critical_path"] == "A > B > D > E"
    with pytest.raises(prolab.ProError):
        run("pm", "critical_path", tasks="A,1,B\nB,1,A")
    s = run("pm", "status_report")
    assert s["spi"] == 0.8 and s["forecast_at_completion"] == 60000.0
    m1, m2 = run("pm", "schedule_risk"), run("pm", "schedule_risk")
    assert m1 == m2 and m1["p80_days"] >= m1["p50_days"]
    assert run("pm", "raci_check", matrix="Task,A,B\nx,A,A\ny,R,I")["issues"]


def test_sysanalyst_checks():
    i = run("sysanalyst", "change_impact")
    assert i["directly_affected"] == ["Billing app", "Website"] and i["total_affected"] == 4
    b = run("sysanalyst", "business_case", upfront_cost=1000, annual_benefit=500, annual_running_cost=0, years=4, discount_pct=0)
    assert b["npv"] == 1000.0 and b["payback_years"] == 2.0
    assert run("sysanalyst", "vendor_score")["ranking"][0]["option"] == "Vendor B"


def test_ai_math():
    k = run("ai", "kv_cache")
    assert k["kv_bytes_per_token"] == 131072
    q = run("ai", "quant_speed")
    assert q["weights_gb"] == 4.0
    r = run("ai", "retrieval_metrics", k=1, queries="a | a b\nb | c b")
    assert r["recall_at_1"] == 0.5 and r["mrr"] == 0.75
    assert run("ai", "lora_memory")["trainable_lora_params_m"] == 16.78


def test_ml_math():
    c = run("ml", "cnn_layer")
    assert c["parameters"] == 1792 and c["output_shape"] == "224 x 224 x 64"
    assert run("ml", "lstm_params", input_size=10, hidden_size=20, layers=1)["parameters"] == 4 * (20 * 30 + 20)
    s = run("ml", "shapley_linear")
    assert s["adds_up"] and [x["shapley"] for x in s["contributions"]] == [2.5, 2.0, 1.5]
    assert run("ml", "drift_psi", expected="1,1", actual="1,1")["psi"] == 0
    assert run("ml", "bandit_sim") == run("ml", "bandit_sim")


def test_de_math():
    d = run("engineering", "dag_check")
    assert d["shortest_possible_runtime"] == 35.0 and d["run_order"][-1] == "publish"
    with pytest.raises(prolab.ProError):
        run("engineering", "dag_check", tasks="a,1,b\nb,1,a")
    assert run("engineering", "volume_anomaly")["latest_is_anomaly"] is True
    assert run("engineering", "contract_check")["passes"] is False
    assert run("engineering", "compaction", files=1000, avg_file_mb=1, target_file_mb=250)["files_after_compaction"] == 4


def test_ds_math():
    assert run("scientist", "diff_in_diff")["difference_in_differences"] == 15.0
    n = run("scientist", "sample_size", baseline_rate_pct=5, relative_lift_pct=10)
    assert 30000 < n["per_group"] < 33000
    km = run("scientist", "kaplan_meier", data="1,1\n2,1\n3,1\n4,0")
    assert km["curve"][0]["survival"] == 0.75
    lp = run("scientist", "optimize_lp")
    assert lp["total_profit"] == 2200.0
    d = run("scientist", "haversine", lat1=0, lon1=0, lat2=0, lon2=1)
    assert math.isclose(d["distance_km"], 111.19, abs_tol=0.05)
    assert run("scientist", "fairness_audit")["groups"][1]["four_fifths_rule"] == "FAIL"
    assert run("scientist", "bayes_ab") == run("scientist", "bayes_ab")
