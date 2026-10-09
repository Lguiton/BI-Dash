import pytest


def test_api_map_lists_this_apps_endpoints(client):
    d = client.get("/api/fullstack/api-map").json()
    paths = {(e["method"], e["path"]) for e in d["endpoints"]}
    assert ("GET", "/api/pm") in paths and ("PATCH", "/api/pm/items/{item_id}") in paths or any(p == "/api/pm/items/{iid}" for _, p in paths)
    assert d["total"] == len(d["endpoints"]) > 60 and sum(d["by_method"].values()) == d["total"]
    assert any(g["group"] == "fullstack" for g in d["groups"])


def test_request_tester_calls_own_api(client):
    r = client.post("/api/fullstack/request", json={"method": "GET", "path": "/api/pm"}).json()
    assert r["status"] == 200 and '"items"' in r["body"] and r["ms"] >= 0
    bad = client.post("/api/fullstack/request", json={"method": "POST", "path": "/api/pm/items", "body": {}}).json()
    assert bad["status"] in (400, 422) and "request was wrong" in bad["reading"]


@pytest.mark.parametrize("path", ["http://evil.example/x", "/etc/passwd", "/api/../etc", "/api//x", "/api/workspaces/active"])
def test_request_tester_refuses_outside_paths(client, path):
    assert client.post("/api/fullstack/request", json={"method": "GET", "path": path}).status_code == 400


def test_request_tester_is_read_only_in_real(client):
    client.post("/api/workspaces/active", json={"name": "real"})
    assert client.post("/api/fullstack/request", json={"method": "POST", "path": "/api/pm/risks", "body": {"title": "x", "probability": 0.5}}).status_code == 409
    assert client.post("/api/fullstack/request", json={"method": "GET", "path": "/api/pm"}).json()["status"] == 200
    assert client.get("/api/pm").json()["risks"]["risks"] == []     # nothing was written


def test_scaffold_generates_every_layer(client):
    t = client.get("/api/fullstack/scaffold/tables").json()["tables"]
    assert "fact_operations" in t and "app_meta" not in t
    d = client.get("/api/fullstack/scaffold", params={"table": "fact_operations"}).json()
    names = [f["name"] for f in d["files"]]
    assert d["primary_key"] == "fact_id" and any(n.endswith(".sql") for n in names) and any(n.endswith("Panel.tsx") for n in names)
    router = next(f for f in d["files"] if f["name"].startswith("backend/app/routers"))["content"]
    compile(router, "gen_router.py", "exec")            # the generated Python is valid Python
    assert "?" in router and "f\"SELECT" not in router   # values are bound parameters
    assert client.get("/api/fullstack/scaffold", params={"table": "app_meta"}).status_code == 404
    assert client.get("/api/fullstack/scaffold", params={"table": "x; DROP TABLE y"}).status_code == 404


def test_codebase_and_stack(client):
    c = client.get("/api/fullstack/codebase").json()
    assert c["tests"] > 100 and any(l["language"] == "Python" for l in c["languages"]) and c["largest"]
    s = client.get("/api/fullstack/stack").json()
    assert s["python"] and s["packages"]["duckdb"] and {f["area"] for f in s["facts"]} >= {"Authentication", "CORS allowed origins"}
    cors = next(f for f in s["facts"] if f["area"] == "CORS allowed origins")
    assert "not used" in cors["note"]


def test_company_plan_detects_progress_from_data(client):
    d = client.get("/api/company").json()
    assert [p["id"] for p in d["phases"]] == ["discover", "design", "build", "operate"]
    assert len(d["disciplines"]) == 8 and d["total"] == sum(p["total"] for p in d["phases"]) 
    # a healthy fresh database already passes its integrity checks; nothing else can be done yet
    assert [i["id"] for p in d["phases"] for i in p["deliverables"] if i["done"]] == ["dba-health"]
    assert d["next"]["id"] == "req-capture"
    client.post("/api/sysanalyst/requirements/example")
    d = client.get("/api/company").json()
    req = next(i for p in d["phases"] for i in p["deliverables"] if i["id"] == "req-capture")
    assert req["detected"] and req["done"] and "requirement" in req["detail"]
    assert d["done"] >= 1 and d["next"]["id"] != "req-capture"


def test_company_manual_ticks_brief_and_workspaces(client):
    r = client.put("/api/company/deliverables/fs-api", json={"done": True}).json()
    assert next(i for p in r["phases"] for i in p["deliverables"] if i["id"] == "fs-api")["done"]
    assert client.put("/api/company/deliverables/nope", json={"done": True}).status_code == 404
    client.put("/api/company/brief", json={"company": "Acme", "goal": "Cut report time", "notes": ""})
    assert client.get("/api/company").json()["brief"]["company"] == "Acme"
    client.post("/api/workspaces/active", json={"name": "real"})
    real = client.get("/api/company").json()                     # a separate plan: nothing carried over
    assert real["brief"]["company"] == "" and real["workspace"] == "real" and not next(i for p in real["phases"] for i in p["deliverables"] if i["id"] == "fs-api")["done"]
    assert client.put("/api/company/deliverables/fs-api", json={"done": False}).status_code == 200


def test_cors_allows_patch(client):
    r = client.options("/api/pm/items/1", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "PATCH"})
    assert r.status_code == 200 and "PATCH" in r.headers["access-control-allow-methods"]


def test_generated_router_actually_works(client):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.services.db import get_cursor
    with get_cursor() as cur:
        cur.execute('CREATE TABLE "gadgets" (id INTEGER PRIMARY KEY, name VARCHAR, price DOUBLE)')
    d = client.get("/api/fullstack/scaffold", params={"table": "gadgets"}).json()
    ns: dict = {}
    exec(next(f for f in d["files"] if f["name"].startswith("backend/app/routers"))["content"], ns)   # noqa: S102 - our own generated text
    app = FastAPI()
    app.include_router(ns["router"])
    c = TestClient(app)
    assert c.post("/api/gadgets", json={"id": 1, "name": "bolt", "price": 2.5}).status_code == 201
    assert c.get("/api/gadgets/1").json()["name"] == "bolt"
    assert c.put("/api/gadgets/1", json={"name": "nut"}).json()["name"] == "nut"
    assert c.get("/api/gadgets").json()[0]["price"] == 2.5
    assert c.get("/api/gadgets/99").status_code == 404
    # hostile column names in the body are ignored, not interpolated into SQL
    assert c.post("/api/gadgets", json={"id": 2, 'name"; DROP TABLE gadgets; --': "x"}).status_code == 201
    assert len(c.get("/api/gadgets").json()) == 2
    assert c.delete("/api/gadgets/1").json() == {"deleted": "1"}
