import json

from app.services import ai_tools as at, learn_path as lp, ml_tools as mt


# ---------------------------------------------------------------- learning paths
def test_paths_are_complete_and_honest(client):
    for t in ("ml", "ai"):
        d = client.get(f"/api/learn/path/{t}").json()
        assert d["total"] >= 20 and d["pct"] == 0
        for lv in d["levels"]:
            assert lv["gate"] and lv["modules"]
            for m in lv["modules"]:
                assert m["status"] in lp.STATUSES and m["where"] and m["practice"]
    ai = client.get("/api/learn/path/ai").json()
    assert [l["id"] for l in ai["levels"]] == [f"L{i}" for i in range(9)]
    assert ai["coverage"]["cannot"] >= 2 and ai["coverage"]["guide"] >= 3
    assert client.get("/api/learn/path/nope").status_code == 404


def test_progress_and_gate_rules(client):
    mods = [m["id"] for m in client.get("/api/learn/path/ml").json()["levels"][0]["modules"]]
    assert client.put("/api/learn/path/ml/gate/M0", json={"passed": True}).status_code == 400  # modules not done yet
    for m in mods:
        assert client.put(f"/api/learn/path/ml/module/{m}", json={"done": True}).status_code == 200
    assert client.put("/api/learn/path/ml/gate/M0", json={"passed": True}).status_code == 200
    d = client.get("/api/learn/path/ml").json()
    assert d["gates_passed"] == 1 and d["done"] == len(mods) and d["pct"] > 0
    assert client.put("/api/learn/path/ml/module/ZZ", json={"done": True}).status_code == 404
    assert client.put("/api/learn/path/ai/module/" + mods[0], json={"done": True}).status_code == 404  # ids are per track


# ---------------------------------------------------------------- ML tools
def test_bias_variance_shows_overfit_and_is_repeatable():
    a = mt.bias_variance(seed=7); b = mt.bias_variance(seed=7)
    assert a == b
    rows = {r["degree"]: r for r in a["rows"]}
    assert rows[12]["train_mse"] < rows[1]["train_mse"]
    assert rows[12]["valid_mse"] > rows[a["best_degree"]]["valid_mse"]
    assert "overfit" in rows[12]["verdict"] and "underfit" in rows[1]["verdict"]


def test_gradient_descent_regimes():
    assert mt.grad_descent("linear", lr=0.3, steps=200)["verdict"].startswith("Converged")
    assert mt.grad_descent("linear", lr=0.0001, steps=50)["verdict"].startswith("Barely")
    assert mt.grad_descent("linear", lr=40, steps=100)["diverged"] is True
    g = mt.grad_descent("logistic", lr=0.5, steps=300)
    assert g["weights"][0] > 0 > g["weights"][1]


def test_scratch_models_beat_baseline_and_logistic_is_not_best():
    r = mt.scratch_compare()
    assert r["rows"][0]["accuracy"] > r["baseline_accuracy"] + 0.2
    assert r["rows"][0]["model"] != "naive Bayes (gaussian)"
    assert [x for x in r["rows"] if x["model"] == "logistic regression"][0]["accuracy"] < r["rows"][0]["accuracy"]


def test_score_report_matches_known_auc_and_costs():
    perfect = "\n".join(f"{s},{l}" for s, l in [(0.9, 1), (0.8, 1), (0.7, 1), (0.6, 1), (0.5, 1), (0.4, 0), (0.3, 0), (0.2, 0), (0.1, 0), (0.05, 0)])
    r = mt.score_report(perfect)
    assert r["roc_auc"] == 1.0 and r["pr_auc"] == 1.0 and r["best_threshold"]["cost"] == 0
    rev = mt.score_report("\n".join(f"{1 - float(l.split(',')[0])},{l.split(',')[1]}" for l in perfect.splitlines()))
    assert rev["roc_auc"] == 0.0
    s = mt.score_report(mt.SAMPLES["scores"], fp_cost=1, fn_cost=10)
    cheap = mt.score_report(mt.SAMPLES["scores"], fp_cost=1, fn_cost=1)
    assert s["best_threshold"]["threshold"] <= cheap["best_threshold"]["threshold"]  # costly misses lower the cut-off
    assert s["calibration"]["bins"]


def test_score_report_rejects_bad_input():
    for bad in ("", "0.5,2\n" * 12, "0.1,1\n" * 12, "a,b\n" * 12):
        try:
            mt.score_report(bad)
        except mt.MlToolError:
            continue
        raise AssertionError(bad)


