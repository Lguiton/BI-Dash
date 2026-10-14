"""Backups of the active workspace."""
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services import backups, state, workspaces

router = APIRouter(prefix="/api/backups", tags=["backups"])


class CreateBody(BaseModel):
    note: str = "manual"


class RestoreBody(BaseModel):
    name: str


def _g(fn, *a):
    try:
        return fn(*a)
    except backups.BackupError as e:
        raise HTTPException(e.status, str(e)) from e


@router.get("")
def list_all():
    return {"workspace": workspaces.active(), "backups": backups.list_backups()}


@router.post("")
def create(body: CreateBody, workspace: str | None = None):
    if workspace not in (None, "practice", "real"):
        raise HTTPException(400, "workspace must be practice or real.")
    b = _g(backups.create, body.note or "manual", workspace)
    state.audit("backup", f"manual backup {b['name']}")
    return b


@router.post("/restore")
def restore(body: RestoreBody):
    res = _g(backups.restore, body.name)
    state.audit("restore", f"restored {body.name}")
    return res


class FolderBody(BaseModel):
    folder: str = ""


@router.get("/copy-folder")
def get_copy_folder():
    return backups.copy_folder()


@router.put("/copy-folder")
def put_copy_folder(body: FolderBody):
    return _g(backups.set_copy_folder, body.folder[:300])


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    """Move to this computer: upload a backup made on another one. Then restore it from the list."""
    raw = await file.read(backups.MAX_IMPORT + 1)
    return _g(backups.import_file, raw)


@router.get("/{name}/download")
def download(name: str):
    p = _g(backups._path, name)
    return FileResponse(p, filename=f"{workspaces.active()}-{name}", media_type="application/octet-stream")


@router.delete("/{name}")
def remove(name: str):
    _g(backups.delete, name)
    state.audit("backup_delete", name)
    return {"deleted": name}
