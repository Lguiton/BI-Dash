"""Relational design lab endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import relational_lab as rl

router = APIRouter(prefix="/api/relational", tags=["relational"])


def _w(fn, *a, **k):
    try:
        return fn(*a, **k)
    except rl.RelError as e:
        raise HTTPException(400, str(e)) from e


class ErdIn(BaseModel):
    entities: list[dict] = Field(max_length=20)
    relationships: list[dict] = Field(default_factory=list, max_length=40)
    audit_columns: bool = False


class AnalyzeIn(BaseModel):
    table: str | None = Field(default=None, max_length=120)
    demo: bool = False


class DepIn(AnalyzeIn):
    kind: str
    lhs: list[str] = Field(max_length=6)
    rhs: list[str] = Field(max_length=6)


@router.get("")
def reference():
    return rl.reference()


@router.post("/erd")
def erd(b: ErdIn):
    return _w(rl.erd_to_tables, b.entities, b.relationships, b.audit_columns)


@router.post("/analyze")
def analyze(b: AnalyzeIn):
    return _w(rl.analyze, b.table, b.demo)


@router.post("/dependency")
def dependency(b: DepIn):
    return _w(rl.check_dependency, b.table, b.kind, b.lhs, b.rhs, b.demo)
