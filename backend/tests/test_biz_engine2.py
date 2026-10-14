import pytest

from app.services import biz_packs as bp


@pytest.fixture()
def c(client):
    return client


def test_job_pack_has_follow_up_dates(c):
    assert c.post("/api/biz-packs/job-search/sample").status_code == 200
    d = c.get("/api/biz-packs/job-search/dashboard?days=0").json()
    assert {k["label"] for k in d["kpis"]} >= {"Applications", "Response rate", "Interview rate", "Offers"}
    f = c.get("/api/biz-packs/job-search/form").json()
    assert [x["name"] for x in f["fields"]][-1] == "follow_up" and f["fields"][-1]["type"] == "date" and not f["fields"][-1]["required"]
    assert "Applied" in next(x for x in f["fields"] if x["name"] == "stage")["options"]


def test_quick_add_row_validates(c):
    c.post("/api/biz-packs/logi-finance/sample")
    before = bp.installed("logi-finance")
    ok = {"record_date": "2026-10-12", "platform": "Instacart", "vehicle": "Car A", "earnings": "85.50", "tips": "20", "fuel": "$12", "other_costs": 0, "miles": "64.2", "hours": "4.5"}
    r = c.post("/api/biz-packs/logi-finance/rows", json={"values": ok})
    assert r.status_code == 200 and r.json()["rows"] == before + 1
    for bad, msg in [({**ok, "platform": ""}, "can't be empty"), ({**ok, "earnings": "abc"}, "must be a number"), ({**ok, "record_date": "13/10/2026"}, "record_date"),
                     ({**ok, "earnings": "1e99"}, "normal number"), ({**ok, "platform": "x" * 81}, "too long")]:
        r = c.post("/api/biz-packs/logi-finance/rows", json={"values": bad})
        assert r.status_code == 400 and msg in r.json()["detail"], (bad, r.text)
    assert bp.installed("logi-finance") == before + 1
    # a row into an empty (not yet installed) dashboard creates the table
    c.delete("/api/biz-packs/logi-finance/data")
    assert c.post("/api/biz-packs/logi-finance/rows", json={"values": ok}).json()["rows"] == 1
    f = c.get("/api/biz-packs/logi-finance/form").json()
    assert "Instacart" in next(x for x in f["fields"] if x["name"] == "platform")["options"]


CSV = "Order Date,Region,Rep,Revenue ($),Cost,Order ID,Notes\n" + "\n".join(
    f"2026-09-{1 + i % 28:02d},{['West', 'East'][i % 2]},{['Ann', 'Bo', 'Cy'][i % 3]},{100 + i * 3},{40 + i},ID{i},free text number {i}" for i in range(40))


def test_custom_dashboard_from_csv(c):
    r = c.post("/api/biz-packs/custom", json={"name": "Sales Q3", "csv": CSV, "lower_is_better": ["Cost"]})
    assert r.status_code == 200, r.text
    j = r.json()
    pid = j["id"]
    assert j["date_column"] == "Order Date" and set(j["measures"]) == {"revenue", "cost"} and set(j["categories"]) == {"region", "rep"}
    assert any("order id" in n.lower() or "notes" in n.lower() for n in j["notes"]) or j["notes"]
    d = c.get(f"/api/biz-packs/{pid}/dashboard?days=0").json()
    labels = {k["label"]: k for k in d["kpis"]}
    assert labels["Records"]["value"] == 40 and labels["Cost (total)"]["direction"] == "lower" and labels["Revenue (total)"]["direction"] == "higher"
    assert any(p["id"] == pid and p["custom"] and not p["can_sample"] for p in c.get("/api/biz-packs").json()["packs"])
    assert c.post(f"/api/biz-packs/{pid}/sample").status_code == 400
    assert c.post(f"/api/biz-packs/{pid}/rows", json={"values": {"record_date": "2026-10-01", "region": "West", "rep": "Ann", "revenue": 500, "cost": 90}}).json()["rows"] == 41
    m = c.post(f"/api/biz-packs/{pid}/model", json={"target": "revenue"})
    assert m.status_code == 200
    assert c.delete(f"/api/biz-packs/{pid}/custom").status_code == 200
    assert not any(p["id"] == pid for p in c.get("/api/biz-packs").json()["packs"])
    assert c.delete("/api/biz-packs/job-search/custom").status_code == 400


def test_custom_errors(c):
    assert c.post("/api/biz-packs/custom", json={"name": "x", "csv": CSV}).status_code == 422
    assert c.post("/api/biz-packs/custom", json={"name": "Two cols", "csv": "a,b\n1,2\n"}).status_code == 400
    assert "date" in c.post("/api/biz-packs/custom", json={"name": "No dates", "csv": "name,qty\n" + "\n".join(f"n{i},{i}" for i in range(10))}).json()["detail"].lower()
    assert c.post("/api/biz-packs/custom", json={"name": "Bad col", "csv": CSV, "date_column": "Nope"}).status_code == 400


def test_identifiers_are_safe():
    used: set[str] = set()
    assert bp._ident("Group", used) == "c_group" and bp._ident("Revenue ($)", used) == "revenue" and bp._ident("revenue", used) == "revenue_2"
    assert bp._ident("1st; DROP TABLE x", used).startswith("c_1st")
    assert bp._ident("record_date", used) != "record_date"


def test_data_browser_search_sort_page_delete(c):
    c.post("/api/biz-packs/retail-sales/sample")
    r = c.get("/api/biz-packs/retail-sales/browse?limit=5").json()
    assert len(r["rows"]) == 5 and r["matched"] == r["total"] > 5 and r["columns"][0] == "record_date"
    s = r["columns"][1]
    word = r["rows"][0]["values"][1]
    f = c.get(f"/api/biz-packs/retail-sales/browse?q={word}&limit=200").json()
    assert 0 < f["matched"] <= r["total"] and all(word.lower() in " ".join(map(str, x["values"])).lower() for x in f["rows"])
    a = c.get(f"/api/biz-packs/retail-sales/browse?sort={s}&dir=asc&limit=2").json()["rows"]
    assert a[0]["values"][1] <= a[1]["values"][1]
    assert c.get("/api/biz-packs/retail-sales/browse?sort=evil;DROP&limit=1").status_code == 200   # unknown sort column is ignored
    d = c.delete(f"/api/biz-packs/retail-sales/rows/{r['rows'][0]['id']}").json()
    assert d["deleted"] == 1 and d["rows"] == r["total"] - 1
    assert c.get("/api/biz-packs/nope/browse").status_code == 400 or c.get("/api/biz-packs/nope/browse").status_code == 404