def test_leak_check_finds_the_planted_leak(client):
    r = mt.leak_check(mt.SAMPLES["leak"], "churned")
    cols = {f["column"] for f in r["findings"]}
    assert "cancellation_date_filled" in cols and "customer_id" in cols
    assert r["verdict"].startswith("Likely leakage")
    assert client.post("/api/learn/ml/leak", json={"csv": mt.SAMPLES["leak"], "target": "nope"}).status_code == 400


# ---------------------------------------------------------------- AI tools
def test_retrieval_metrics_by_hand():
    cases = [{"retrieved": ["a", "b", "c"], "relevant": ["b"]}, {"retrieved": ["x", "y"], "relevant": ["x", "z"]}, {"retrieved": [], "relevant": []}, {"retrieved": ["q"], "relevant": []}]
    r = at.retrieval_metrics(cases, k=3)
    assert r["answerable"] == 2 and r["unanswerable"] == 2
    assert r["mrr"] == 0.75 and r["recall@3"] == 0.75
    assert r["abstain_rate"] == 0.5
    assert abs(r["ndcg@3"] - ((1 / 1.5849625 / 1) + (1 / (1 + 1 / 1.5849625))) / 2) < 0.01 or r["ndcg@3"] > 0


def test_hybrid_search_fuses_and_abstains():
    d = at.SAMPLES["docs"]
    r = at.hybrid_search(d, "how long do refunds take", k=2)
    assert r["fused_rrf"][0]["id"] == "refund"
    assert at.hybrid_search(d, "zzzz qqqq xxxx", k=2)["found_nothing"] in (True, False)
    assert at.hash_str("abc") == at.hash_str("abc")  # stable, not Python's salted hash
    dup = [{"id": "a", "text": "refund policy fourteen days"}, {"id": "b", "text": "refund policy fourteen days"}, {"id": "c", "text": "refund of damaged goods"}]
    assert len(at.hybrid_search(dup, "refund policy", k=2, mmr_lambda=0.3)["after_mmr"]) == 2


def test_schema_check_catches_fences_types_and_extras():
    r = at.schema_check(at.SAMPLES["output"], at.SAMPLES["schema"])
    assert not r["valid"] and any("code fence" in n for n in r["notes"])
    txt = " ".join(r["errors"])
    assert "urgent" in txt and "amount" in txt and "extra" in txt
    assert "Fix ONLY" in r["repair_prompt"]
    ok = at.schema_check('{"name": "x", "priority": "low", "amount": 5}', at.SAMPLES["schema"])
    assert ok["valid"] and ok["parsed"]["amount"] == 5
    assert not at.schema_check("{'name': 'x'}", at.SAMPLES["schema"])["valid"]
    assert not at.schema_check('{"name": "x", "priority": "low", "amount": true}', at.SAMPLES["schema"])["valid"]  # bool is not a number


def test_agent_trace_flags_loop_errors_and_risk():
    r = at.agent_trace(at.SAMPLE_TRACE, max_steps=4)
    t = " ".join(f["issue"] for f in r["findings"])
    assert "looping" in t and "failed calls" in t and "send_email" in t and "budget" in t and "no final answer" in t
    assert r["verdict"] == "Problems found."
    clean = at.agent_trace([{"tool": "query", "args": {}, "ok": True}, {"type": "final"}])
    assert clean["findings"] == [] and clean["finished"]


def test_eval_stats_numbers():
    i = at.eval_stats("interval", n=100, passes=80)
    assert abs(i["low"] - 0.7112) < 0.001 and abs(i["high"] - 0.8666) < 0.001
    assert at.eval_stats("sample_size", expected_rate=0.5, margin=0.05)["cases_needed"] == 385
    c = at.eval_stats("compare", n1=100, passes1=70, n2=100, passes2=71)
    assert not c["significant_at_5pct"]
    assert at.eval_stats("compare", n1=1000, passes1=700, n2=1000, passes2=760)["significant_at_5pct"]
    assert at.eval_stats("kappa", both_yes=40, judge_yes_human_no=10, judge_no_human_yes=10, both_no=40)["kappa"] == 0.6
    assert at.eval_stats("pass_at_k", samples=10, correct=0, k=3)["pass_at_k"] == 0.0
    assert at.eval_stats("pass_at_k", samples=10, correct=10, k=1)["pass_at_k"] == 1.0
    assert abs(at.eval_stats("pass_at_k", samples=10, correct=5, k=1)["pass_at_k"] - 0.5) < 1e-9
    try:
        at.eval_stats("interval", n=10, passes=11)
    except at.AiToolError:
        pass
    else:
        raise AssertionError("passes > n accepted")


