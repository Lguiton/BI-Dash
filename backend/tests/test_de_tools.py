import pytest

from app.services import de_tools as de, datasets
from app.services.db import get_cursor


def _mk(name, ddl, rows):
    with get_cursor() as cur:
        cur.execute(f"CREATE OR REPLACE TABLE {name} {ddl}")
        cur.executemany(f"INSERT INTO {name} VALUES ({','.join('?' for _ in rows[0])})", rows)
    datasets.ensure_registry()
    with get_cursor() as cur:
        cur.execute("DELETE FROM user_tables WHERE table_name=?", [name])
        cur.execute("INSERT INTO user_tables VALUES (?,?,?,?,?,now(),now())", [name, name, "upload", len(rows), "[]"])


@pytest.fixture()
def tbls(client):
    _mk("cust", "(id INTEGER, email VARCHAR, amt DOUBLE, seen DATE)", [(1, "A@x.com", 10.0, "2026-01-01"), (2, "a@x.com ", 12.0, "2026-02-01"), (3, "b@x.com", 5.0, "2026-01-05"), (4, "c@x.com", 7.0, "2026-01-06")])
    _mk("orders", "(email VARCHAR, total DOUBLE)", [("b@x.com", 1.0), ("b@x.com", 2.0), ("c@x.com", 3.0)])
    return "cust"


def test_schema_changes(tbls):
    assert de.schema_check("cust")["status"] == "no_baseline"
    de.snapshot("cust")
    assert de.schema_check("cust")["status"] == "ok"
    with get_cursor() as cur:
        cur.execute("ALTER TABLE cust RENAME COLUMN email TO email_address")
        cur.execute("ALTER TABLE cust ADD COLUMN extra VARCHAR")
        cur.execute("ALTER TABLE cust ALTER amt TYPE VARCHAR")
    r = de.schema_check("cust")
    kinds = {c["kind"] for c in r["changes"]}
    assert r["status"] == "breaking" and {"renamed", "new", "type_changed"} <= kinds
    assert next(c for c in r["changes"] if c["kind"] == "renamed")["to"] == "email_address"
    assert de.schema_check("cust", accept=True)["accepted"]["columns"] == 5
    assert de.schema_check("cust")["status"] == "ok"


def test_dedupe_undo(tbls):
    p = de.dedupe_preview("cust", ["email"])
    assert p["duplicate_groups"] == 1 and p["rows_to_remove"] == 1
    with pytest.raises(de.DeError):
        de.dedupe_apply("cust", ["email"], "cust")
    r = de.dedupe_apply("cust", ["email"], "cust_clean", "newest", "seen")
    with get_cursor() as cur:
        assert cur.execute("SELECT COUNT(*) FROM cust").fetchone()[0] == 4
        assert cur.execute("SELECT id FROM cust_clean WHERE lower(trim(email))='a@x.com'").fetchone()[0] == 2
    assert r["removed"] == 1 and de.made_tables()[0]["table"] == "cust_clean"
    with pytest.raises(de.DeError):
        de.undo("cust")
    de.undo("cust_clean")
    with get_cursor() as cur:
        assert cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='cust_clean'").fetchone()[0] == 0
    with pytest.raises(de.DeError):
        de.dedupe_apply("cust", ["email"], "orders")      # never overwrite someone else's table


def test_merge_explosion(tbls):
    p = de.merge_preview("cust", "orders", "email", "email")
    assert p["explosion"] and p["result_rows"] == 5
    with pytest.raises(de.DeError):
        de.merge_apply("cust", "orders", "email", "email", "joined")
    r = de.merge_apply("cust", "orders", "email", "email", "joined", allow_multiply=True)
    assert r["rows"] == 5
    de.undo("joined")


def test_contract(tbls):
    pr = de.contract_propose("cust")
    assert any(c["name"] == "id" and c.get("unique") for c in pr["columns"])
    de.contract_save("cust", pr["columns"], owner="me")
    assert de.contract_check("cust")["status"] == "pass"
    with get_cursor() as cur:
        cur.execute("INSERT INTO cust VALUES (1, NULL, 999, '2026-03-01')")
    r = de.contract_check("cust")
    rules = {(i["column"], i["rule"]) for i in r["issues"]}
    assert r["status"] == "fail" and ("id", "unique") in rules and ("amt", "range") in rules and ("email", "not_blank") in rules
    assert de.contract_check_all()[0]["status"] == "fail"
    assert "| id |" in de.contract_markdown("cust")
    with pytest.raises(de.DeError):
        de.contract_save("cust", [])


def test_estimate():
    s = de.estimate(1000, 10)
    assert s["tier"] == "laptop" and s["storage_db_gb"] < 1
    b = de.estimate(5_000_000, 40, ram_gb=8)
    assert b["tier"] in ("database", "warehouse") and b["notes"]
    with pytest.raises(de.DeError):
        de.estimate(0)
