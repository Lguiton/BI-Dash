"""Backup practice area: an incremental backup engine, a restore drill and a corruption check, on a private sample folder."""
import shutil

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import db_path
from app.services import backup_lab as bl
from app.services.backup_lab import BackupError

router = APIRouter(prefix="/api/backuplab", tags=["backuplab"])

SAMPLE = {"notes.txt": "Meeting notes\n- budget approved\n", "budget.csv": "item,cost\nlaptops,4800\nlicences,1200\n", "readme.md": "# Project\nPractice files for the backup lab.\n", "docs/plan.txt": "Plan v1\n", "docs/risks.txt": "Risk list\n1. Data loss\n"}


def _root():
    return db_path().parent / "backup_lab"


def _src():
    return _root() / "source"


def _repo():
    return _root() / "repo"


def _w(fn, *a, **k):
    try:
        return fn(*a, **k)
    except BackupError as e:
        raise HTTPException(e.status, e.message) from e


def _files():
    if not _src().is_dir():
        return []
    return [{"name": p.relative_to(_src()).as_posix(), "bytes": p.stat().st_size} for p in sorted(_src().rglob("*")) if p.is_file()]


def _state():
    return {"files": _files(), "snapshots": bl.summary(_repo()), "ready": _src().is_dir()}


class Label(BaseModel):
    label: str = Field(default="", max_length=80)


class Edit(BaseModel):
    action: str = Field(max_length=20)


class Sid(BaseModel):
    id: str = Field(max_length=40)


class Keep(BaseModel):
    keep: int = 3


@router.get("")
def state():
    return _state()


@router.get("/reference")
def reference():
    return {"slips": bl.SLIPS, "not_built": bl.NOT_BUILT}


@router.post("/reset")
def reset():
    shutil.rmtree(_root(), ignore_errors=True)
    for rel, text in SAMPLE.items():
        p = _src() / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return _state()


@router.post("/edit")
def edit(b: Edit):
    if not _src().is_dir():
        raise HTTPException(400, "Press Reset practice folder first.")
    files = sorted(p for p in _src().rglob("*") if p.is_file())
    if b.action == "modify":
        if not files:
            raise HTTPException(400, "There are no files to change.")
        with files[0].open("a") as f:
            f.write(f"edited line {len(files[0].read_text().splitlines()) + 1}\n")
    elif b.action == "add":
        n = 1
        while (_src() / f"report-{n}.txt").exists():
            n += 1
        (_src() / f"report-{n}.txt").write_text(f"New report {n}\n")
    elif b.action == "delete":
        if not files:
            raise HTTPException(400, "There are no files to delete.")
        pick = next((f for f in files if f.name == "risks.txt"), None) or next((f for f in reversed(files) if not f.name.startswith("report-")), files[-1])
        pick.unlink()
    elif b.action == "corrupt":
        objs = sorted((_repo() / "objects").glob("*/*")) if (_repo() / "objects").is_dir() else []
        if not objs:
            raise HTTPException(400, "Take a backup first; there is nothing stored to damage.")
        data = bytearray(objs[0].read_bytes() or b"x")
        data[0] ^= 0xFF
        objs[0].write_bytes(bytes(data))
    else:
        raise HTTPException(400, "Action must be modify, add, delete or corrupt.")
    return _state()


@router.post("/snapshot")
def snap(b: Label):
    if not _src().is_dir():
        raise HTTPException(400, "Press Reset practice folder first.")
    return {"result": _w(bl.snapshot, _src(), _repo(), b.label), **_state()}


@router.post("/verify")
def verify():
    return _w(bl.verify, _repo())


@router.post("/drill")
def drill(b: Sid):
    return _w(bl.drill, _repo(), b.id, _src())


@router.post("/restore")
def restore(b: Sid):
    dest = _root() / "restored"
    shutil.rmtree(dest, ignore_errors=True)
    r = _w(bl.restore, _repo(), b.id, dest)
    return {**r, "files": sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()), "where": "the practice area's 'restored' folder (not your source folder)"}


@router.post("/prune")
def prune(b: Keep):
    return {"result": _w(bl.prune, _repo(), b.keep), **_state()}