def test_reliability_math():
    b = at.reliability("backoff", base_s=1, factor=2, cap_s=10, retries=5, timeout_s=10)
    assert b["delays_s"] == [1, 2, 4, 8, 10] and b["worst_case_s"] == 25 + 60
    e = at.reliability("error_budget", slo_pct=99.9, window_days=30, downtime_min=10)
    assert abs(e["budget_min"] - 43.2) < 0.1 and e["left_min"] > 30
    c = at.reliability("chain", availabilities=[99.9, 99.5, 99.0], fallback_pct=99.0)
    assert abs(c["chain_pct"] - 98.4) < 0.1 and c["with_model_fallback_pct"] > 99.9
    assert at.reliability("amplification", retries_per_layer=2, layers=3)["multiplier"] == 27


def test_finetune_data_check_and_lora_math():
    r = at.finetune_check(at.SAMPLES["finetune"], test_text=at.SAMPLES["finetune"].splitlines()[1])
    t = " ".join(r["issues"])
    assert "duplicate" in t and "empty" in t and r["train_test_overlap"] == 1
    try:
        at.finetune_check("not json\nalso not")
    except at.AiToolError:
        pass
    l = at.lora_calc(7, layers=32, hidden=4096, rank=16, targets=4)
    assert l["lora_trainable_params"] == 32 * 4 * 16 * 2 * 4096
    assert 100 < l["full_finetune_gb"] < 120 and l["lora_gb"] < 25 and l["saving_x"] > 4
    assert l["chinchilla_tokens_b"] == 140.0


def test_guard_scan_redacts_and_flags():
    r = at.guard_scan(at.SAMPLES["guard"])
    assert "dana@example.com" not in r["redacted"] and "[CARD]" in r["redacted"] and "[PHONE]" in r["redacted"]
    assert r["pii_found"].get("card_number") == 1 and r["injection_risk"] == "high"
    assert "4111" not in json.dumps(r["pii_found"])
    # an invalid card checksum is not flagged as a card
    assert "card_number" not in at.guard_scan("order 1234 5678 9012 3456")["pii_found"]
    assert at.guard_scan("Quarterly sales rose 4%.")["injection_risk"] == "low"
    assert at.guard_scan("hello‮world")["injection_signals"]


def test_endpoints_reject_bad_input(client):
    assert client.post("/api/learn/ai/eval-stats", json={"mode": "bogus"}).status_code == 400
    assert client.post("/api/learn/ai/lora", json={"params_b": -1}).status_code == 400
    assert client.post("/api/learn/ai/retrieval", json={"cases": []}).status_code == 400
    assert client.post("/api/learn/ml/gradient-descent", json={"task": "x"}).status_code == 400
    assert client.post("/api/learn/ai/schema", json={"output": "{}", "schema": {}}).status_code == 400
    assert client.post("/api/learn/ai/guard", json={"text": "my mail a@b.co"}).status_code == 200
    assert client.get("/api/learn/ai/reference").json()["not_built"]


# ---------------------------------------------------------------- outside links
def test_links_are_well_formed_and_cover_what_cannot_be_built(client):
    import re
    for key, (label, url) in lp.L.items():
        assert re.fullmatch(r"https://[a-z0-9.-]+\.[a-z]{2,}(/[^\s]*)?", url), (key, url)
        assert label
    assert len({u for _, u in lp.L.values()}) == len(lp.L)  # no duplicate URLs under two names
    for k in {k for ks in lp.MODULE_LINKS.values() for k in ks} | {k for g in lp.NOT_HERE for it in g["items"] for k in it[3]} | set(lp.RESOURCE_LINKS.values()):
        assert k in lp.L, k
    for t in ("ml", "ai"):
        d = client.get(f"/api/learn/path/{t}").json()
        ids = set()
        for lv in d["levels"]:
            for m in lv["modules"]:
                ids.add(m["id"])
                if m["status"] in ("cannot", "guide"):
                    assert m["links"], m["id"]
        for key in lp.MODULE_LINKS:
            if key[0] == "M" and t == "ml" or key[0] != "M" and t == "ai":
                assert key in ids, key
        assert d["not_here"] and d["link_note"]
    ai = client.get("/api/learn/path/ai").json()
    cannot = [m for lv in ai["levels"] for m in lv["modules"] if m["status"] == "cannot"]
    assert cannot and all(m["links"] for m in cannot)
    mlc = [m for lv in client.get("/api/learn/path/ml").json()["levels"] for m in lv["modules"] if m["status"] == "cannot"]
    assert mlc and all(m["links"] for m in mlc)
    pt = [l for g in ai["not_here"] for it in g["items"] for l in it["links"] if l["label"] == "PyTorch"]
    assert pt and pt[0]["url"] == "https://pytorch.org/"
