from app.services import it_drills as d


def test_every_kind_is_gradable_with_its_own_answer(client):
    for k in d.KINDS:
        qs = client.get(f"/api/itdrills?kind={k}&n=12&seed=5").json()["questions"]
        assert len(qs) == 12 and all(q["kind"] == k for q in qs)
        ans = {q["id"]: d._build(q["id"])["answer"] for q in qs}
        g = client.post("/api/itdrills/grade", json={"answers": ans}).json()
        assert g["right"] == 12, (k, [r for r in g["results"] if not r["ok"]][:2])


def test_questions_are_deterministic_and_do_not_leak(client):
    a = client.get("/api/itdrills?kind=bin2dec&n=3&seed=9").json()["questions"]
    b = client.get("/api/itdrills?kind=bin2dec&n=3&seed=9").json()["questions"]
    assert a == b and all("answer" not in q and "why" not in q for q in a)
    assert len({q["id"] for q in client.get("/api/itdrills?n=30&seed=2").json()["questions"]}) == 30


def test_answer_normalisation():
    assert d._norm_eq("bin", "0101 0111", "01010111") and d._norm_eq("bin", "1010111", "01010111") and not d._norm_eq("bin", "0101012", "01010111")
    assert d._norm_eq("hex", "0xff", "FF") and d._norm_eq("hex", "ff", "FF") and not d._norm_eq("hex", "zz", "FF")
    assert d._norm_eq("sym", "rwxr-xr--", "rwxr-xr--") and d._norm_eq("sym", "-rwxr-xr--", "rwxr-xr--") and not d._norm_eq("sym", "rwxr-xr-x", "rwxr-xr--")
    assert d._norm_eq("oct", "0644", "644") and not d._norm_eq("oct", "4", "400")
    assert d._norm_eq("yn", "Yes", "yes") and not d._norm_eq("yn", "no", "yes")
    assert d._norm_eq("num", "932", "931") and not d._norm_eq("num", "940", "931")
    assert d._norm_eq("int", "87", "87") and not d._norm_eq("int", "x", "87")


def test_wrong_answers_progress_and_errors(client):
    client.delete("/api/itdrills/results")
    qs = client.get("/api/itdrills?kind=gate&n=4&seed=3").json()["questions"]
    g = client.post("/api/itdrills/grade", json={"answers": {q["id"]: "7" for q in qs}}).json()
    assert g["right"] == 0 and g["weak"] == ["Logic gates"] and all(r["why"] and r["answer"] for r in g["results"])
    p = {r["kind"]: r for r in client.get("/api/itdrills/progress").json()["rows"]}
    assert p["gate"]["answered"] == 4 and p["gate"]["pct"] == 0 and p["umask"]["pct"] is None
    assert client.post("/api/itdrills/grade", json={"answers": {"nope:1": "x"}}).status_code == 404
    assert client.post("/api/itdrills/grade", json={"answers": {}}).status_code == 400
    assert client.get("/api/itdrills?kind=zzz").status_code == 404
    client.delete("/api/itdrills/results")
    assert all(r["answered"] == 0 for r in client.get("/api/itdrills/progress").json()["rows"])
