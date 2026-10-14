"""Database administration for the active workspace: health, integrity, query benchmarks, checkpoint and backup verification.

DuckDB is an embedded database: one file, one writer, no users or roles. So the DBA work here is the part that applies:
size and free space, constraints and indexes, integrity checks, the slowest standard queries and their plans, and proof
that a backup can actually be restored. (Roles, grants and replication are practised in postgres_practice/.)
"""
from __future__ import annotations

import shutil
import statistics
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from app.services import backups, db, state, workspaces
from app.services.db import fetch_all, fetch_one, get_cursor

SLOW_MS = 250
BENCHMARKS = [
    ("Total revenue and cost", "SELECT SUM(revenue), SUM(operational_cost) FROM fact_operations"),
    ("Daily time series", "SELECT record_date, SUM(revenue) FROM fact_operations GROUP BY 1 ORDER BY 1"),
    ("Fact joined to entity", "SELECT e.category, SUM(f.revenue) FROM fact_operations f JOIN dim_entities e ON e.entity_id = f.entity_id GROUP BY 1"),
    ("Flat view, top entities", "SELECT entity_name, SUM(revenue) AS r FROM v_operations_flat GROUP BY 1 ORDER BY r DESC LIMIT 10"),
    ("Window function over days", "SELECT record_date, SUM(revenue) OVER (ORDER BY record_date) FROM (SELECT record_date, SUM(revenue) AS revenue FROM fact_operations GROUP BY 1)"),
    ("Row count of every imported table", "SELECT COUNT(*) FROM fact_operations"),
]


def _size(p: Path) -> int:
    return p.stat().st_size if p.exists() else 0


