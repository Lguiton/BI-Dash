"""Backups of the active workspace's database file.

A backup is a plain copy of the .duckdb file taken while the connection is closed (a few milliseconds), so it is always
consistent. Restoring copies one back, after taking a safety backup of what is there now, so a restore can be undone.
Files live in <data dir>/backups/<workspace>/.
"""
import re
import shutil
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import backups_dir
from app.services import db, state, workspaces

NAME_RE = re.compile(r"^\d{8}-\d{6}_[a-z0-9-]{1,40}\.duckdb$")
SAFETY_KEEP = 10
_lock = threading.Lock()


class BackupError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _dir(ws: str) -> Path:
    d = backups_dir() / ws
    d.mkdir(parents=True, exist_ok=True)
    return d


def _label(kind: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", kind.lower().replace(" ", "-").replace("_", "-"))[:40] or "manual"


def create(kind: str = "manual") -> dict:
    ws = workspaces.active()
    src = workspaces.path_of(ws)
    if not src.exists():
        raise BackupError("There is nothing to back up yet (the database file doesn't exist).")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    name = f"{stamp}_{_label(kind)}.duckdb"
    dest = _dir(ws) / name
    with _lock, db.exclusive():
        shutil.copy2(src, dest)
        wal = src.with_name(src.name + ".wal")
        if wal.exists():
            shutil.copy2(wal, dest.with_name(dest.name + ".wal"))
    prune(ws)
    return describe(ws, dest)


def safety_backup(reason: str) -> None:
    """Take a backup before something destructive. Only for Real data (Practice is meant to be broken) and never raises."""
    try:
        if workspaces.active() == "real" and workspaces.path_of("real").exists():
            create(f"safety-{reason}")
    except Exception:  # noqa: BLE001
        pass


def describe(ws: str, p: Path) -> dict:
    st = p.stat()
    kind = p.stem.split("_", 1)[1] if "_" in p.stem else "manual"
    return {"name": p.name, "kind": kind, "size_bytes": st.st_size,
            "created_at": datetime.strptime(p.name[:15], "%Y%m%d-%H%M%S").strftime("%Y-%m-%d %H:%M:%S")}


def list_backups(ws: str | None = None) -> list[dict]:
    ws = ws or workspaces.active()
    out = [describe(ws, p) for p in _dir(ws).glob("*.duckdb") if NAME_RE.match(p.name)]
    return sorted(out, key=lambda b: b["name"], reverse=True)


def prune(ws: str) -> None:
    keep = int(workspaces.settings(ws)["backup_keep"])
    items = list_backups(ws)
    safety = [b for b in items if b["kind"].startswith("safety")]
    normal = [b for b in items if not b["kind"].startswith("safety")]
    for b in normal[keep:] + safety[SAFETY_KEEP:]:
        p = _dir(ws) / b["name"]
        p.unlink(missing_ok=True)
        p.with_name(p.name + ".wal").unlink(missing_ok=True)


def _path(name: str) -> Path:
    if not NAME_RE.match(name):
        raise BackupError("Not a valid backup name.", 404)
    p = _dir(workspaces.active()) / name
    if not p.exists():
        raise BackupError("That backup no longer exists.", 404)
    return p


def restore(name: str) -> dict:
    src = _path(name)
    ws = workspaces.active()
    create("safety-before-restore")           # so the restore itself can be undone
    live = workspaces.path_of(ws)
    with _lock, db.exclusive():
        shutil.copy2(src, live)
        live.with_name(live.name + ".wal").unlink(missing_ok=True)
        wal = src.with_name(src.name + ".wal")
        if wal.exists():
            shutil.copy2(wal, live.with_name(live.name + ".wal"))
    workspaces._prepare(ws)                    # backups from older versions get any missing tables
    return {"restored": name, "workspace": ws}


def delete(name: str) -> None:
    p = _path(name)
    p.unlink()
    p.with_name(p.name + ".wal").unlink(missing_ok=True)


def maybe_auto() -> dict | None:
    """Daily automatic backup for the active workspace if its setting is on and the last one is over 24 hours old."""
    ws = workspaces.active()
    if not workspaces.settings(ws)["auto_backup"] or not workspaces.path_of(ws).exists():
        return None
    last = [b for b in list_backups(ws) if not b["kind"].startswith("safety")]
    if last:
        age = datetime.now(timezone.utc) - datetime.strptime(last[0]["created_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        if age < timedelta(hours=24):
            return None
    b = create("auto")
    state.audit("backup", f"auto backup {b['name']}")
    return b
