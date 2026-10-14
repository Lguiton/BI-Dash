import pytest

from app.services import known_errors, ml_build as mb
from app.services.ml_tools import MlToolError


def test_numeric_and_label_drift():
    d = mb.drift(**mb.DRIFT_SAMPLE)
    assert d["verdict"] == "investigate" and d["psi"] > 0.25 and d["ks_p_value"] < 0.001 and len(d["bins"]) >= 5
    same = mb.drift(mb.DRIFT_SAMPLE["reference"], mb.DRIFT_SAMPLE["reference"])
    assert same["psi"] == 0 and same["verdict"] == "no clear drift"
    lab = mb.drift("a,a,a,a,b,b,a,a,a,a", "a,b,b,b,b,b,a,b,b,b", "labels")
    assert lab["verdict"] == "investigate" and {c["label"] for c in lab["categories"]} == {"a", "b"}
    for bad in (("1 2", "3 4 5 6 7"), ("a b c d e", "1 2 3 4 5"), ("5 5 5 5 5 5", "1 2 3 4 5")):
        with pytest.raises(MlToolError):
            mb.drift(*bad)
    with pytest.raises(MlToolError):
        mb.drift("1 2 3 4 5", "1 2 3 4 5", "bogus")


def test_performance_drift():
    p = mb.perf_drift(mb.PERF_SAMPLE)
    assert p["flagged"] == ["Apr", "May"] and p["baseline_accuracy_pct"] == 92.0
    assert p["periods"][1]["flag"] == "" and p["periods"][0]["drop_p_value"] is None
    for bad in ("a, 5, 10\nb, 6, 10", "a,1,1\nb,x,5\nc,1,2", "a,5,3\nb,1,2\nc,1,2"):
        with pytest.raises(MlToolError):
            mb.perf_drift(bad)


def test_automl_ignores_ids_and_warns():
    r = mb.automl(mb._auto_sample(), "target")
    assert r["task"] == "classification" and set(r["selected_features"]) >= {"a", "b"} and "noise_id" in r["ignored_columns"]
    assert r["models"][0]["cv_mean"] > r["baseline"]["cv_mean"] + 0.2 and any("optimistic" in w for w in r["warnings"])
    leaky = mb._auto_sample().replace("target", "y").splitlines()
    rows = ["a,b,c,noise_id,y,copy"] + [f"{l},{l.split(',')[-1]}" for l in leaky[1:]]
    r2 = mb.automl("\n".join(rows), "y")
    assert r2["models"][0]["cv_mean"] > 0.97 and any("suspicious" in w for w in r2["warnings"])
    with pytest.raises(MlToolError):
        mb.automl("a,b\n1,2", "zzz")
    with pytest.raises(MlToolError):
        mb.automl("a,b\n1,2\n3,4", "b")


def test_network_learns_xor_only_with_a_hidden_layer():
    deep = mb.nn_train("xor", "8", "tanh", 0.1, 400)
    flat = mb.nn_train("xor", "", "tanh", 0.1, 400)
    assert deep["test_accuracy_pct"] >= 80 and flat["test_accuracy_pct"] <= 65
    assert deep["loss_curve"][-1]["loss"] < deep["loss_curve"][0]["loss"] and len(deep["boundary_grid"]) == 24
    assert mb.nn_train("xor", "8", "tanh", 0.1, 100) == mb.nn_train("xor", "8", "tanh", 0.1, 100)
    for bad in ({"hidden": "99"}, {"activation": "x"}, {"data": "nope"}, {"lr": 100}):
        with pytest.raises(MlToolError):
            mb.nn_train(**bad)


def test_gradient_check_and_attention():
    g = mb.grad_check()
    assert g["ok"] and all(c["difference"] < 1e-6 for c in g["checks"])
    a = mb.attention("the cat sat on the mat", causal=True)
    assert a["rows_sum_to_one"] and a["weights"][0][0] == 1.0 and a["weights"][0][1] == 0.0
    assert not mb.attention("a b c", causal=False)["causal"]
    with pytest.raises(MlToolError):
        mb.attention("one")


def test_bpe_and_lsa():
    b = mb.bpe(mb.BPE_SAMPLE, 10, "lowest")
    assert b["merges"][0]["count"] >= b["merges"][-1]["count"] >= 2
    assert "".join(b["encoded"][0]["tokens"]).replace("</w>", "") == "lowest" and b["vocab_size"] > b["base_symbols"]
    with pytest.raises(MlToolError):
        mb.bpe("short", 5)
    r = mb.lsa(**mb.LSA_SAMPLE)
    assert r["results"][0]["doc"] in (1, 5) and 5 in r["found_only_by_concepts"]
    with pytest.raises(MlToolError):
        mb.lsa("a b\nc d\ne f", "zzz")
    with pytest.raises(MlToolError):
        mb.lsa("a\nb", "a")


def test_endpoints_and_sources(client):
    ref = client.get("/api/mlbuild/reference").json()
    assert set(ref["samples"]) == {"drift", "perf", "automl", "bpe", "lsa", "attention"}
    assert client.post("/api/mlbuild/drift", json={**ref["samples"]["drift"], "kind": "numeric"}).json()["verdict"] == "investigate"
    assert client.post("/api/mlbuild/neural-net", json={"data": "line", "hidden": "4"}).status_code == 200
    assert client.post("/api/mlbuild/neural-net", json={"hidden": "x"}).status_code == 400
    assert client.get("/api/mlbuild/gradient-check").json()["ok"]
    assert "ml_build" in known_errors.SOURCES and len(mb.SLIPS) == 5
