"""Business-data backup: make, test, restore, download."""
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse

from app.services import bizbackup as bb

router = APIRouter(prefix="/api/biz-backup", tags=["biz-backup"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except bb.BizBackupError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("")
def listing():
    return {"backups": bb.listing(), "status": bb.status()}


@router.post("")
def create():
    b = bb.create("manual")
    return {**b, "test": bb.verify(b["name"])}


@router.post("/{name}/test")
def test(name: str):
    return _g(bb.verify, name)


@router.post("/{name}/restore")
def restore(name: str, body: dict = Body(default={})):
    if body.get("confirm") is not True:
        raise HTTPException(400, "Confirm the restore first.")
    return _g(bb.restore, name)


@router.get("/{name}/download")
def download(name: str):
    p = _g(bb.path_of, name)
    return FileResponse(p, media_type="application/zip", filename=p.name)


@router.delete("/{name}")
def delete(name: str):
    _g(bb.delete, name)
    return {"deleted": name}
