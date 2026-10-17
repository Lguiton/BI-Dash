"""Live capture on the backend's own computer. Private tool: only for networks you own or may test."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import capture

router = APIRouter(prefix="/api/capture", tags=["capture"])


class RunIn(BaseModel):
    iface: str = Field(max_length=300)
    seconds: int = 10
    count: int = 500
    filter: str = Field("", max_length=200)
    confirm: bool = False
    headers_only: bool = True


@router.get("/status")
def status():
    return capture.status()


@router.post("/run")
def run(b: RunIn):
    try:
        return capture.run(b.iface, b.seconds, b.count, b.filter, b.confirm, b.headers_only)
    except capture.CaptureError as e:
        raise HTTPException(e.status, e.message) from None
