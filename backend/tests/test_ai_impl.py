import pytest

from app.services import ai_impl as ai, ai_vendor as av, known_errors


def test_readiness_sample_says_repair_first():
    r = ai.readiness(ai.SAMPLE["readiness"])
    assert "repair" in str(r).lower()


def test_checklist_verdicts():
    assert "Exception mapping" in ai.checklist({"outcome": True, "process": True})["verdict"] or "Exception" in ai.checklist({"outcome": True, "process": True})["verdict"]
    full = {k: True for k in ("outcome", "process", "exceptions", "readiness", "allocation")}
    c = ai.checklist(full)
    assert c["ready_for_trial"] and c["verdict"] == "Ready to start the trial."
    assert ai.checklist({**full, "trial": True, "expand": True})["verdict"].startswith("Trial done")
    with pytest.raises(ai.ImplError):
        ai.checklist({"nope": True})


def test_autonomy_uses_lower_bound_and_caps():
    few = ai.autonomy("low", "easy", False, 19, 20, 0)
    many = ai.autonomy("low", "easy", False, 950, 1000, 0)
    assert few["level"] < many["level"] or few["level"] == 1
    assert ai.autonomy("high", "easy", False, 990, 1000, 2)["level"] <= 2
    with pytest.raises(ai.ImplError):
        ai.autonomy("extreme", "easy", False, 1, 1, 0)


def test_exceptions_and_value_check():
    r = ai.exceptions(ai.SAMPLE["exceptions"])
    assert "predictable" in str(r).lower()
    v = ai.value_check(ai.SAMPLE["baseline"], ai.SAMPLE["current"], 80, 12, 95, 2000, 5000)
    assert v
    with pytest.raises(ai.ImplError):
        ai.value_check({}, {}, 120, None, None)


def test_vendor_gate_beats_total():
    for name, a in av.SAMPLE["vendors"].items():
        r = av.score(a)
        assert r["gate_failures"] and r["verdict"].startswith("Do not buy")
    a = {i: "yes" for i, *_ in av.Q}
    assert av.score(a)["verdict"].startswith("Passes") and av.score(a)["original_score"] == 25
    assert av.score({i: "yes" for i, *_ in av.Q if i[0] != "x"}, include_extra=False)["verdict"].startswith("Passes")


def test_vendor_unknown_is_not_yes_and_validation():
    a = {i: "yes" for i, *_ in av.Q}
    a["w1"] = "unknown"
    r = av.score(a)
    assert r["unknown_count"] == 1 and "unknown" in r["verdict"]
    for bad in ({"zz": "yes"}, {"n1": "maybe"}, []):
        with pytest.raises(av.VendorError):
            av.score(bad)
    assert len(av.Q) == 32 and sum(1 for q in av.Q if not q[5]) == 25


def test_vendor_compare_ranks_gate_failures_first():
    good = {i: "yes" for i, *_ in av.Q}
    bad = {**good, "s1": "no"}
    r = av.compare({"bad": bad, "good": good})
    assert r["ranking"][0]["vendor"] == "good"
    with pytest.raises(av.VendorError):
        av.compare({"only": good})


def test_endpoints(client):
    assert client.get("/api/aiimpl/reference").status_code == 200
    assert client.post("/api/aiimpl/readiness", json={"scores": ai.SAMPLE["readiness"]}).status_code == 200
    assert client.post("/api/aiimpl/autonomy", json={"error_cost": "low", "reversible": "easy", "correct": 20, "reviewed": 20}).status_code == 200
    assert client.post("/api/aiimpl/autonomy", json={"error_cost": "x", "reversible": "easy"}).status_code == 400
    assert client.post("/api/aiimpl/vendor/score", json={"answers": {"n1": "yes"}}).status_code == 200
    assert client.post("/api/aiimpl/vendor/score", json={"answers": {"zz": "yes"}}).status_code == 400
    assert client.get("/api/aiimpl/vendor/sample").status_code == 200


def test_slips_registered_for_retrieval():
    assert len(ai.SLIPS) == 7 and len(av.SLIPS) == 7
    assert "ai_impl" in known_errors.SOURCES and "ai_vendor" in known_errors.SOURCES
