"""Pipeline runner endpoints."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import pipelines as pl

router = APIRouter(prefix="/api/pipelines", tags=["pipeline runner"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except pl.PipelineError as e:
        raise HTTPException(e.status, str(e)) from e


class PipeIn(BaseModel):
    name: str = Field(max_length=80)
    tasks: list[dict] = Field(min_length=1, max_length=pl.MAX_TASKS)
    every_minutes: int = Field(0, ge=0, le=10080)
    enabled: bool = True
    id: int | None = None


@router.get("")
def pipelines():
    return {"pipelines": pl.list_pipelines(), "kinds": [{"id": k, "label": v} for k, v in pl.KINDS.items()]}


@router.post("")
def save(body: PipeIn):
    return _g(pl.save, body.name, body.tasks, body.every_minutes, body.enabled, body.id)


@router.delete("/{pid}")
def delete(pid: int):
    _g(pl.delete, pid)
    return {"deleted": pid}


@router.post("/{pid}/run")
def run(pid: int):
    return _g(pl.run, pid)


@router.get("/{pid}/history")
def history(pid: int, limit: int = Query(20, ge=1, le=50)):
    return {"runs": _g(pl.history, pid, limit)}
