"""Business-data backup: your clients, jobs, invoices, leads, books, fix log, notes and settings.

The older Backups copy the DuckDB database only. Your freelance records live in the separate state file, so this makes a zip of that file
(taken with SQLite's own backup call, so it is consistent while the app runs), with a manifest of what was inside and a checksum.
Every bundle can be put through a restore test: it is opened in a scratch folder, checked against its checksum and row counts, and nothing
live is touched. Restoring takes a safety bundle first, so a restore can be undone. A copy also goes to the folder you chose for backups
(USB drive, OneDrive or Google Drive folder), if you set one."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import tempfile
import threading
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import backups_dir
from app.services import state

NAME_RE = re.compile(r"^\d{8}-\d{6}_[a-z0-9-]{1,40}\.zip$")
KEEP, SAFETY_KEEP, EVERY, STALE_DAYS = 14, 5, timedelta(hours=20), 7
_lock = threading.Lock()


class BizBackupError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _dir() -> Path:
    p = backups_dir() / "business"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _counts(c: sqlite3.Connection) -> dict:
    """What matters to a freelancer, counted from a database connection (a live one or a scratch copy)."""
    out = {"clients": 0, "jobs": 0, "invoices": 0, "leads": 0, "fixes": 0, "keys": 0}
    try:
        out["keys"] = c.execute("SELECT COUNT(*) FROM kv").fetchone()[0]
        for key, value in c.execute("SELECT key, value FROM kv WHERE key LIKE 'clients:%' OR key LIKE 'leads:%'").fetchall():
            try:
                d = json.loads(value)
            except ValueError:
                continue
            if key.startswith("clients:"):
                for k in ("clients", "jobs", "invoices"):
                    out[k] += len(d.get(k, []))
            else:
                out["leads"] += len(d.get("leads", []))
        out["fixes"] = c.execute("SELECT COUNT(*) FROM fix_log").fetchone()[0]
    except sqlite3.Error:
        pass
    return out


def _name(kind: str) -> str:
    k = re.sub(r"[^a-z0-9-]+", "-", kind.lower()).strip("-")[:30] or "manual"
    return f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}_{k}.zip"


def create(kind: str = "manual") -> dict:
    with _lock, tempfile.TemporaryDirectory() as tmp:
        snap = Path(tmp) / "state.sqlite"
        with state._lock:
            dst = sqlite3.connect(snap)
            try:
                state.conn().backup(dst)
            finally:
                dst.close()
        check = sqlite3.connect(snap)
        try:
            counts = _counts(check)
        finally:
            check.close()
        manifest = {"made": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "kind": kind, "sha256": _sha(snap), "counts": counts, "format": 1}
        name = _name(kind)
        dest = _dir() / name
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(snap, "state.sqlite")
            z.writestr("manifest.json", json.dumps(manifest, indent=2))
            z.writestr("README.txt", "Business-data backup from the BI Dashboard.\nstate.sqlite holds clients, jobs, invoices, leads, books, fix log, notes and settings.\n"
                       "Restore it from Settings, Data and backups, Business data. Do not edit it by hand.\n")
    _prune()
    _copy_out(dest)
    state.audit("bizbackup.create", f"{name} {counts['clients']} clients, {counts['invoices']} invoices")
    return _describe(dest)


def _describe(p: Path) -> dict:
    man: dict = {}
    try:
        with zipfile.ZipFile(p) as z:
            man = json.loads(z.read("manifest.json"))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        pass
    ver = _verified().get(p.name)
    return {"name": p.name, "kind": p.stem.split("_", 1)[1] if "_" in p.stem else "manual", "size_bytes": p.stat().st_size,
            "created_at": datetime.strptime(p.name[:15], "%Y%m%d-%H%M%S").strftime("%Y-%m-%d %H:%M:%S"), "counts": man.get("counts", {}), "tested": ver}


def _verified() -> dict:
    try:
        v = json.loads(state.kv_get("bizbackup_verified") or "{}")
        return v if isinstance(v, dict) else {}
    except ValueError:
        return {}


def listing() -> list[dict]:
    return sorted((_describe(p) for p in _dir().glob("*.zip") if NAME_RE.match(p.name)), key=lambda b: b["name"], reverse=True)


def _prune() -> None:
    items = listing()
    safety = [b for b in items if b["kind"].startswith("safety")]
    normal = [b for b in items if not b["kind"].startswith("safety")]
    for b in normal[KEEP:] + safety[SAFETY_KEEP:]:
        (_dir() / b["name"]).unlink(missing_ok=True)


def _copy_out(src: Path) -> None:
    """A copy in the folder you chose for backups. Never raises: a missing USB drive must not break the backup itself."""
    folder = state.kv_get("backup_copy_dir", "") or ""
    if not folder:
        return
    try:
        from app.services import backups
        dest = backups._real_path(folder)
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest / f"business_{src.name}")
        for old in sorted(dest.glob("business_*.zip"), reverse=True)[KEEP:]:
            old.unlink(missing_ok=True)
        state.kv_set("bizbackup_copy_last", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " ok")
    except Exception as e:  # noqa: BLE001
        state.kv_set("bizbackup_copy_last", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + f" failed: {e}")


def _path(name: str) -> Path:
    if not NAME_RE.match(name):
        raise BizBackupError("Not a valid backup name.", 404)
    p = _dir() / name
    if not p.exists():
        raise BizBackupError("That backup no longer exists.", 404)
    return p


def _extract(p: Path, tmp: str) -> tuple[Path, dict]:
    try:
        with zipfile.ZipFile(p) as z:
            names = set(z.namelist())
            if "state.sqlite" not in names or "manifest.json" not in names:
                raise BizBackupError("This zip is missing the database or its manifest.")
            man = json.loads(z.read("manifest.json"))
            out = Path(tmp) / "state.sqlite"
            with z.open("state.sqlite") as src, out.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            return out, man
    except (zipfile.BadZipFile, ValueError, OSError):
        raise BizBackupError("This backup file is damaged or isn't a business-data backup.") from None


def verify(name: str) -> dict:
    """The restore test. Works on a scratch copy only; nothing live changes."""
    p = _path(name)
    checks = []
    with tempfile.TemporaryDirectory() as tmp:
        try:
            snap, man = _extract(p, tmp)
        except BizBackupError as e:
            checks.append({"name": "Opens as a backup", "ok": False, "detail": e.message})
            return _record(name, checks)
        checks.append({"name": "Opens as a backup", "ok": True, "detail": "The zip and its manifest were read."})
        ok = _sha(snap) == man.get("sha256")
        checks.append({"name": "Checksum matches", "ok": ok, "detail": "The database is exactly what was saved." if ok else "The database file changed after it was saved."})
        try:
            c = sqlite3.connect(f"file:{snap}?mode=ro", uri=True)
            try:
                integ = c.execute("PRAGMA integrity_check").fetchone()[0]
                checks.append({"name": "Database is healthy", "ok": integ == "ok", "detail": "SQLite's own integrity check passed." if integ == "ok" else str(integ)[:120]})
                counts = _counts(c)
            finally:
                c.close()
            same = counts == man.get("counts")
            want = man.get("counts", {})
            checks.append({"name": "Records are all there", "ok": same, "detail": (f"{counts['clients']} clients, {counts['jobs']} jobs, {counts['invoices']} invoices, {counts['leads']} leads, {counts['fixes']} fixes."
                                                                                if same else f"Found {counts}, but it was saved with {want}.")})
        except sqlite3.Error as e:
            checks.append({"name": "Database is healthy", "ok": False, "detail": f"Could not open it: {str(e)[:100]}"})
    return _record(name, checks)


def _record(name: str, checks: list[dict]) -> dict:
    ok = all(c["ok"] for c in checks)
    v = _verified()
    v[name] = {"ok": ok, "at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")}
    keep = {n for n in (b["name"] for b in listing())}
    state.kv_set("bizbackup_verified", json.dumps({k: x for k, x in v.items() if k in keep or k == name}))
    return {"name": name, "ok": ok, "checks": checks}


def restore(name: str) -> dict:
    """Replace the live business records with this backup. Refuses a backup that fails the restore test, and saves a safety bundle first."""
    p = _path(name)
    res = verify(name)
    if not res["ok"]:
        raise BizBackupError("This backup failed its restore test, so it was not restored: " + "; ".join(c["detail"] for c in res["checks"] if not c["ok"]), 409)
    create("safety-before-restore")
    with _lock, tempfile.TemporaryDirectory() as tmp:
        snap, _ = _extract(p, tmp)
        src = sqlite3.connect(snap)
        try:
            with state._lock:
                live = state.conn()
                src.backup(live)
                live.executescript(state.SCHEMA)
                state._migrate(live)
        finally:
            src.close()
    state.audit("bizbackup.restore", name)
    return {"restored": name}


def delete(name: str) -> None:
    _path(name).unlink()


def path_of(name: str) -> Path:
    return _path(name)


def status(now: datetime | None = None) -> dict:
    """For the Today screen and Settings: when the last bundle was made, whether it was tested, and a warning if it is old or missing."""
    now = now or datetime.now(timezone.utc)
    items = [b for b in listing() if not b["kind"].startswith("safety")]
    last = items[0] if items else None
    age = None
    warn = ""
    if last:
        age = round((now - datetime.strptime(last["created_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)).total_seconds() / 3600, 1)
        if age > STALE_DAYS * 24:
            warn = f"The newest business backup is {int(age // 24)} days old. Make a new one."
        elif not last["tested"]:
            warn = "The newest business backup hasn't been through the restore test yet."
        elif not last["tested"]["ok"]:
            warn = "The newest business backup FAILED its restore test. Make a new one."
    else:
        warn = "There is no business-data backup yet. Make one."
    folder = state.kv_get("backup_copy_dir", "") or ""
    return {"last": last, "age_hours": age, "count": len(items), "warning": warn, "copy_folder": folder, "copy_last": state.kv_get("bizbackup_copy_last", "") or ""}


def tick(now: datetime | None = None) -> list[str]:
    """Runs while the app runs: a new bundle at most every 20 hours, tested right away. Never raises."""
    try:
        now = now or datetime.now(timezone.utc)
        items = [b for b in listing() if not b["kind"].startswith("safety")]
        if items and now - datetime.strptime(items[0]["created_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) < EVERY:
            return []
        b = create("auto")
        verify(b["name"])
        return ["business-backup"]
    except Exception:  # noqa: BLE001 - a failed backup never stops the app; Today shows the warning
        return []
