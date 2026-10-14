"""Single-source-of-truth audits (systems, metrics, documents, key-person risk)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import info_audit as ia

router = APIRouter(prefix="/api/infoaudit", tags=["infoaudit"])


def _w(fn, *a):
    try:
        return fn(*a)
    except ia.AuditError as e:
        raise HTTPException(e.status, e.message) from e


class TextIn(BaseModel):
    text: str = Field(max_length=100_000)


class DocsIn(TextIn):
    stale_days: int = Field(365, ge=1, le=3650)


class CostIn(BaseModel):
    people: float
    searches_per_day: float
    minutes_each: float
    hourly_cost: float
    working_days: float = 230


@router.get("/reference")
def reference():
    return ia.reference()


@router.get("/sample")
def sample():
    return ia.SAMPLE


@router.post("/systems")
def systems(b: TextIn):
    return _w(ia.systems, b.text)


@router.post("/metrics")
def metrics(b: TextIn):
    return _w(ia.metrics, b.text)


@router.post("/documents")
def documents(b: DocsIn):
    return _w(ia.documents, b.text, b.stale_days)


@router.post("/search-cost")
def search_cost(b: CostIn):
    return _w(ia.search_cost, b.people, b.searches_per_day, b.minutes_each, b.hourly_cost, b.working_days)


@router.post("/key-person")
def key_person(b: TextIn):
    return _w(ia.key_person, b.text)
