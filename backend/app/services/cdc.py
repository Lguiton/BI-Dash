"""Change data capture (CDC) for tables you have imported.

* snapshot_diff: compare an old and a new snapshot of a table and find what was inserted, updated and deleted, optionally
  saving that as a change feed.
* apply_changes: turn a change feed (rows with an operation and a sequence) into a current-state table (SCD type 1: keep the
  latest, apply deletes) or a history table (SCD type 2: every version with start and end).

Ordering uses the sequence column, not arrival order, so late or out-of-order events land correctly. Every result is a NEW
table; the inputs are never changed.
"""
from __future__ import annotations

import json

from app.services import datasets, state
from app.services.datasets import DataError, q
from app.services.db import fetch_all, get_cursor

OPS = {"INSERT": "INSERT", "I": "INSERT", "CREATE": "INSERT", "UPDATE": "UPDATE", "U": "UPDATE", "DELETE": "DELETE", "D": "DELETE", "REMOVE": "DELETE"}
SAMPLE = 8


def _cols(table: str) -> list[str]:
    return [c["name"] for c in datasets.table_columns(table)]


def _need_keys(cols: list[str], key: list[str], what: str = "table") -> list[str]:
    key = [k for k in (key or []) if k]
    if not key:
        raise DataError("Pick at least one key column (the column that identifies a record, such as an id).")
    miss = [k for k in key if k not in cols]
    if miss:
        raise DataError(f"Not a column in the {what}: {', '.join(miss)}.")
    return key


def _register(cur, label: str, target: str, note: str) -> int:
    datasets.ensure_registry()
    n = cur.execute(f"SELECT COUNT(*) FROM {q(target)}").fetchone()[0]
    meta = fetch_all(cur, "SELECT column_name AS name, data_type AS type FROM information_schema.columns WHERE table_schema='main' AND table_name = ? ORDER BY ordinal_position", [target])
    cur.execute("DELETE FROM user_tables WHERE table_name = ?", [target])
    cur.execute("INSERT INTO user_tables VALUES (?, ?, ?, ?, ?, now(), now())", [target, label.strip()[:80], note, n, json.dumps(meta)])
    return n


def _target_name(new_table: str, *sources: str) -> str:
    if not (new_table or "").strip():
        raise DataError("Name the new table.")
    t = datasets.table_name_for(new_table)
    if t in sources:
        raise DataError("The new table needs a different name: the inputs are never changed.")
    datasets.ensure_registry()
    with get_cursor() as cur:
        registered = cur.execute("SELECT 1 FROM user_tables WHERE table_name = ?", [t]).fetchone()
        exists = cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='main' AND table_name = ?", [t]).fetchone()
    if exists and not registered:
        raise DataError(f"'{t}' is a built-in table. Pick another name.")
    return t


