"""Job Autopilot endpoint: upload a file plus a concern, get every fitting analysis back. Nothing is stored."""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services import autopilot

router = APIRouter(prefix="/api/autopilot", tags=["autopilot"])


@router.post("/run")
async def run(file: UploadFile = File(...), concern: str = Form(""), field: str = Form("")):
    raw = await file.read(autopilot.MAX_BYTES + 1)
    try:
        return autopilot.run(file.filename or "upload", raw, concern[:2000], field[:40])
    except autopilot.AutoError as e:
        raise HTTPException(e.status, e.message) from None
