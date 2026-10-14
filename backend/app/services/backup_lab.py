"""A small incremental backup engine with a restore drill, standard library only.

Files are stored once by their SHA-256 (so unchanged files cost nothing the next time), and every snapshot is a list
of file names with their hashes. Restoring re-checks every hash. The practice area in the app uses a private folder;
scripts/backup_tool.py runs the same engine on folders you choose, on your own computer.

Honest limits: no encryption, no compression, no scheduling, no network or cloud target, symlinks are skipped, and a
backup kept on the same disk as the originals protects against deletion and bad edits, not against losing the disk."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

MAX_FILE = 200 * 1024 * 1024
MAX_FILES = 20000


class BackupError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _obj(repo: Path, sha: str) -> Path:
    return repo / "objects" / sha[:2] / sha[2:]


def _snap_dir(repo: Path) -> Path:
    return repo / "snapshots"


def _safe_rel(rel: str) -> str:
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts or not rel or "\x00" in rel:
        raise BackupError(f"The snapshot contains an unsafe path ({rel!r}); restore refused.")
    return rel


def _walk(src: Path):
    n = 0
    for root, dirs, files in os.walk(src, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not (Path(root) / d).is_symlink())
        for f in sorted(files):
            p = Path(root) / f
            if p.is_symlink() or not p.is_file():
                continue
            n += 1
            if n > MAX_FILES:
                raise BackupError(f"More than {MAX_FILES:,} files. Back up a smaller folder.")
            yield p, p.relative_to(src).as_posix()


def snapshot(src: Path, repo: Path, label: str = "") -> dict:
    src, repo = Path(src), Path(repo)
    if not src.is_dir():
        raise BackupError("The folder to back up does not exist.")
    try:
        if repo.resolve().is_relative_to(src.resolve()):
            raise BackupError("The backup location cannot be inside the folder being backed up.")
    except ValueError:
        pass
    _snap_dir(repo).mkdir(parents=True, exist_ok=True)
    prev = list_snapshots(repo)
    old = prev[-1]["files"] if prev else {}
    files, skipped = {}, []
    new_bytes = 0
    stats = {"added": [], "changed": [], "unchanged": 0}
    for p, rel in _walk(src):
        size = p.stat().st_size
        if size > MAX_FILE:
            skipped.append(f"{rel} (over 200 MB)")
            continue
        try:
            sha = _sha(p)
        except OSError as e:
            skipped.append(f"{rel} ({e.strerror or 'unreadable'})")
            continue
        files[rel] = {"sha256": sha, "size": size, "mtime": int(p.stat().st_mtime)}
        o = _obj(repo, sha)
        if not o.exists():
            o.parent.mkdir(parents=True, exist_ok=True)
            tmp = o.with_suffix(".tmp")
            shutil.copy2(p, tmp)
            if _sha(tmp) != sha:
                tmp.unlink(missing_ok=True)
                skipped.append(f"{rel} (changed while it was being copied; run again)")
                files.pop(rel)
                continue
            os.replace(tmp, o)
            new_bytes += size
        if rel not in old:
            stats["added"].append(rel)
        elif old[rel]["sha256"] != sha:
            stats["changed"].append(rel)
        else:
            stats["unchanged"] += 1
    removed = sorted(set(old) - set(files))
    sid = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + f"-{len(prev) + 1:03d}"
    man = {"id": sid, "created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "label": label[:80], "source": str(src), "files": files, "skipped": skipped}
    (_snap_dir(repo) / f"{sid}.json").write_text(json.dumps(man))
    return {"id": sid, "files": len(files), "added": stats["added"], "changed": stats["changed"], "removed": removed, "unchanged": stats["unchanged"], "new_bytes_stored": new_bytes,
            "total_bytes": sum(f["size"] for f in files.values()), "skipped": skipped, "first_backup": not prev}


def list_snapshots(repo: Path) -> list[dict]:
    d = _snap_dir(Path(repo))
    out = []
    if d.is_dir():
        for f in sorted(d.glob("*.json")):
            try:
                out.append(json.loads(f.read_text()))
            except (OSError, ValueError):
                continue
    return out


def _find(repo: Path, sid: str) -> dict:
    for s in list_snapshots(repo):
        if s["id"] == sid:
            return s
    raise BackupError("No snapshot with that id.", 404)


def summary(repo: Path) -> list[dict]:
    return [{"id": s["id"], "created": s["created"], "label": s["label"], "files": len(s["files"]), "bytes": sum(f["size"] for f in s["files"].values())} for s in list_snapshots(repo)]


def verify(repo: Path) -> dict:
    repo = Path(repo)
    need = {f["sha256"] for s in list_snapshots(repo) for f in s["files"].values()}
    missing, corrupt = [], []
    for sha in sorted(need):
        o = _obj(repo, sha)
        if not o.exists():
            missing.append(sha[:12])
        elif _sha(o) != sha:
            corrupt.append(sha[:12])
    return {"objects_checked": len(need), "missing": missing, "corrupt": corrupt, "ok": not missing and not corrupt,
            "lesson": "A backup you have never checked is a hope, not a backup. Verification re-reads every stored file and compares its fingerprint, which catches silent disk damage before the day you need the data."}


def restore(repo: Path, sid: str, dest: Path) -> dict:
    repo, dest = Path(repo), Path(dest)
    snap = _find(repo, sid)
    if dest.exists() and any(dest.iterdir()):
        raise BackupError("Restore into an empty or new folder, so it cannot overwrite anything.")
    t0 = time.monotonic()
    dest.mkdir(parents=True, exist_ok=True)
    bad, n = [], 0
    for rel, meta in sorted(snap["files"].items()):
        rel = _safe_rel(rel)
        o = _obj(repo, meta["sha256"])
        target = dest / rel
        if not target.resolve().is_relative_to(dest.resolve()):
            raise BackupError("Unsafe path in snapshot; restore refused.")
        if not o.exists() or _sha(o) != meta["sha256"]:
            bad.append(rel)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(o, target)
        os.utime(target, (meta["mtime"], meta["mtime"]))
        n += 1
    return {"restored": n, "failed": bad, "seconds": round(time.monotonic() - t0, 3), "ok": not bad}


def drill(repo: Path, sid: str, src: Path) -> dict:
    """Restore a snapshot into a temporary folder and compare it with the live folder."""
    repo, src = Path(repo), Path(src)
    snap = _find(repo, sid)
    tmp = Path(tempfile.mkdtemp(prefix="restore-drill-"))
    try:
        r = restore(repo, sid, tmp / "restored")
        same, differ, missing_now, extra_now = 0, [], [], []
        live = {rel: p for p, rel in _walk(src)} if src.is_dir() else {}
        for rel, meta in snap["files"].items():
            if rel not in live:
                missing_now.append(rel)
            elif _sha(live[rel]) == meta["sha256"]:
                same += 1
            else:
                differ.append(rel)
        extra_now = sorted(set(live) - set(snap["files"]))
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(snap["created"])).total_seconds()
        return {"snapshot": sid, "restore_ok": r["ok"], "restored_files": r["restored"], "restore_seconds": r["seconds"], "failed": r["failed"], "identical_to_live": same,
                "changed_since": differ, "deleted_since": missing_now, "new_since": extra_now, "snapshot_age_minutes": round(age / 60, 1),
                "reading": ("The restore worked and every file's fingerprint matched what was stored. " if r["ok"] else "The restore FAILED for some files: do not trust this backup. ")
                + (f"Since the snapshot, {len(differ)} file(s) changed, {len(missing_now)} were deleted and {len(extra_now)} are new: that is the data you would lose, or recover, depending on which way you restore." if (differ or missing_now or extra_now) else "The live folder is identical to the snapshot."),
                "lesson": "A restore drill answers the two questions that matter: does the restore work (and how long did it take: your recovery time), and how much would be lost since the last backup (your recovery point)."}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def prune(repo: Path, keep: int) -> dict:
    repo = Path(repo)
    if not 1 <= keep <= 1000:
        raise BackupError("Keep between 1 and 1000 snapshots.")
    snaps = list_snapshots(repo)
    drop = snaps[:-keep] if len(snaps) > keep else []
    for s in drop:
        (_snap_dir(repo) / f"{s['id']}.json").unlink(missing_ok=True)
    live = {f["sha256"] for s in list_snapshots(repo) for f in s["files"].values()}
    freed = 0
    removed = 0
    ob = repo / "objects"
    if ob.is_dir():
        for p in ob.glob("*/*"):
            if p.suffix == ".tmp" or (p.parent.name + p.name) not in live:
                freed += p.stat().st_size
                p.unlink(missing_ok=True)
                removed += 1
    return {"snapshots_removed": len(drop), "objects_removed": removed, "bytes_freed": freed, "kept": len(snaps) - len(drop)}


SLIPS = ["Backup guides say 'sync to the cloud' is a backup. A sync copies deletions and ransomware-encrypted files too; a backup keeps older versions.",
         "Many guides treat the 3-2-1 rule as three copies on three disks. It is three copies, on two kinds of storage, with one copy off-site.",
         "Tutorials show copying with 'cp -r' as a backup. It cannot tell you what changed, cannot keep versions and cannot prove the copy is complete."]
NOT_BUILT = ["Encryption, compression, scheduling, cloud or network targets, and database-aware backups (use the database's own dump or snapshot tool).", "Open-file/VSS snapshots on Windows: files in use may be skipped or copied mid-change.", "For real data use a proven tool such as restic, Borg or Veeam; this engine teaches the ideas and handles small folders."]