def snapshot_diff(old: str, new: str, key: list[str], create_feed: str | None = None) -> dict:
    oc, nc = _cols(old), _cols(new)
    key = _need_keys(oc, key, f"old table {old}")
    _need_keys(nc, key, f"new table {new}")
    shared = [c for c in nc if c in oc and c not in key]
    only_old = [c for c in oc if c not in nc]
    only_new = [c for c in nc if c not in oc]
    on = " AND ".join(f"o.{q(k)} IS NOT DISTINCT FROM n.{q(k)}" for k in key)
    kcols = ", ".join(q(k) for k in key)
    changed = " OR ".join(f"o.{q(c)} IS DISTINCT FROM n.{q(c)}" for c in shared) or "FALSE"
    target = _target_name(create_feed, old, new) if create_feed else None
    with get_cursor() as cur:
        for t, label in ((old, "old"), (new, "new")):
            d = cur.execute(f"SELECT COUNT(*) FROM (SELECT {kcols} FROM {q(t)} GROUP BY {kcols} HAVING COUNT(*) > 1)").fetchone()[0]
            if d:
                raise DataError(f"The {label} table has {d} key value(s) that appear more than once, so rows can't be matched one to one. Pick a more specific key.")
        ins = cur.execute(f"SELECT COUNT(*) FROM {q(new)} n WHERE NOT EXISTS (SELECT 1 FROM {q(old)} o WHERE {on})").fetchone()[0]
        dele = cur.execute(f"SELECT COUNT(*) FROM {q(old)} o WHERE NOT EXISTS (SELECT 1 FROM {q(new)} n WHERE {on})").fetchone()[0]
        upd = cur.execute(f"SELECT COUNT(*) FROM {q(old)} o JOIN {q(new)} n ON {on} WHERE {changed}").fetchone()[0]
        same = cur.execute(f"SELECT COUNT(*) FROM {q(old)} o JOIN {q(new)} n ON {on} WHERE NOT ({changed})").fetchone()[0]
        by_col = {c: cur.execute(f"SELECT COUNT(*) FROM {q(old)} o JOIN {q(new)} n ON {on} WHERE o.{q(c)} IS DISTINCT FROM n.{q(c)}").fetchone()[0] for c in shared}
        sample = {
            "inserted": fetch_all(cur, f"SELECT n.* FROM {q(new)} n WHERE NOT EXISTS (SELECT 1 FROM {q(old)} o WHERE {on}) LIMIT {SAMPLE}"),
            "deleted": fetch_all(cur, f"SELECT o.* FROM {q(old)} o WHERE NOT EXISTS (SELECT 1 FROM {q(new)} n WHERE {on}) LIMIT {SAMPLE}"),
            "updated": fetch_all(cur, f"SELECT {', '.join('n.' + q(k) for k in key)}, " + ", ".join(f"o.{q(c)} AS {q('was_' + c)}, n.{q(c)} AS {q('now_' + c)}" for c in shared[:6]) +
                                 f" FROM {q(old)} o JOIN {q(new)} n ON {on} WHERE {changed} LIMIT {SAMPLE}") if shared else [],
        }
        feed_rows = None
        if target:
            data = [c for c in nc]
            sel_new = ", ".join(f"n.{q(c)}" for c in data)
            sel_old = ", ".join((f"o.{q(c)}" if c in oc else "NULL") for c in data)
            cur.execute("BEGIN")
            try:
                cur.execute(f"""CREATE OR REPLACE TABLE {q(target)} AS
                    SELECT {sel_new}, 'INSERT' AS _op, 1 AS _seq FROM {q(new)} n WHERE NOT EXISTS (SELECT 1 FROM {q(old)} o WHERE {on})
                    UNION ALL SELECT {sel_new}, 'UPDATE', 1 FROM {q(old)} o JOIN {q(new)} n ON {on} WHERE {changed}
                    UNION ALL SELECT {sel_old}, 'DELETE', 1 FROM {q(old)} o WHERE NOT EXISTS (SELECT 1 FROM {q(new)} n WHERE {on})""")
                feed_rows = _register(cur, create_feed, target, f"change feed: {old} to {new}")
                cur.execute("COMMIT")
            except Exception:
                cur.execute("ROLLBACK")
                raise
    state.audit("cdc_diff", f"{old} -> {new}: +{ins} ~{upd} -{dele}")
    return {"old": old, "new": new, "key": key, "inserted": ins, "updated": upd, "deleted": dele, "unchanged": same, "changed_by_column": {c: n for c, n in by_col.items() if n},
            "columns_only_in_old": only_old, "columns_only_in_new": only_new, "sample": sample, "feed_table": target, "feed_rows": feed_rows,
            "lesson": "Comparing two snapshots finds what changed when the source gives you no change log: rows only in the new snapshot were inserted, rows only in the old one were deleted, and rows in both with different values were updated. A change feed records those as events (_op and _seq) so they can be applied, in order, to another table."}


