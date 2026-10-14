"""Data quality rule endpoints."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import expectations as ex

router = APIRouter(prefix="/api/dq", tags=["data quality rules"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except ex.DqError as e:
        raise HTTPException(e.status, str(e)) from e


class RuleIn(BaseModel):
    table: str = Field(max_length=80)
    kind: str = Field(max_length=20)
    params: dict = Field(default_factory=dict)


@router.get("/kinds")
def kinds():
    return {"kinds": [{"id": k, "label": v} for k, v in ex.KINDS.items()]}


@router.get("/rules")
def rules(table: str | None = None):
    return {"rules": ex.list_rules(table)}


@router.post("/rules")
def add(body: RuleIn):
    return _g(ex.add_rule, body.table, body.kind, body.params)


@router.delete("/rules/{rid}")
def delete(rid: int):
    _g(ex.delete_rule, rid)
    return {"deleted": rid}


@router.post("/run")
def run(table: str = Query(max_length=80)):
    return _g(ex.run, table)


@router.get("/suggest")
def suggest(table: str = Query(max_length=80)):
    return _g(ex.suggest, table)


@router.get("/history")
def history(table: str | None = None, limit: int = Query(30, ge=1, le=200)):
    return {"runs": ex.history(table, limit)}
