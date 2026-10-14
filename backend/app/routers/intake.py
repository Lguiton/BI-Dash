"""Intake Workflow: upload a file; the Supervisor runs it past the specialist agents stage by stage."""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import MAX_UPLOAD_BYTES
from app.services import intake

router = APIRouter(prefix="/api/intake", tags=["intake"])


def _wrap(fn, *a):
    try:
        return fn(*a)
    except intake.IntakeError as e:
        raise HTTPException(e.status, e.message) from e


@router.get("/agents")
def agents():
    return intake.agents()


@router.get("")
def runs():
    return {"runs": intake.list_runs()}


@router.post("/start")
async def start(file: UploadFile = File(...), name: str = Form(""), target: str = Form(""), preview: bool = Form(True), protect_pii: bool = Form(True)):
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    return _wrap(intake.start, raw, file.filename or "data.csv", name, target, preview, protect_pii)


@router.get("/{rid}")
def one(rid: str):
    return _wrap(intake.get, rid)


@router.post("/{rid}/next")
def nxt(rid: str):
    return _wrap(intake.advance, rid)


@router.post("/{rid}/apply")
def apply(rid: str):
    return _wrap(intake.apply, rid)


@router.post("/{rid}/undo")
def undo(rid: str):
    return _wrap(intake.undo, rid)
