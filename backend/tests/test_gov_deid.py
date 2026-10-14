def _mk(client):
    from app.services import datasets
    from app.services.db import get_cursor
    datasets.ensure_registry()
    with get_cursor() as cur:
        cur.execute("CREATE OR REPLACE TABLE people AS SELECT * FROM (VALUES ('Ann Lee','ann@x.com',34,DATE '2020-03-05'),('Bob Ray','bob@x.com',51,DATE '2015-07-01'),('Ann Lee','ann@x.com',29,CURRENT_DATE - 10)) t(name,email,age,joined)")
        cur.execute("DELETE FROM user_tables WHERE table_name = 'people'")
        cur.execute("INSERT INTO user_tables VALUES ('people', 'people', 'test', 3, '[]', now(), now())")


def test_deidentify_copy(client):
    _mk(client)
    r = client.post("/api/governance/deidentify", json={"table": "people", "new_table": "people_safe", "columns": {"name": "pseudonym", "email": "mask", "age": "generalize", "joined": "generalize"}})
    assert r.status_code == 200, r.text
    from app.services.db import get_cursor
    with get_cursor() as cur:
        rows = cur.execute("SELECT name, email, age, joined FROM people_safe ORDER BY age").fetchall()
        orig = cur.execute("SELECT COUNT(*) FROM people WHERE email = 'ann@x.com'").fetchone()[0]
    assert orig == 2  # original untouched
    assert all(r[0].startswith("P-") for r in rows)
    names = [r[0] for r in rows]
    assert len(set(names)) == 2  # the two Ann rows share one pseudonym
    assert all(r[1].startswith("*") and r[1].endswith("om") for r in rows)
    assert all(r[2] % 10 == 0 for r in rows)
    assert all(r[3].month == 1 and r[3].day == 1 for r in rows)


def test_deidentify_validation(client):
    _mk(client)
    assert client.post("/api/governance/deidentify", json={"table": "people", "new_table": "x", "columns": {"nope": "mask"}}).status_code == 404
    assert client.post("/api/governance/deidentify", json={"table": "people", "new_table": "x", "columns": {"name": "bad"}}).status_code == 400
    assert client.post("/api/governance/deidentify", json={"table": "people", "new_table": "people", "columns": {"name": "mask"}}).status_code == 400
    assert client.post("/api/governance/deidentify", json={"table": "people", "new_table": "", "columns": {"name": "mask"}}).status_code == 400


def test_purge_expired(client):
    _mk(client)
    assert client.post("/api/governance/purge", json={"name": "people"}).status_code == 400  # no retention rule yet
    r = client.put("/api/governance/assets/people", json={"retention_days": 365, "retention_column": "joined"})
    assert r.status_code == 200, r.text
    dry = client.post("/api/governance/purge", json={"name": "people"}).json()
    assert dry["eligible_rows"] == 2 and dry["deleted"] == 0
    done = client.post("/api/governance/purge", json={"name": "people", "confirm": True}).json()
    assert done["deleted"] == 2
    from app.services.db import get_cursor
    with get_cursor() as cur:
        assert cur.execute("SELECT COUNT(*) FROM people").fetchone()[0] == 1