def _fmt_time(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def integrity_checks(cur) -> list[dict]:
    def one(sql): return cur.execute(sql).fetchone()[0]
    out = []
    orphans = one("SELECT COUNT(*) FROM fact_operations f WHERE f.entity_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM dim_entities e WHERE e.entity_id = f.entity_id)")
    out.append({"name": "Every record points to a real entity", "ok": orphans == 0, "detail": f"{orphans} orphan record(s)" if orphans else "no orphans",
                "fix": "Add the missing entities to dim_entities, or remove the records."})
    dup = one("SELECT COUNT(*) - COUNT(DISTINCT fact_id) FROM fact_operations")
    out.append({"name": "Record ids are unique", "ok": dup == 0, "detail": f"{dup} duplicate id(s)" if dup else "unique", "fix": "Deduplicate on fact_id."})
    nulls = one("SELECT COUNT(*) FROM fact_operations WHERE record_date IS NULL OR entity_id IS NULL OR revenue IS NULL OR operational_cost IS NULL")
    out.append({"name": "Required fields are filled in", "ok": nulls == 0, "detail": f"{nulls} record(s) missing a required value" if nulls else "complete", "fix": "Fix at the source and re-import."})
    neg = one("SELECT COUNT(*) FROM fact_operations WHERE revenue < 0 OR operational_cost < 0 OR units_processed < 0")
    out.append({"name": "No negative revenue, cost or units", "ok": neg == 0, "detail": f"{neg} negative value(s) (refunds? check)" if neg else "none", "fix": "Confirm they are refunds, or correct them."})
    fut = one("SELECT COUNT(*) FROM fact_operations WHERE record_date > current_date")
    out.append({"name": "No records dated in the future", "ok": fut == 0, "detail": f"{fut} future-dated record(s)" if fut else "none", "fix": "Check the date format (day/month swapped?)."})
    ents = one("SELECT COUNT(*) FROM dim_entities e WHERE NOT EXISTS (SELECT 1 FROM fact_operations f WHERE f.entity_id = e.entity_id)")
    out.append({"name": "No entities without records", "ok": ents == 0, "detail": f"{ents} unused entit(ies)" if ents else "all used", "fix": "Harmless, but remove stale entities to keep lists clean."})
    return out


def health() -> dict:
    ws = workspaces.active()
    path = workspaces.path_of(ws)
    with get_cursor() as cur:
        version = cur.execute("SELECT version()").fetchone()[0]
        size = fetch_one(cur, "PRAGMA database_size")
        tables = fetch_all(cur, """SELECT table_name AS name, estimated_size AS rows, column_count AS columns, has_primary_key AS has_pk, index_count AS indexes
            FROM duckdb_tables() WHERE schema_name = 'main' AND internal = false ORDER BY estimated_size DESC""")
        views = cur.execute("SELECT COUNT(*) FROM duckdb_views() WHERE schema_name = 'main' AND internal = false").fetchone()[0]
        indexes = fetch_all(cur, "SELECT index_name AS name, table_name AS \"table\", is_unique, sql FROM duckdb_indexes() WHERE schema_name = 'main'")
        cons = fetch_all(cur, "SELECT table_name AS \"table\", constraint_type AS type, constraint_column_names AS columns FROM duckdb_constraints() WHERE schema_name = 'main' ORDER BY 1, 2")
        mem = fetch_all(cur, "SELECT tag, memory_usage_bytes AS bytes FROM duckdb_memory() WHERE memory_usage_bytes > 0 ORDER BY 2 DESC")
        sets = fetch_all(cur, "SELECT name, value FROM duckdb_settings() WHERE name IN ('memory_limit','threads','access_mode','enable_external_access','checkpoint_threshold','default_order')")
        checks = integrity_checks(cur)
    total_blocks, free_blocks = int(size.get("total_blocks") or 0), int(size.get("free_blocks") or 0)
    free_pct = round(100 * free_blocks / total_blocks, 1) if total_blocks else 0.0
    wal = path.with_name(path.name + ".wal")
    bl = backups.list_backups(ws)
    last = next((b for b in bl if not b["kind"].startswith("safety")), bl[0] if bl else None)
    age_h = None
    if last:
        age_h = round((datetime.now(timezone.utc) - datetime.strptime(last["created_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)).total_seconds() / 3600, 1)
    findings = []
    if not bl:
        findings.append({"level": "high", "text": "There are no backups of this workspace.", "action": "Back up now (Settings & backups)."})
    elif age_h is not None and age_h > 24 * 7:
        findings.append({"level": "medium", "text": f"The newest backup is {age_h / 24:.0f} days old.", "action": "Back up now, or turn on the daily backup."})
    for c in checks:
        if not c["ok"] and "unused" not in c["detail"]:
            findings.append({"level": "high", "text": f"{c['name']}: {c['detail']}.", "action": c["fix"]})
    if free_pct >= 25 and total_blocks > 8:
        findings.append({"level": "low", "text": f"{free_pct}% of the file is free space left by deleted data.", "action": "Run a checkpoint; to shrink the file, copy the data into a fresh database."})
    if _size(wal) > 16 * 1024 * 1024:
        findings.append({"level": "medium", "text": "The write-ahead log is large.", "action": "Run a checkpoint to fold it into the main file."})
    if any(t["name"] == "fact_operations" and not t["has_pk"] for t in tables):
        findings.append({"level": "medium", "text": "fact_operations has no primary key.", "action": "Add one so duplicates can't slip in."})
    rows_total = sum(t["rows"] or 0 for t in tables)
    hist = state.rows("SELECT at, size_bytes, rows_total FROM dba_snapshots WHERE workspace = ? ORDER BY id DESC LIMIT 60", (ws,))[::-1]
    now = state.now()
    if not hist or (datetime.strptime(now, "%Y-%m-%d %H:%M:%S") - datetime.strptime(hist[-1]["at"], "%Y-%m-%d %H:%M:%S")).total_seconds() > 3600:
        state.run("INSERT INTO dba_snapshots (workspace, at, size_bytes, rows_total) VALUES (?,?,?,?)", (ws, now, _size(path), rows_total))
        state.run("DELETE FROM dba_snapshots WHERE id NOT IN (SELECT id FROM dba_snapshots ORDER BY id DESC LIMIT 400)")
        hist.append({"at": now, "size_bytes": _size(path), "rows_total": rows_total})
    return {"workspace": ws, "engine": f"DuckDB {version}", "file": {"name": path.name, "size_bytes": _size(path), "wal_bytes": _size(wal), "modified": _fmt_time(path.stat().st_mtime) if path.exists() else None},
            "blocks": {"total": total_blocks, "used": int(size.get("used_blocks") or 0), "free": free_blocks, "free_pct": free_pct, "block_size": int(size.get("block_size") or 0)},
            "tables": tables, "views": views, "indexes": indexes, "constraints": cons, "memory": mem, "settings": sets, "integrity": checks,
            "backup": {"count": len(bl), "latest": last, "age_hours": age_h, "auto": workspaces.settings(ws)["auto_backup"],
                       "rpo": "If the file is lost you can recover up to the last backup: that gap is your recovery point."},
            "findings": findings, "growth": hist,
            "access": "DuckDB has one writer and no user accounts: protect the file itself (disk permissions, disk encryption) and the app (it has no login). Roles and grants are practised in postgres_practice/."}


def benchmarks() -> dict:
    out = []
    with get_cursor() as cur:
        for name, sql in BENCHMARKS:
            times = []
            for _ in range(3):
                t0 = time.perf_counter()
                cur.execute(sql).fetchall()
                times.append((time.perf_counter() - t0) * 1000)
            plan = "\n".join(str(r[1]) for r in cur.execute("EXPLAIN " + sql).fetchall())
            ms = statistics.median(times)
            scans = plan.count("SEQ_SCAN") + plan.count("TABLE_SCAN")
            out.append({"name": name, "sql": sql, "median_ms": round(ms, 2), "runs_ms": [round(t, 2) for t in times], "slow": ms > SLOW_MS,
                        "scans": scans, "plan": plan[:1500],
                        "note": "Over the 250 ms line: look at the plan." if ms > SLOW_MS else "Fine."})
    return {"threshold_ms": SLOW_MS, "queries": out,
            "reading": "Each query runs three times and the median is shown. Compare after importing more data to see how things scale. A growing time with the same plan means more rows; a changed plan means a different strategy."}


def checkpoint() -> dict:
    ws = workspaces.active()
    path = workspaces.path_of(ws)
    before = _size(path) + _size(path.with_name(path.name + ".wal"))
    with get_cursor() as cur:
        cur.execute("CHECKPOINT")
    after = _size(path) + _size(path.with_name(path.name + ".wal"))
    state.audit("dba_checkpoint", f"{before} -> {after} bytes")
    return {"before_bytes": before, "after_bytes": after, "message": "Checkpoint done: the write-ahead log was folded into the main file."}


def verify_backup(name: str | None = None) -> dict:
    """Open a COPY of a backup read-only and compare it with the live data. A backup you have never opened is a hope, not a backup."""
    ws = workspaces.active()
    bl = backups.list_backups(ws)
    if not bl:
        raise backups.BackupError("There are no backups to verify. Take one first.", 404)
    b = next((x for x in bl if x["name"] == name), None) if name else bl[0]
    if b is None:
        raise backups.BackupError("That backup no longer exists.", 404)
    src = backups._path(b["name"])
    with get_cursor() as cur:
        live = {t: cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in ("fact_operations", "dim_entities")}
    with tempfile.TemporaryDirectory() as td:
        dst = Path(td) / "verify.duckdb"
        shutil.copy2(src, dst)
        wal = src.with_name(src.name + ".wal")
        if wal.exists():
            shutil.copy2(wal, dst.with_name(dst.name + ".wal"))
        started = time.perf_counter()
        try:
            con = duckdb.connect(str(dst), read_only=True)
            try:
                tables = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()}
                counts = {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in live if t in tables}
                ok_integrity = all(c is not None for c in counts.values())
            finally:
                con.close()
        except Exception as e:  # noqa: BLE001
            state.audit("dba_verify_backup", f"{b['name']}: FAILED to open ({type(e).__name__})", ok=False)
            return {"ok": False, "backup": b["name"], "message": f"The backup could not be opened: {str(e).splitlines()[0]}. Do not rely on it.", "tables": 0, "counts": {}, "live": live}
        secs = round(time.perf_counter() - started, 3)
    diff = {t: {"backup": counts.get(t), "live": live[t]} for t in live}
    same = all(d["backup"] == d["live"] for d in diff.values())
    state.audit("dba_verify_backup", f"{b['name']}: opened, {len(tables)} tables")
    return {"ok": ok_integrity, "backup": b["name"], "tables": len(tables), "counts": diff, "matches_live": same, "restore_seconds": secs,
            "message": ("The backup opens and matches the live data." if same else "The backup opens. It differs from the live data, which is normal if data changed since it was taken.")}
