import pytest

from app.services import biz_packs as packs


@pytest.fixture()
def c(client):
    return client


def test_catalog_has_industries_and_departments():
    ps = packs.CATALOG
    assert len({p["industry"] for p in ps}) >= 5 and len({p["dept"] for p in ps}) >= 5
    assert len({p["id"] for p in ps}) == len(ps)


@pytest.mark.parametrize("pid", [p["id"] for p in packs.CATALOG])
def test_every_pack_loads_and_computes(c, pid):
    assert c.post(f"/api/biz-packs/{pid}/sample").status_code == 200
    d = c.get(f"/api/biz-packs/{pid}/dashboard?days=30").json()
    assert d["records"] > 0 and d["trend"] and d["breakdowns"]
    assert all(k["value"] is not None for k in d["kpis"]), d["kpis"]
    d0 = c.get(f"/api/biz-packs/{pid}/dashboard?days=0").json()
    assert d0["records"] >= d["records"]


def test_import_roundtrip_and_errors(c):
    pid = "logi-finance"
    t = c.get(f"/api/biz-packs/{pid}/template.csv").text
    r = c.post(f"/api/biz-packs/{pid}/import", json={"csv": t, "replace": True}).json()
    assert r["imported"] == 3 and r["rows"] == 3
    bad = c.post(f"/api/biz-packs/{pid}/import", json={"csv": "a,b\n1,2\n"})
    assert bad.status_code == 400 and "Missing columns" in bad.json()["detail"]
    lines = t.splitlines()
    junk = "\n".join([lines[0], lines[1].replace(lines[1].split(",")[0], "notadate")])
    assert c.post(f"/api/biz-packs/{pid}/import", json={"csv": junk}).status_code == 400
    net = c.get(f"/api/biz-packs/{pid}/dashboard?days=0").json()["kpis"]
    assert {k["label"] for k in net} >= {"Net", "Net per hour", "Net per mile"}


def test_unknown_pack_and_empty(c):
    assert c.get("/api/biz-packs/nope/dashboard").status_code == 404
    c.delete("/api/biz-packs/prof-hr/data")
    assert c.get("/api/biz-packs/prof-hr/dashboard").status_code == 400


def test_no_change_shown_when_previous_window_is_partial(c):
    c.post("/api/biz-packs/retail-sales/sample")  # sample spans ~120 days
    k90 = c.get("/api/biz-packs/retail-sales/dashboard?days=90").json()["kpis"]
    assert all(x["change_pct"] is None for x in k90)
    k30 = c.get("/api/biz-packs/retail-sales/dashboard?days=30").json()["kpis"]
    assert all(x["change_pct"] is not None for x in k30)


def test_overview_rolls_up_everything(c):
    assert c.post("/api/biz-packs/samples").json()["installed"] == len(packs.CATALOG)
    o = c.get("/api/biz-packs/overview?days=30").json()
    assert o["packs"] == len(packs.CATALOG) == len(o["cards"])
    assert o["improving"] + o["worsening"] > 0
    assert all(a["change_pct"] is not None and abs(a["change_pct"]) >= 10 for a in o["attention"])
    c.delete("/api/biz-packs/prof-hr/data")
    assert c.get("/api/biz-packs/overview").json()["packs"] == len(packs.CATALOG) - 1


def test_samples_refused_in_real_workspace(c, monkeypatch):
    from app.services import workspaces
    monkeypatch.setattr(workspaces, "active", lambda: "real")
    r = c.post("/api/biz-packs/retail-sales/sample")
    assert r.status_code == 400 and "Practice" in r.json()["detail"]
    assert c.post("/api/biz-packs/samples").status_code == 400


def test_repair_packs_work_end_to_end(client):
    for pid in ("repair-jobs", "repair-parts"):
        assert client.post(f"/api/biz-packs/{pid}/sample").status_code == 200
        d = client.get(f"/api/biz-packs/{pid}/dashboard").json()
        assert d["records"] > 100 and all(k["value"] is not None for k in d["kpis"])
    assert {p["industry"] for p in client.get("/api/biz-packs").json()["packs"]} >= {"Repair and IT services"}
    f = client.get("/api/biz-packs/repair-jobs/form").json()["fields"]
    assert {"device_type", "fault", "price", "follow_up"} <= {x["name"] for x in f}
    assert client.get("/api/biz-packs/repair-jobs/assistant").json()["role"] == "Repair and Service Analyst"


def test_explain_this_number(client):
    client.post("/api/biz-packs/repair-jobs/sample")
    d = client.get("/api/biz-packs/repair-jobs/dashboard?days=30").json()
    k = d["kpis"][0]["label"]
    r = client.get("/api/biz-packs/repair-jobs/explain", params={"kpi": k, "days": 30})
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["value"] == d["kpis"][0]["value"] and e["formula"] and e["in_words"] and e["summary"].startswith(k)
    assert e["best_day"]["v"] >= e["worst_day"]["v"]
    assert client.get("/api/biz-packs/repair-jobs/explain", params={"kpi": "nope"}).status_code == 400
