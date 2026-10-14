def test_star_operations(client):
    r = client.get("/api/pipeline/star", params={"source": "operations"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["fact"].startswith("fact_") and d["measures"] and d["dimensions"]
    assert any(m["column"] == "margin" and not m["additive"] for m in d["measures"])
    assert any(x["name"] == "dim_entity" and "entity_name" in x["attributes"] for x in d["dimensions"])
    assert "entity_id" in d["grain"]
    assert not any(m["column"] in ("month", "year") for m in d["measures"])
    assert not any(x["name"] == "dim_month_name" for x in d["dimensions"])


def test_star_bad_source(client):
    assert client.get("/api/pipeline/star", params={"source": "nope"}).status_code == 400


def test_choose_store(client):
    p = lambda **k: client.post("/api/pipeline/store", json=k)
    assert p(workload="transactions").json()["recommendation"] == "operational database"
    assert p(workload="reporting").json()["recommendation"] == "data warehouse"
    assert p(data="raw").json()["recommendation"] == "data lake"
    assert p(volume="huge", workload="reporting").json()["reasons"]
    assert p(workload="x").status_code == 400


def test_metadata_view(client):
    d = client.get("/api/pipeline/metadata").json()
    assert d["technical"] and "process" in d and d["business"] and "described_pct" in d["coverage"]
    t = d["technical"][0]
    assert t["columns"] and "type" in t["columns"][0]
    first_col = t["columns"][0]["name"]
    hit = client.get("/api/pipeline/metadata", params={"search": first_col}).json()
    assert any(first_col in [c["name"] for c in x["columns"]] for x in hit["technical"])
    assert client.get("/api/pipeline/metadata", params={"search": "zzzznotacolumn"}).json()["technical"] == []
