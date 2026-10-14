"""Backups of the active workspace's database file.

A backup is a plain copy of the .duckdb file taken while the connection is closed (a few milliseconds), so it is always
consistent. Restoring copies one back, after taking a safety backup of what is there now, so a restore can be undone.
Files live in <data dir>/backups/<workspace>/.
"""
import contextlib
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


def create(kind: str = "manual", ws: str | None = None) -> dict:
    active = workspaces.active()
    ws = ws or active
    src = workspaces.path_of(ws)
    if not src.exists():
        raise BackupError("There is nothing to back up yet (the database file doesn't exist).")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    name = f"{stamp}_{_label(kind)}.duckdb"
    dest = _dir(ws) / name
    with _lock, (db.exclusive() if ws == active else contextlib.nullcontext()):      # a workspace that isn't open can be copied as it is
        shutil.copy2(src, dest)
        wal = src.with_name(src.name + ".wal")
        if wal.exists():
            shutil.copy2(wal, dest.with_name(dest.name + ".wal"))
    prune(ws)
    copy_out(dest)
    return describe(ws, dest)


# ---- copy to another place (USB drive, OneDrive or Google Drive folder), so a lost laptop doesn't lose the data ----
COPY_KEEP = 14


def _real_path(text: str) -> Path:
    """Accept a Windows path like D:\\Backups even though the app runs inside WSL (it becomes /mnt/d/Backups)."""
    t = text.strip().strip('"')
    m = re.match(r"^([A-Za-z]):[\\/](.*)$", t)
    if m and not Path(t).exists() and Path("/mnt").exists():
        return Path("/mnt") / m.group(1).lower() / m.group(2).replace("\\", "/")
    return Path(t)


def copy_folder() -> dict:
    return {"folder": state.kv_get("backup_copy_dir", "") or "", "last": state.kv_get("backup_copy_last", "") or "", "keep": COPY_KEEP}


def set_copy_folder(folder: str) -> dict:
    folder = (folder or "").strip()
    if not folder:
        state.kv_set("backup_copy_dir", "")
        state.kv_set("backup_copy_last", "")
        return copy_folder()
    p = _real_path(folder)
    try:
        p.mkdir(parents=True, exist_ok=True)
        probe = p / ".bi_write_test"
        probe.write_text("ok")
        probe.unlink()
    except OSError as e:
        raise BackupError(f"I can't write to that folder ({e.strerror or 'not allowed'}). Check the path and that the drive is plugged in.") from e
    state.kv_set("backup_copy_dir", folder)
    state.kv_set("backup_copy_last", "")
    state.audit("backup_copy_folder", folder)
    return copy_folder()


def copy_out(src: Path) -> None:
    """Copy a fresh backup to the chosen folder. Never raises: a missing USB drive must not break the backup itself."""
    folder = state.kv_get("backup_copy_dir", "") or ""
    if not folder:
        return
    try:
        dest = _real_path(folder)
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest / f"{src.parent.name}_{src.name}")
        mine = sorted(dest.glob(f"{src.parent.name}_*.duckdb"), reverse=True)
        for old in mine[COPY_KEEP:]:
            old.unlink(missing_ok=True)
        state.kv_set("backup_copy_last", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " ok")
    except Exception as e:  # noqa: BLE001
        state.kv_set("backup_copy_last", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + f" failed: {e}")


MAX_IMPORT = 1024 * 1024 * 1024


def import_file(raw: bytes) -> dict:
    """Bring a backup from another computer. It is checked, then saved with your other backups; restoring it is a separate step."""
    import duckdb
    import tempfile
    if len(raw) > MAX_IMPORT:
        raise BackupError("That file is over 1 GB.")
    if raw[8:12] != b"DUCK":
        raise BackupError("That isn't a database backup from this dashboard (.duckdb file).")
    ws = workspaces.active()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = _dir(ws) / f"{stamp}_imported.duckdb"
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False, dir=str(_dir(ws))) as t:
        t.write(raw)
        tmp = Path(t.name)
    try:
        con = duckdb.connect(str(tmp), read_only=True)
        try:
            n = con.execute("SELECT COUNT(*) FROM information_schema.tables").fetchone()[0]
        finally:
            con.close()
    except Exception as e:  # noqa: BLE001
        tmp.unlink(missing_ok=True)
        raise BackupError("That file couldn't be opened as a database. It may be damaged.") from e
    tmp.replace(dest)
    state.audit("backup_import", f"{dest.name}: {n} tables")
    return {**describe(ws, dest), "tables": int(n)}


DAILY_EVERY = timedelta(hours=20)


def daily_tick(now: datetime | None = None) -> list[str]:
    """Automatic backup of your Real data, at most once every 20 hours. Because the computer isn't always on, this runs whenever the app is running
    (including right after it starts), not at a fixed clock time. Practice data is not backed up automatically."""
    try:
        if not workspaces.path_of("real").exists():
            return []
        now = now or datetime.now(timezone.utc)
        last = next((b for b in list_backups("real") if b["kind"] == "daily"), None)
        if last and now - datetime.strptime(last["created_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) < DAILY_EVERY:
            return []
        create("daily", "real")
        state.audit("auto_backup", "daily backup of Real data")
        return ["daily-backup"]
    except Exception:  # noqa: BLE001 - a failed backup never stops the app; the Settings page shows the newest backup
        return []


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