def apply_changes(feed: str, key: list[str], op_col: str, seq_col: str, mode: str, new_table: str) -> dict:
    if mode not in ("scd1", "scd2"):
        raise DataError("mode must be scd1 (keep the latest) or scd2 (keep history).")
    cols = _cols(feed)
    key = _need_keys(cols, key, f"change feed {feed}")
    for c, what in ((op_col, "operation"), (seq_col, "sequence")):
        if c not in cols:
            raise DataError(f"Not a column in the change feed: {c} (the {what} column).")
    if op_col == seq_col or op_col in key or seq_col in key:
        raise DataError("The operation, sequence and key columns must all be different.")
    data = [c for c in cols if c not in (op_col, seq_col)]
    target = _target_name(new_table, feed)
    kcols = ", ".join(q(k) for k in key)
    with get_cursor() as cur:
        seen = {str(r[0]).strip().upper() for r in cur.execute(f"SELECT DISTINCT {q(op_col)} FROM {q(feed)} WHERE {q(op_col)} IS NOT NULL").fetchall()}
        bad = sorted(s for s in seen if s not in OPS)
        if bad:
            raise DataError(f"Unknown operation value(s): {', '.join(bad)}. Use insert, update or delete (or I, U, D).")
        nulls = cur.execute(f"SELECT COUNT(*) FROM {q(feed)} WHERE {q(seq_col)} IS NULL OR {q(op_col)} IS NULL").fetchone()[0]
        if nulls:
            raise DataError(f"{nulls} change(s) have no operation or no sequence value, so they can't be put in order.")
        norm = "CASE UPPER(TRIM(CAST({c} AS VARCHAR))) " + " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in OPS.items()) + " END"
        ev = (f"SELECT {', '.join(q(c) for c in data)}, {q(seq_col)} AS _seq, {norm.format(c=q(op_col))} AS _o, rowid AS _r FROM {q(feed)}")
        events = cur.execute(f"SELECT COUNT(*) FROM {q(feed)}").fetchone()[0]
        if not events:
            raise DataError("The change feed is empty.")
        late = cur.execute(f"""SELECT COUNT(*) FROM (SELECT _seq, MAX(_seq) OVER (PARTITION BY {kcols} ORDER BY _r ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prev FROM ({ev})) WHERE prev IS NOT NULL AND _seq < prev""").fetchone()[0]
        dup = cur.execute(f"SELECT COUNT(*) FROM (SELECT 1 FROM ({ev}) GROUP BY {kcols}, _seq HAVING COUNT(*) > 1)").fetchone()[0]
        if dup:
            raise DataError(f"{dup} key(s) have two changes with the same sequence value, so their order is unknown. Make the sequence unique per key.")
        if mode == "scd1":
            sql = (f"SELECT {', '.join(q(c) for c in data)} FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY {kcols} ORDER BY _seq DESC) AS _n FROM ({ev})) WHERE _n = 1 AND _o <> 'DELETE'")
        else:
            sql = (f"SELECT {', '.join(q(c) for c in data)}, _seq AS __start_at, _end AS __end_at, (_end IS NULL) AS is_current FROM "
                   f"(SELECT *, LEAD(_seq) OVER (PARTITION BY {kcols} ORDER BY _seq) AS _end FROM ({ev})) WHERE _o <> 'DELETE'")
        cur.execute("BEGIN")
        try:
            cur.execute(f"CREATE OR REPLACE TABLE {q(target)} AS {sql}")
            n = _register(cur, new_table, target, f"{'current state' if mode == 'scd1' else 'history'} from change feed {feed}")
            keys = cur.execute(f"SELECT COUNT(*) FROM (SELECT DISTINCT {kcols} FROM {q(feed)})").fetchone()[0]
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise
    state.audit("cdc_apply", f"{feed} -> {target} ({mode}): {events} events, {n} rows")
    return {"table": target, "mode": mode, "events": events, "keys": keys, "rows": n, "out_of_order_events": late,
            "lesson": ("SCD type 1 keeps only the latest version of each record and applies deletes, so history is lost. " if mode == "scd1" else
                       "SCD type 2 keeps every version with the sequence value it started and ended at; the version with no end is current, and a delete closes the last version. ") +
            ("Events were put in order by the sequence column, so " + (f"{late} that arrived late were still placed correctly." if late else "arrival order did not matter here.")),
            "note": "The input change feed is unchanged."}
