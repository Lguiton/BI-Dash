"""Computer control and settings reset (personal edition only; every route is a 404 unless it is switched on)."""
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import cors_origins
from app.services import settings_reset, syscontrol

router = APIRouter(prefix="/api/system", tags=["computer"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except syscontrol.SysError as e:
        raise HTTPException(e.status, e.message) from e
    except settings_reset.ResetError as e:
        raise HTTPException(e.status, e.message) from e


def _origin(request: Request) -> None:
    """A browser tab on another site can't be allowed to press these buttons: refuse requests that name an origin we don't trust."""
    o = request.headers.get("origin")
    if o and o not in cors_origins():
        raise HTTPException(403, "That request came from a page this app doesn't trust.")


class PinIn(BaseModel):
    pin: str = Field(max_length=64)
    current: str | None = Field(None, max_length=64)


class RunIn(BaseModel):
    action: str = Field(max_length=40)
    params: dict | None = None
    confirm: str | None = Field(None, max_length=20)


class PreviewIn(BaseModel):
    action: str = Field(max_length=40)
    params: dict | None = None


@router.get("/status")
def status():
    return syscontrol.status()


@router.get("/actions")
def actions():
    _g(syscontrol.need_enabled)
    return syscontrol.catalog()


@router.post("/pin")
def pin(b: PinIn, request: Request):
    _origin(request)
    return _g(syscontrol.set_pin, b.pin, b.current)


@router.post("/arm")
def arm(b: PinIn, request: Request):
    _origin(request)
    return _g(syscontrol.arm, b.pin)


@router.post("/disarm")
def disarm(request: Request):
    _origin(request)
    _g(syscontrol.need_enabled)
    syscontrol.disarm()
    return {"armed": False}


@router.post("/preview")
def preview(b: PreviewIn):
    return _g(syscontrol.preview, b.action, b.params)


@router.post("/run")
def run(b: RunIn, request: Request, x_control_token: str | None = Header(None)):
    _origin(request)
    return _g(syscontrol.run, b.action, b.params, x_control_token, b.confirm)


@router.post("/scan-all")
def scan_all(request: Request, x_control_token: str | None = Header(None)):
    _origin(request)
    return _g(syscontrol.run_scan_all, x_control_token)


@router.get("/jobs/{job_id}")
def job(job_id: str):
    _g(syscontrol.need_enabled)
    return _g(syscontrol.job, job_id)


@router.get("/changes")
def changes():
    _g(syscontrol.need_enabled)
    return {"changes": syscontrol.history()}


@router.post("/changes/{cid}/undo")
def undo(cid: int, request: Request, x_control_token: str | None = Header(None)):
    _origin(request)
    return _g(syscontrol.undo, cid, x_control_token)


@router.post("/changes/{cid}/keep")
def keep(cid: int, request: Request):
    _origin(request)
    return _g(syscontrol.keep, cid)


@router.post("/undo-all")
def undo_all(request: Request, x_control_token: str | None = Header(None)):
    _origin(request)
    return _g(syscontrol.undo_all, x_control_token)


# ---- settings reset (fallback for app settings)
class ResetIn(BaseModel):
    scope: str = Field(max_length=10)


class RestoreIn(BaseModel):
    id: int


@router.get("/settings")
def settings_state():
    _g(syscontrol.need_enabled)
    return {**settings_reset.current(), "snapshots": settings_reset.snapshots()}


@router.post("/settings/snapshot")
def settings_snapshot(request: Request):
    _origin(request)
    _g(syscontrol.need_enabled)
    return settings_reset.snapshot("manual snapshot")


@router.post("/settings/reset")
def settings_do_reset(b: ResetIn, request: Request):
    _origin(request)
    _g(syscontrol.need_enabled)
    return _g(settings_reset.reset, b.scope)


@router.post("/settings/restore")
def settings_do_restore(b: RestoreIn, request: Request):
    _origin(request)
    _g(syscontrol.need_enabled)
    return _g(settings_reset.restore, b.id)
