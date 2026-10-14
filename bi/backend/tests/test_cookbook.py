import pytest

from app.services import cookbook as cb


def test_every_recipe_runs_on_the_sample():
    for r in cb.RECIPES:
        out = cb._run(r["sql"])
        assert out["columns"], r["id"]
    assert len(cb.RECIPES) == 13


def test_all_50_interview_answers_run():
    assert [q["n"] for q in cb.INTERVIEW] == list(range(1, 51))
    for q in cb.INTERVIEW:
        out = cb._run(q["sql"])
        assert out["columns"], q["n"]


def test_known_answers():
    r = lambda n: cb._run(next(q for q in cb.INTERVIEW if q["n"] == n)["sql"])["rows"]
    assert r(2) == [[95000]] or r(2)[0][0] == 95000  # second highest distinct (99000 is the top)
    assert r(3) == [[82000]]   # 3rd distinct: 99000, 95000, 82000
    assert r(25) == [["Lee"]]
    assert r(26) == [[3], [4]] and r(27) == [[1], [2]]
    assert [x[0] for x in r(48)] == [3, 6]
    assert {x[0]: x[1] for x in r(49)} == {"level": True, "radar": True, "sql": False}
    assert len(r(45)) == 5
    assert len(r(13)) == 6


def test_g_flag_matters():
    only_first = cb._run("SELECT regexp_replace('a-b-c','[^a-z]','') AS x")["rows"][0][0]
    assert only_first == "ab-c"   # without 'g' only the first match goes: the recipes pass 'g'
    d = cb._run(next(r for r in cb.RECIPES if r["id"] == "phone_digits")["sql"])["rows"]
    assert all(x[1] is None or x[1].isdigit() for x in d)


def test_endpoints(client):
    c = client.get("/api/cookbook").json()
    assert len(c["interview"]) == 50 and len(c["sites"]) == 8 and c["pandas"][-1]["items"][-1]["code"].startswith("pd.concat")
    r = client.post("/api/cookbook/run", json={"kind": "interview", "id": "17"})
    assert r.status_code == 200 and r.json()["result"]["row_count"] >= 1
    assert client.post("/api/cookbook/run", json={"kind": "recipe", "id": "special_chars"}).json()["after"]["rows"]
    assert client.post("/api/cookbook/run", json={"kind": "recipe", "id": "nope"}).status_code == 400
    assert client.get("/api/cookbook/sample/users").status_code == 404
    assert client.get("/api/cookbook/sample/orders").status_code == 200


def test_new_clean_steps(client):
    from app.services import cleaning, datasets
    csv = b"id,phone,full_name,city\n1,(555) 123-4567,Ann Lee,Nwe York\n2,555.987.6543,Bob Van Dyke,NYC\n3,+1 555 222,Cy,Boston\n"
    datasets.import_file(csv, "cb_messy.csv", "cb_messy")
    t = datasets.table_name_for("cb_messy")
    res = cleaning.clean(t, "cb_messy_clean", [
        {"op": "strip_chars", "column": "phone", "keep": "digits"},
        {"op": "split_text", "column": "full_name", "delimiter": "space", "names": ["first", "last"]},
        {"op": "replace_text", "column": "city", "find": "Nwe York", "with": "New York"}])
    assert res["rows_after"] == 3
    from app.services.db import get_cursor
    with get_cursor() as cur:
        rows = cur.execute("SELECT phone, first, last, city FROM cb_messy_clean ORDER BY id").fetchall()
    assert rows[0] == ("5551234567", "Ann", "Lee", "New York")
    assert rows[1][0] == "5559876543" and rows[1][2] == "Van Dyke"
    assert rows[2][1] == "Cy" and rows[2][2] is None
    with pytest.raises(datasets.DataError):
        cleaning.clean(t, "cb_x", [{"op": "strip_chars", "column": "phone", "keep": "bogus"}])
