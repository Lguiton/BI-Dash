from app.services import it_software


def test_catalog_has_ten_categories_and_known_values(client):
    c = client.get("/api/it/software").json()
    assert len(c["categories"]) == 10
    ids = [x["id"] for x in c["categories"]]
    assert {"rmm", "mdm", "patch", "asset", "desk", "remote", "backup", "netmon", "edr"} <= set(ids)
    patch = next(x for x in c["categories"] if x["id"] == "patch")
    top = patch["products"][0]
    assert top["name"] == "Action1" and top["g2_overall"] == 4.9 and top["change"] == 2
    ivanti = patch["products"][-1]
    assert ivanti["name"] == "Ivanti UEM" and ivanti["cap_overall"] is None
    assert "NinjaOne" in c["source"] and any("NinjaOne" in n for n in c["notes"])


def test_every_row_is_complete_and_in_range():
    maxes = {k: v[1] for k, v in it_software.METRICS.items()}
    for cid, cat in it_software.CATS.items():
        for r in cat["rows"]:
            assert len(r) == 11, (cid, r[0])
            for k, v in zip(it_software._KEYS, r[3:]):
                assert v is None or 0 <= v <= maxes[k], (cid, r[0], k)


def test_shortlist_weights_missing_and_exclude(client):
    r = client.post("/api/it/software/shortlist", json={"category": "patch"}).json()
    assert r["rows"][0]["position"] == 1 and r["rows"][0]["score"] >= r["rows"][-1]["score"]
    ivanti = next(x for x in r["rows"] if x["name"] == "Ivanti UEM")
    assert ivanti["weight_covered_pct"] < 100 and ivanti["missing"]
    only_setup = client.post("/api/it/software/shortlist", json={"category": "desk", "weights": {"g2_setup": 5}}).json()
    assert only_setup["rows"][0]["name"] == "Splashtop SOS" or only_setup["rows"][0]["score"] >= 9.4
    ex = client.post("/api/it/software/shortlist", json={"category": "desk", "exclude": ["splashtop sos"]}).json()
    assert all(x["name"] != "Splashtop SOS" for x in ex["rows"])
    assert only_setup["caution"]


def test_shortlist_errors(client):
    assert client.post("/api/it/software/shortlist", json={"category": "nope"}).status_code == 400
    assert client.post("/api/it/software/shortlist", json={"category": "edr", "weights": {"bogus": 1}}).status_code == 400
    assert client.post("/api/it/software/shortlist", json={"category": "edr", "weights": {"g2_use": 0}}).status_code == 400
    assert client.post("/api/it/software/shortlist", json={"category": "edr", "weights": {"g2_use": 99}}).status_code == 400


def test_stack_save_and_gaps(client):
    s = client.get("/api/it/software/stack").json()
    assert len(s["gaps"]) == len(s["rows"]) and s["have"] == 0
    r = client.put("/api/it/software/stack", json={"items": [{"id": "backup", "tool": "restic", "status": "have", "note": "weekly"}, {"id": "mdm", "status": "not_needed"}]})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["have"] == 1 and "Cloud backup" not in j["gaps"] and "Mobile device management" not in j["gaps"]
    assert client.get("/api/it/software/stack").json()["have"] == 1
    assert client.put("/api/it/software/stack", json={"items": [{"id": "zzz", "status": "have"}]}).status_code == 400
    assert client.put("/api/it/software/stack", json={"items": [{"id": "edr", "status": "maybe"}]}).status_code == 400
