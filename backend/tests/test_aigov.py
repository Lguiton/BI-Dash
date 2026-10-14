import pytest

from app.services import ai_gov as g, known_errors, pylib_map as pm

ASSET = {"name": "support-bot", "kind": "agent", "owner": "Ana", "purpose": "Drafts replies", "provider": "internal", "data_class": "confidential", "pii": True,
         "actions": ["read", "send_message"], "autonomy": "act_with_approval", "human_oversight": True, "approved": True, "traced": True, "last_review": "2099-01-01"}


@pytest.fixture()
def reg(client):
    return client


def test_asset_risk_rises_with_data_actions_and_autonomy():
    low = g.assess({**g._clean({**ASSET, "name": "a", "kind": "model", "data_class": "public", "pii": False, "actions": [], "autonomy": "suggest", "last_review": "2099-01-01"})})
    high = g.assess(g._clean({**ASSET, "name": "b", "data_class": "restricted", "actions": ["write", "deploy", "delete"], "autonomy": "autonomous", "human_oversight": False}))
    assert low["tier"] == "low" and high["tier"] == "high" and high["score"] > low["score"]
    assert any("no human oversight" in i for i in high["issues"])


def test_issues_cover_owner_approval_external_review_and_tracing():
    a = g._clean({**ASSET, "owner": "", "approved": False, "provider": "external", "traced": False, "last_review": ""})
    issues = " ".join(g.assess(a)["issues"])
    for word in ("No owner", "Not approved", "external provider", "Never reviewed", "not traced"):
        assert word in issues
    old = g._clean({**ASSET, "last_review": "2000-01-01"})
    assert "days ago" in " ".join(g.assess(old)["issues"])


@pytest.mark.parametrize("bad", [{}, {"name": "x", "kind": "robot"}, {"name": "x", "kind": "agent", "data_class": "secret"}, {"name": "x", "kind": "agent", "autonomy": "wild"},
                                 {"name": "x", "kind": "agent", "actions": ["fly"]}, {"name": "x", "kind": "agent", "last_review": "yesterday"}, {"name": "x", "kind": "agent", "provider": "mars"}])
def test_clean_rejects_bad_assets(bad):
    with pytest.raises(g.GovError):
        g._clean(bad)


def test_shadow_check_logic(client):
    g.register(ASSET)
    g.register({**ASSET, "name": "old-tool", "approved": False})
    r = g.shadow_check(["Support-Bot", "mystery-agent", "OLD-TOOL"])
    assert r["shadow_ai"] == ["mystery-agent"] and r["registered_but_unapproved"] == ["old-tool"] and r["registered_not_seen"] == []
    with pytest.raises(g.GovError):
        g.shadow_check([" ", ""])


def test_registry_crud_and_duplicates_via_http(client):
    r = client.post("/api/aigov/assets", json=ASSET)
    assert r.status_code == 200 and r.json()["tier"] in ("low", "medium", "high")
    aid = r.json()["id"]
    assert client.post("/api/aigov/assets", json={**ASSET, "name": "SUPPORT-BOT"}).status_code == 409
    assert client.put(f"/api/aigov/assets/{aid}", json={**ASSET, "owner": "Ben"}).json()["owner"] == "Ben"
    assert client.put("/api/aigov/assets/nope", json=ASSET).status_code == 404
    d = client.get("/api/aigov/assets").json()
    assert d["count"] == 1 and set(d["tiers"]) == {"high", "medium", "low"}
    assert client.delete(f"/api/aigov/assets/{aid}").json() == {"deleted": aid}
    assert client.delete(f"/api/aigov/assets/{aid}").status_code == 404
    assert client.post("/api/aigov/assets", json={**ASSET, "kind": "robot"}).status_code == 400


def test_risk_tier_levels():
    assert g.risk_tier({})["tier"] == "minimal"
    assert g.risk_tier({"talks_to_people": True})["tier"] == "limited"
    assert g.risk_tier({"talks_to_people": True, "employment": True})["tier"] == "high"
    r = g.risk_tier({"employment": True, "social_scoring": True})
    assert r["tier"] == "prohibited" and "not legal advice" in r["limit"]
    with pytest.raises(g.GovError):
        g.risk_tier({"nonsense": True})


def test_policy_precedence_default_and_warnings():
    rules = "allow, *, read, *, *\ndeny, intern, read, restricted, *\napprove, agent, deploy, *, *"
    reqs = "analyst, read, internal, model\nintern, read, restricted, model\nagent, deploy, internal, agent\nagent, delete, internal, tool"
    r = g.simulate_text(rules, reqs)
    got = [x["decision"] for x in r["results"]]
    assert got == ["allow", "deny", "approve", "deny"] and r["results"][3]["rule"] == 0
    assert any("never decided" in w for w in r["warnings"]) is False
    blanket = g.simulate_text("allow, *, *, *, *\ndeny, *, delete, *, *", "x, delete, internal, tool", "allow")
    assert blanket["results"][0]["decision"] == "deny"
    assert any("allows everything" in w for w in blanket["warnings"]) and any("default is allow" in w for w in blanket["warnings"])
    for bad in ((" ", "a,b,c,d"), ("maybe, *, *, *, *", "a,b,c,d")):
        with pytest.raises(g.GovError):
            g.simulate_text(*bad)


