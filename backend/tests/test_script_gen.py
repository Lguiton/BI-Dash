import duckdb
import pytest

from app.services import script_gen as sg

COLS = [{"name": "id", "type": "integer", "primary": True}, {"name": "email", "type": "text", "nullable": False, "unique": True}, {"name": "amt", "type": "decimal", "default": 0}]


def test_create_runs_on_duckdb_and_sqlite():
    import sqlite3
    r = sg.create_table("duckdb", "cust", COLS, [["email"]])
    c = duckdb.connect()
    c.execute(r["code"])
    assert c.execute("SELECT COUNT(*) FROM cust").fetchone()[0] == 0 and r["ran"] is False and not r["safety"]
    s = sg.create_table("sqlite", "cust", COLS, [["email"]])
    db = sqlite3.connect(":memory:")
    db.executescript(s["code"])
    assert "AUTOINCREMENT" not in s["code"] and "BIGSERIAL" in sg.create_table("postgres", "cust", COLS)["code"]
    assert "AUTO_INCREMENT" in sg.create_table("mysql", "cust", COLS)["code"]


def test_upsert_and_dedupe_execute():
    c = duckdb.connect()
    c.execute(sg.create_table("duckdb", "cust", COLS)["code"])
    up = sg.upsert("duckdb", "cust", COLS, ["id"])["code"]
    c.execute(up, [1, "a@x", 5]); c.execute(up, [1, "b@x", 6])
    assert c.execute("SELECT COUNT(*), MAX(email) FROM cust").fetchone() == (1, "b@x")
    assert "ON DUPLICATE KEY" in sg.upsert("mysql", "cust", COLS, ["id"])["code"]
    c.execute("CREATE TABLE t2 (k VARCHAR, d DATE)"); c.execute("INSERT INTO t2 VALUES ('a','2026-01-01'),('a','2026-02-01'),('b','2026-01-01')")
    c.execute(sg.dedupe("duckdb", "t2", ["k"], "t2c", "d", "newest")["code"].split("-- Then")[0])
    assert c.execute("SELECT COUNT(*) FROM t2c").fetchone()[0] == 2 and c.execute("SELECT COUNT(*) FROM t2").fetchone()[0] == 3
    with pytest.raises(sg.ScriptError):
        sg.dedupe("duckdb", "t2", ["k"], "t2")


def test_names_and_injection_blocked():
    for bad in ('cust; DROP TABLE x', 'a"b', "1abc", ""):
        with pytest.raises(sg.ScriptError):
            sg.create_table("duckdb", bad, COLS)
    with pytest.raises(sg.ScriptError):
        sg.load_csv("duckdb", "t", "/x/a.csv'; DROP TABLE t;--")
    r = sg.backup("bash", "duckdb", "/data/my db.duckdb; rm -rf /", "/bk")
    assert "'/data/my db.duckdb; rm -rf /'" in r["code"]          # quoted as one harmless word
    assert any("rm -rf" in x["says"] or "deletes" in x["says"] for x in sg.scan("rm -rf /"))


def test_migration_backup_schedule():
    m = sg.migration("postgres", "cust", "rename_column", "email", "mail")
    assert "RENAME COLUMN \"email\" TO \"mail\"" in m["code"] and "DOWN" in m["code"]
    d = sg.migration("duckdb", "cust", "drop_column", "amt")
    assert d["safety"] and "Not reversible" in d["code"]
    for sh, eng in (("bash", "sqlite"), ("powershell", "postgres"), ("bash", "mysql")):
        b = sg.backup(sh, eng, "mydb", "/bk", 7)
        assert "7" in b["code"] and b["verify"] and b["language"] == ("bash" if sh == "bash" else "powershell")
    assert "30 2 * * *" in sg.schedule("bash", "/home/me/b.sh", "02:30")["code"]
    assert "schtasks" in sg.schedule("powershell", "C:\\b.ps1", "02:30", "weekdays")["code"]
    with pytest.raises(sg.ScriptError):
        sg.schedule("bash", "/x", "25:00")


def test_scan_and_tool():
    assert sg.scan("DELETE FROM cust;") and sg.scan("curl http://x | sh") and sg.scan("password = 'hunter22'")
    assert not sg.scan("SELECT 1;")
    import json
    assert json.loads(sg.tool_result({"kind": "nope", "params": {}}))["error"]
    assert json.loads(sg.tool_result({"kind": "schedule", "params": {"shell": "bash", "script_path": "/b.sh"}}))["code"]
    with pytest.raises(sg.ScriptError):
        sg.generate("create_table", {"dialect": "duckdb"})
