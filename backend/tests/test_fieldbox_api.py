from app.services import field_howto as fh


def test_field_howto_search_scoped(client):
    s = lambda q, a="": client.get("/api/fieldbox/howto/search", params={"q": q, "area": a}).json()["results"]
    assert s("board resets when motor starts")[0]["id"] == "cpe-power"
    assert s("assistant got worse after change")[0]["id"] == "ai-eval-regress"
    assert s("client adds extra work")[0]["id"] == "pm-scope-creep"
    assert s("api has no login")[0]["id"] == "fs-no-login"
    assert all(r["area"] == "Full stack" for r in s("deploy", "Full stack"))
    assert not s("client adds extra work", "Computer engineering") or s("client adds extra work", "Computer engineering")[0]["area"] == "Computer engineering"
    assert client.get("/api/fieldbox/howto/nope").status_code == 404
    assert set(client.get("/api/fieldbox/howto").json()["areas"]) == set(fh.AREAS)
    for g in fh.GUIDES:
        assert g["steps"] and g["verify"]
    assert len({g["id"] for g in fh.GUIDES}) == len(fh.GUIDES)
    for ref, gid in fh.REF.items():
        assert fh.get(gid), ref


def test_fieldbox_flows(client):
    p = client.post("/api/fieldbox/cpe/parts", json={"board": "esp32", "parts": [{"name": "Relay", "qty": 1, "unit_cost": 3, "current_ma": 70, "pins": 1, "voltage": "5"}]})
    assert p.status_code == 200 and "status" in p.json()
    assert client.post("/api/fieldbox/cpe/parts", json={"board": "nope", "parts": []}).status_code == 400
    assert client.post("/api/fieldbox/cpe/runtime", json={"battery_mah": 2000, "active_ma": 80, "sleep_ma": 0.1, "active_s": 5, "period_s": 600}).status_code == 200
    c = client.post("/api/fieldbox/ai/cost", json={"requests_per_day": 500, "in_tokens": 800, "out_tokens": 300}).json()
    assert c
    sid = client.post("/api/fieldbox/ai/evals", json={"name": "t", "cases": [{"prompt": "hi", "checks": [{"type": "contains", "value": "hello"}]}]}).json()["id"]
    cid = client.get(f"/api/fieldbox/ai/evals/{sid}").json()["cases"][0]["id"]
    assert client.post(f"/api/fieldbox/ai/evals/{sid}/score", json={"outputs": {cid: "hello there"}}).status_code == 200
    assert client.post("/api/fieldbox/ai/risks", json={"system": "bot"}).status_code == 200
    assert client.post("/api/fieldbox/text/sets", json={"name": "tix", "labels": ["a", "b"]}).status_code == 200
    assert client.post("/api/fieldbox/text/sets/tix/examples", json={"text": "a,refund please\nb,love it"}).status_code == 200
    assert client.get("/api/fieldbox/text/sets").json()["sets"]
    ex = "\n".join(f"{l},{t}" for l, t in [("a", "refund please"), ("b", "love it"), ("a", "refund now"), ("b", "great job"), ("a", "money back"), ("b", "thanks so much")])
    client.post("/api/fieldbox/text/sets/tix/examples", json={"text": ex})
    assert client.post("/api/fieldbox/text/sets/tix/train").json()["verdict"]
    assert client.post("/api/fieldbox/text/sets/tix/classify", json={"texts": ["refund me"]}).json()["results"]
    assert client.post("/api/fieldbox/pm/estimate", json={"tasks": [{"name": "x", "optimistic": 2, "likely": 4, "pessimistic": 9}]}).status_code == 200
    assert client.post("/api/fieldbox/pm/roadmap", json={"title": "A", "lane": "now"}).status_code == 200
    assert "A" in client.get("/api/fieldbox/pm/roadmap.html").text
    assert client.post("/api/fieldbox/pm/log", json={"kind": "decision", "decision": "Use X", "context": "cheap"}).status_code == 200
    assert client.get("/api/fieldbox/pm/log.md").status_code == 200
    assert client.post("/api/fieldbox/pm/sow", json={}).status_code == 400
    s = client.post("/api/fieldbox/fs/scaffold", json={"table": "orders", "fields": [{"name": "item", "type": "text"}]})
    assert s.status_code == 200
    assert client.post("/api/fieldbox/fs/scaffold", json={"table": "x;y", "fields": [{"name": "a"}]}).status_code == 400
    assert client.post("/api/fieldbox/fs/runbook", json={"kind": "api"}).status_code == 200
    assert client.get("/api/fieldbox/experiments.csv").status_code == 200


def test_field_agent_tool(client):
    from app.services import agents
    from app.services.providers import Call, Turn
    from tests.test_math_and_shortcuts import Fake
    f = Fake([Turn("", [Call("1", "field_fix", {"action": "search", "query": "client adds extra work"})]), Turn("", [Call("2", "field_fix", {"action": "guide", "id": "pm-scope-creep"})]), Turn("Walkthrough.")])
    r = agents.chat("pm", "Client keeps adding things", adapters={"anthropic": f, "openai": f, "google": f}, provider="anthropic")
    assert "field_fix" in [t["name"] for t in f.tools] and "pm-scope-creep" in str(f.results[0]) and "verify" in str(f.results[1]) and r.reply == "Walkthrough."
    g = Fake([Turn("ok")])
    agents.chat("network", "hi", adapters={"anthropic": g, "openai": g, "google": g}, provider="anthropic")
    assert "field_fix" not in [t["name"] for t in g.tools]