def test_spend_totals_attribution_budgets_and_routing():
    prices = {"big": {"input": 3.0, "output": 15.0}, "small": {"input": 0.25, "output": 1.25}}
    csvt = "user,team,app,model,input_tokens,output_tokens,task\na,t1,x,big,1000000,100000,simple\nb,t2,y,small,1000000,0,complex\n"
    r = g.spend(csvt, prices, {"t1": 4, "t2": 10}, "small")
    assert r["total_cost"] == pytest.approx(3 + 1.5 + 0.25) and r["calls"] == 2
    assert r["by_team"][0]["team"] == "t1" and r["by_team"][0]["share_pct"] == pytest.approx(100 * 4.5 / 4.75, abs=0.1)
    t1 = next(b for b in r["budgets"] if b["team"] == "t1")
    assert t1["status"] == "blocked" and next(b for b in r["budgets"] if b["team"] == "t2")["status"] == "ok"
    assert r["routing_what_if"]["simple_calls_moved"] == 1 and r["routing_what_if"]["estimated_saving"] == pytest.approx(4.5 - 0.375)
    assert "test" in r["routing_what_if"]["caveat"]


def test_spend_flags_outlier_and_rejects_bad_input():
    s = g.sample()
    import json
    r = g.spend(s["usage"], json.loads(s["prices"]))
    assert r["outliers"] and r["outliers"][0]["user"] == "gus"
    p = {"big-model": {"input": 1, "output": 1}}
    for bad in ("user,team\nx,y", "user,team,app,model,input_tokens,output_tokens\na,b,c,big-model,x,1", "user,team,app,model,input_tokens,output_tokens\na,b,c,other,1,1",
                "user,team,app,model,input_tokens,output_tokens\na,b,c,big-model,-1,1"):
        with pytest.raises(g.GovError):
            g.spend(bad, p)
    with pytest.raises(g.GovError):
        g.spend(s["usage"], {"big-model": {"input": "x"}, "small-model": {"input": 1, "output": 1}})


def test_reference_and_slips_registered():
    ref = g.reference()
    assert len(ref["crosswalk"]) >= 8 and any("NIST AI Risk" in x or "EU AI Act" in x for x in ref["gaps_in_the_book"])
    text = " ".join(i["text"] for i in known_errors.all_items())
    assert "vendor material" in text and "Django, Flask, Kivy" in text
    assert any("vendor" in i["text"] for i in known_errors.relevant("ai", "is the vendor governance book claim of 30% lower cost true"))


def test_governance_endpoints(client):
    s = client.get("/api/aigov/sample").json()
    assert client.post("/api/aigov/spend", json={"usage": s["usage"], "prices": __import__("json").loads(s["prices"]), "cheap_model": "small-model"}).json()["routing_what_if"]
    assert client.post("/api/aigov/spend", json={"usage": "bad", "prices": {"a": {"input": 1, "output": 1}}}).status_code == 400
    assert client.post("/api/aigov/policy", json={"rules": s["rules"], "requests": s["requests"]}).json()["tally"]
    assert client.post("/api/aigov/risk-tier", json={"answers": {"credit": True}}).json()["tier"] == "high"
    assert client.post("/api/aigov/risk-tier", json={"answers": {"zzz": True}}).status_code == 400
    assert client.post("/api/aigov/shadow", json={"names": ["x"]}).json()["shadow_ai"] == ["x"]
    assert client.get("/api/aigov/reference").json()["themes"]


# ---------------------------------------------------------------- python libraries
def test_library_list_has_19_with_install_commands():
    d = pm.libraries()
    assert d["total"] == 19 and len(d["libraries"]) == 19 and all(r["install"].startswith("pip install ") and r["docs"].startswith("https://") for r in d["libraries"])
    assert {"spaCy", "Pydantic"} <= {x["name"] for x in d["also_worth_knowing"]}


def test_missing_library_gives_pip_command_not_an_error(monkeypatch):
    monkeypatch.setattr(pm.importlib.util, "find_spec", lambda name: None)
    r = pm.demo("pandas")
    assert r["status"] == "missing" and r["install"] == "pip install pandas"
    assert "run" in pm.demo("streamlit")["note"].lower()


def test_demo_unknown_key(client):
    assert client.post("/api/pylib/nope/demo").status_code == 404


@pytest.mark.parametrize("key", ["pandas", "numpy", "sklearn", "fastapi", "matplotlib"])
def test_core_demos_run_offline(key):
    r = pm.demo(key)
    assert r["status"] == "ok" and r["output"]


def test_demo_outputs_are_correct():
    assert "column means [3.0, 4.0, 5.0]" in pm.demo("numpy")["output"]
    assert "200 {'hello': 'ada'}" in pm.demo("fastapi")["output"]
    out = pm.demo("pandas")["output"]
    assert "a" in out and "90" in out and "60" in out


@pytest.mark.parametrize("key,needle", [("bs4", "first -> /a"), ("nltk", "'the': 2"), ("boto3", "no request was made"), ("cv2", "edge pixels")])
def test_optional_demos_when_installed(key, needle):
    r = pm.demo(key)
    if r["status"] == "missing":
        pytest.skip(f"{key} not installed")
    assert r["status"] == "ok" and needle in r["output"]


def test_failing_demo_is_reported_not_raised(monkeypatch):
    monkeypatch.setitem(pm.DEMOS, "numpy", lambda: 1 / 0)
    r = pm.demo("numpy")
    assert r["status"] == "failed" and "ZeroDivisionError" in r["note"]


def test_pylib_endpoints(client):
    d = client.get("/api/pylib").json()
    assert d["total"] == 19 and d["slips"]
    assert client.post("/api/pylib/numpy/demo").json()["status"] == "ok"
