from app.services import biz_packs, data_howto as hw


def test_howto_search_and_refs(client):
    r = client.get("/api/toolbox/howto/search", params={"q": "totals doubled after join"}).json()["results"]
    assert r and r[0]["id"] == "an-join-explosion"
    assert client.get("/api/toolbox/howto/search", params={"q": "model no better than baseline"}).json()["results"][0]["id"] == "ds-no-better"
    assert client.get("/api/toolbox/howto/search", params={"q": "column renamed broke report"}).json()["results"][0]["id"] == "de-schema-drift"
    assert client.get("/api/toolbox/howto/nope").status_code == 404
    assert client.get("/api/toolbox/howto-ref/join_explosion").json()["id"] == "an-join-explosion"
    g = client.get("/api/toolbox/howto/de-contract-fail").json()
    assert g["steps"] and g["verify"]
    ar = client.get("/api/toolbox/howto").json()["areas"]
    assert set(ar) == {"Data Analyst", "BI", "Data Science", "Data Engineering"}
    for ref, gid in hw.REF.items():
        assert hw.get(gid), ref


def test_api_flow(client):
    biz_packs.install_sample("repair-jobs")
    cols = client.get("/api/toolbox/analyst/columns", params={"source": "repair-jobs"}).json()["columns"]
    assert cols
    assert client.post("/api/toolbox/analyst/query", json={"source": "repair-jobs", "metric": "count"}).json()["rows"]
    assert client.post("/api/toolbox/analyst/query", json={"source": "repair-jobs", "metric": "bogus"}).status_code == 400
    assert client.post("/api/toolbox/analyst/ab", json={"a_success": 120, "a_n": 1000, "b_success": 150, "b_n": 1000}).json()["p_value"] < 0.06
    n = client.post("/api/toolbox/analyst/notebook", json={"title": "T", "finding": "ok"}).json()
    assert "T" in client.get(f"/api/toolbox/analyst/notebook/{n['id']}/html").text
    h = client.post("/api/toolbox/bi/design", json={"pack": "repair-jobs", "title": "Rep"})
    assert h.status_code == 200 and "Rep" in h.text
    s = client.post("/api/toolbox/bi/schedules", json={"pack": "repair-jobs", "every_days": 7}).json()
    assert client.post(f"/api/toolbox/bi/schedules/{s['id']}/run").json()["ran"] == [s["id"]]
    assert client.get("/api/toolbox/bi/dictionary", params={"fmt": "csv"}).text.startswith("dashboard")
    assert client.get("/api/toolbox/bi/alerts").json()["rules"] == []
    assert client.post("/api/toolbox/de/estimate", json={"rows_per_day": 5000}).json()["tier"] == "laptop"
    assert client.post("/api/toolbox/de/estimate", json={"rows_per_day": 0}).status_code == 400
    assert client.post("/api/toolbox/de/snapshot", json={"source": "repair-jobs"}).json()["columns"] > 3
    assert client.post("/api/toolbox/de/schema-check", json={"source": "repair-jobs"}).json()["status"] == "ok"
    assert client.get("/api/toolbox/de/contract/propose", params={"source": "repair-jobs"}).json()["columns"]


def test_data_agent_tool(client):
    from app.services import agents
    from app.services.providers import Call, Turn
    from tests.test_math_and_shortcuts import Fake
    f = Fake([Turn("", [Call("1", "data_fix", {"action": "search", "query": "join doubled totals"})]), Turn("", [Call("2", "data_fix", {"action": "guide", "id": "an-join-explosion"})]), Turn("Steps ready.")])
    r = agents.chat("analyst", "My totals doubled after a join", adapters={"anthropic": f, "openai": f, "google": f}, provider="anthropic")
    assert "data_fix" in [t["name"] for t in f.tools] and "an-join-explosion" in str(f.results[0]) and "verify" in str(f.results[1]) and r.reply == "Steps ready."
    g = Fake([Turn("ok")])
    agents.chat("security", "hi", adapters={"anthropic": g, "openai": g, "google": g}, provider="anthropic")
    assert "data_fix" not in [t["name"] for t in g.tools]


def test_scripts_api_and_agent(client):
    k = client.get("/api/toolbox/scripts/kinds").json()
    assert "backup" in k["kinds"] and "duckdb" in k["dialects"]
    r = client.post("/api/toolbox/scripts", json={"kind": "create_table", "params": {"dialect": "postgres", "table": "orders", "columns": [{"name": "id", "type": "integer", "primary": True}]}}).json()
    assert "CREATE TABLE" in r["code"] and r["ran"] is False
    assert client.post("/api/toolbox/scripts", json={"kind": "create_table", "params": {"dialect": "postgres", "table": "x;y", "columns": [{"name": "id"}]}}).status_code == 400
    assert client.post("/api/toolbox/scripts/check", json={"text": "DROP TABLE a;"}).json()["safety"]
    from app.services import agents
    from app.services.providers import Call, Turn
    from tests.test_math_and_shortcuts import Fake
    f = Fake([Turn("", [Call("1", "make_script", {"kind": "schedule", "params": {"shell": "bash", "script_path": "/b.sh"}})]), Turn("Here it is.")])
    agents.chat("engineering", "schedule my backup", adapters={"anthropic": f, "openai": f, "google": f}, provider="anthropic")
    assert "make_script" in [t["name"] for t in f.tools] and "crontab" in str(f.results[0])
    g = Fake([Turn("ok")])
    agents.chat("analyst", "hi", adapters={"anthropic": g, "openai": g, "google": g}, provider="anthropic")
    assert "make_script" not in [t["name"] for t in g.tools]
