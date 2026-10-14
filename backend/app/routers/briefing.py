"""Morning briefing email (see services/briefing.py)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import briefing

router = APIRouter(prefix="/api/briefing", tags=["briefing"])


class ConfigIn(BaseModel):
    enabled: bool | None = None
    hour: int | None = Field(default=None, ge=0, le=20)


def _r(fn, *a):
    try:
        return fn(*a)
    except briefing.BriefingError as e:
        raise HTTPException(e.status, e.message) from e


@router.get("")
def get_status():
    return briefing.status()


@router.put("/config")
def put_config(body: ConfigIn):
    _r(briefing.update_config, body.model_dump(exclude_none=True))
    return briefing.status()


@router.get("/preview")
def preview():
    return briefing.build()


@router.post("/send")
def send():
    return _r(briefing.send_now)
