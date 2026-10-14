"""Dataset hub endpoints: health check, notes and tags for imported tables."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import datahub, datasets

router = APIRouter(prefix="/api/hub", tags=["hub"])


def _g(fn, *a):
    try:
        return fn(*a)
    except datasets.DataError as e:
        raise HTTPException(e.status, e.message) from e


class NotesIn(BaseModel):
    note: str = Field("", max_length=datahub.MAX_NOTE)
    tags: list[str] = Field(default_factory=list, max_length=20)


@router.get("")
def hub():
    return {"tables": datahub.list_hub()}


@router.get("/{table}")
def table_summary(table: str):
    return _g(datahub.summary, table)


@router.put("/{table}/notes")
def table_notes(table: str, body: NotesIn):
    return _g(datahub.set_notes, table, body.note, body.tags)
