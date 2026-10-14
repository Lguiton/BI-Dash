from app.services import datasets
from app.services.db import get_cursor


def _tbl(name, select):
    datasets.ensure_registry()
    with get_cursor() as cur:
        cur.execute(f"CREATE OR REPLACE TABLE {name} AS {select}")
        cur.execute("DELETE FROM user_tables WHERE table_name = ?", [name])
        cur.execute("INSERT INTO user_tables VALUES (?, ?, 'test', 1, '[]', now(), now())", [name, name])


def _rows(sql):
    with get_cursor() as cur:
        return cur.execute(sql).fetchall()


def _snapshots():
    _tbl("users_old", "SELECT * FROM (VALUES (123,'Isabel','Monterrey'),(124,'Raul','Oaxaca'),(125,'Mercedes','Guadalajara')) t(id,name,city)")
    _tbl("users_new", "SELECT * FROM (VALUES (124,'Raul','Oaxaca'),(125,'Mercedes','Tijuana'),(126,'Lily','Cancun')) t(id,name,city)")


def test_snapshot_diff_counts_and_feed(client):
    _snapshots()
    r = client.post("/api/pipeline/cdc/diff", json={"old": "users_old", "new": "users_new", "key": ["id"], "create_feed": "user_changes"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["inserted"], d["updated"], d["deleted"], d["unchanged"]) == (1, 1, 1, 1)
    assert d["changed_by_column"] == {"city": 1} and d["feed_rows"] == 3
    ops = dict(_rows("SELECT id, _op FROM user_changes"))
    assert ops == {126: "INSERT", 125: "UPDATE", 123: "DELETE"}
    assert _rows("SELECT COUNT(*) FROM users_old")[0][0] == 3  # inputs untouched


def test_diff_rejects_duplicate_keys_and_bad_columns(client):
    _snapshots()
    _tbl("dups", "SELECT * FROM (VALUES (1,'a'),(1,'b')) t(id,name)")
    assert client.post("/api/pipeline/cdc/diff", json={"old": "dups", "new": "dups", "key": ["id"]}).status_code == 400
    assert client.post("/api/pipeline/cdc/diff", json={"old": "users_old", "new": "users_new", "key": ["nope"]}).status_code == 400
    assert client.post("/api/pipeline/cdc/diff", json={"old": "users_old", "new": "users_new", "key": []}).status_code == 400
    assert client.post("/api/pipeline/cdc/diff", json={"old": "users_old", "new": "missing", "key": ["id"]}).status_code == 404


def _feed():
    # the documented example: user 123 inserted then updated then deleted; 125 updated twice, the later one arriving FIRST
    _tbl("feed", """SELECT * FROM (VALUES
        (123,'Isabel','Monterrey','INSERT',1),(124,'Raul','Oaxaca','INSERT',1),(125,'Mercedes','Tijuana','INSERT',1),
        (125,'Mercedes','Mexicali','UPDATE',6),(125,'Mercedes','Guadalajara','UPDATE',5),
        (123,'Isabel','Chihuahua','UPDATE',5),(123,NULL,NULL,'DELETE',6),(126,'Lily','Cancun','insert',2)) t(id,name,city,op,seq)""")


def test_apply_scd1_latest_wins_deletes_and_late_events(client):
    _feed()
    r = client.post("/api/pipeline/cdc/apply", json={"feed": "feed", "key": ["id"], "op_col": "op", "seq_col": "seq", "mode": "scd1", "new_table": "users_now"})
    assert r.status_code == 200, r.text
    assert r.json()["out_of_order_events"] == 1 and r.json()["rows"] == 3
    assert dict((i, c) for i, n, c in _rows("SELECT id, name, city FROM users_now")) == {124: "Oaxaca", 125: "Mexicali", 126: "Cancun"}


def test_apply_scd2_history_windows(client):
    _feed()
    r = client.post("/api/pipeline/cdc/apply", json={"feed": "feed", "key": ["id"], "op_col": "op", "seq_col": "seq", "mode": "scd2", "new_table": "users_hist"})
    assert r.status_code == 200, r.text
    rows = _rows("SELECT id, city, __start_at, __end_at, is_current FROM users_hist ORDER BY id, __start_at")
    isabel = [(c, s, e, cur) for i, c, s, e, cur in rows if i == 123]
    assert isabel == [("Monterrey", 1, 5, False), ("Chihuahua", 5, 6, False)]   # the delete at 6 closes her last version
    m = [(c, s, e, cur) for i, c, s, e, cur in rows if i == 125]
    assert m == [("Tijuana", 1, 5, False), ("Guadalajara", 5, 6, False), ("Mexicali", 6, None, True)]
    assert sum(1 for r in rows if r[4]) == 3   # 124, 125, 126 are current; 123 is not


def test_apply_validation(client):
    _feed()
    p = lambda **k: client.post("/api/pipeline/cdc/apply", json={"feed": "feed", "key": ["id"], "op_col": "op", "seq_col": "seq", "mode": "scd1", "new_table": "o", **k})
    assert p(mode="scd3").status_code == 400
    assert p(op_col="nope").status_code == 400
    assert p(seq_col="op").status_code == 400
    assert p(new_table="feed").status_code == 400
    _tbl("badops", "SELECT * FROM (VALUES (1,'x','merge',1)) t(id,name,op,seq)")
    assert p(feed="badops").status_code == 400
    _tbl("dupseq", "SELECT * FROM (VALUES (1,'x','insert',1),(1,'y','update',1)) t(id,name,op,seq)")
    assert p(feed="dupseq").status_code == 400


def test_snapshot_feed_round_trips_into_new_snapshot(client):
    _snapshots()
    client.post("/api/pipeline/cdc/diff", json={"old": "users_old", "new": "users_new", "key": ["id"], "create_feed": "f2"})
    # applying the diff feed on top of old rows plus the feed should reproduce the new snapshot
    _tbl("merged_feed", "SELECT id,name,city,'INSERT' AS _op,0 AS _seq FROM users_old UNION ALL SELECT id,name,city,_op,_seq FROM f2")
    r = client.post("/api/pipeline/cdc/apply", json={"feed": "merged_feed", "key": ["id"], "op_col": "_op", "seq_col": "_seq", "mode": "scd1", "new_table": "rebuilt"})
    assert r.status_code == 200, r.text
    assert sorted(_rows("SELECT id, name, city FROM rebuilt")) == sorted(_rows("SELECT id, name, city FROM users_new"))
