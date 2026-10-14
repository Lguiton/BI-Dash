"""Restore drill: prove a backup really restores, without touching the live database.

A drill copies the newest backup into a scratch folder, opens it like a real restore would (the write-ahead log is replayed),
runs the same integrity checks the live database gets, compares row counts with the live data, and deletes the scratch copy.
Result: pass or fail, how long a restore takes, and your recovery point (how much work a restore would lose).
The live database is never written to.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from app.services import backups, dba, state, workspaces
from app.services.db import get_cursor

KEEP = 20
CORE = ("fact_operations", "dim_entities")


def _key() -> str:
    return f"drill_log:{workspaces.active()}"


def history() -> list[dict]:
    raw = state.kv_get(_key())
    return json.loads(raw) if raw else []


def _live_counts() -> dict:
    with get_cursor() as cur:
        return {t: cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in CORE}


def run(name: str | None = None) -> dict:
    ws = workspaces.active()
    bl = [b for b in backups.list_backups(ws)]
    if not bl:
        raise backups.BackupError("There are no backups to drill. Take one first.", 404)
    b = next((x for x in bl if x["name"] == name), None) if name else (next((x for x in bl if not x["kind"].startswith("safety")), bl[0]))
    if b is None:
        raise backups.BackupError("That backup no longer exists.", 404)
    src = backups._path(b["name"])
    live = _live_counts()
    steps: list[dict] = []
    ok = False
    seconds = 0.0
    behind: dict = {}
    with tempfile.TemporaryDirectory() as td:
        dst = Path(td) / "restored.duckdb"
        t0 = time.perf_counter()
        shutil.copy2(src, dst)
        wal = src.with_name(src.name + ".wal")
        if wal.exists():
            shutil.copy2(wal, dst.with_name(dst.name + ".wal"))
        steps.append({"name": "Copy the backup to a scratch folder", "ok": True, "detail": f"{b['size_bytes']:,} bytes"})
        try:
            con = duckdb.connect(str(dst))                      # a normal open: this is what a real restore does
            try:
                tables = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()}
                steps.append({"name": "Open it and replay the log", "ok": True, "detail": f"{len(tables)} table(s)"})
                missing = [t for t in CORE if t not in tables]
                steps.append({"name": "Core tables are present", "ok": not missing, "detail": ("missing: " + ", ".join(missing)) if missing else ", ".join(CORE)})
                if not missing:
                    counts = {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in CORE}
                    behind = {t: live[t] - counts[t] for t in CORE}
                    steps.append({"name": "Row counts are readable", "ok": True, "detail": ", ".join(f"{t}: {counts[t]:,}" for t in CORE)})
                    checks = dba.integrity_checks(con)
                    failed = [c for c in checks if not c["ok"] and "unused" not in c["detail"]]
                    steps.append({"name": "Integrity checks pass", "ok": not failed, "detail": f"{len(checks) - len(failed)}/{len(checks)} pass" + (": " + failed[0]["name"] if failed else "")})
                    con.execute("CHECKPOINT")
                ok = all(s["ok"] for s in steps)
            finally:
                con.close()
        except Exception as e:  # noqa: BLE001
            steps.append({"name": "Open it and replay the log", "ok": False, "detail": str(e).splitlines()[0][:200]})
        seconds = round(time.perf_counter() - t0, 3)
    age_h = round((datetime.now(timezone.utc) - datetime.strptime(b["created_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)).total_seconds() / 3600, 1)
    entry = {"at": state.now(), "backup": b["name"], "ok": ok, "seconds": seconds, "steps": steps, "backup_age_hours": age_h,
             "records_since_backup": behind.get("fact_operations"),
             "reading": ("PASSED: this backup restores and its data is consistent." if ok else "FAILED: do not rely on this backup. Take a fresh one and run the drill again."),
             "recovery_point": f"A restore of this backup would lose about {age_h:g} hours of changes" + (f" (roughly {behind['fact_operations']:,} records)" if behind.get("fact_operations", 0) > 0 else "") + "."}
    state.kv_set(_key(), json.dumps(([entry] + history())[:KEEP]))
    state.audit("restore_drill", f"{b['name']}: {'passed' if ok else 'FAILED'} in {seconds}s", ok=ok)
    return entry


def due(days: int = 7) -> bool:
    if not backups.list_backups():
        return False
    h = history()
    if not h:
        return True
    age = datetime.now(timezone.utc) - datetime.strptime(h[0]["at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return age.days >= days
