"""Inventory agent: download the script, import its reports."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.services import inventory_agent as ia
from app.services.itlab import ItError

router = APIRouter(prefix="/api/it-agent", tags=["it-agent"])


def _w(fn, *a):
    try:
        return fn(*a)
    except ItError as e:
        raise HTTPException(e.status, e.message) from e


class Reports(BaseModel):
    text: str = Field(max_length=2_000_000)


@router.get("/script", response_class=PlainTextResponse)
def script():
    return PlainTextResponse(_w(ia.script_text), headers={"Content-Disposition": 'attachment; filename="inventory_agent.py"'})


@router.post("/import")
def import_reports(b: Reports):
    return _w(ia.import_reports, b.text)
