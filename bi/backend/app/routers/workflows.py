"""Workflow builder endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import state, workflows

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except workflows.WorkflowError as e:
        raise HTTPException(e.status, str(e)) from e


class StepsIn(BaseModel):
    steps: list[dict] = Field(min_length=1, max_length=workflows.MAX_STEPS + 1)
    limit: int = Field(workflows.PREVIEW_ROWS, ge=1, le=1000)


class SaveIn(BaseModel):
    name: str = Field(max_length=80)
    steps: list[dict] = Field(min_length=1, max_length=workflows.MAX_STEPS + 1)
    id: int | None = None


class TableIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    steps: list[dict] = Field(min_length=1, max_length=workflows.MAX_STEPS + 1)


@router.get("/sources")
def sources():
    out = []
    for s in workflows.sources():
        try:
            cols = workflows._columns(s["table"])
        except workflows.WorkflowError:
            continue
        out.append({**s, "columns": [{"name": n, "type": t, "kind": workflows.datasets.kind_of(t)} for n, t in cols.items()]})
    return {"sources": out}


@router.post("/explain")
def explain(body: StepsIn):
    return _g(workflows.explain, body.steps)


@router.post("/run")
def run(body: StepsIn):
    return _g(workflows.run, body.steps, body.limit)


@router.post("/save-table")
def save_table(body: TableIn):
    out = _g(workflows.save_as_table, body.steps, body.name)
    state.audit("workflow_to_table", f"{out['table']}: {out['rows']} rows")
    return out


@router.get("")
def saved():
    return {"workflows": workflows.list_saved()}


@router.post("")
def save(body: SaveIn):
    return _g(workflows.save, body.name, body.steps, body.id)


@router.delete("/{wid}")
def delete(wid: int):
    _g(workflows.delete, wid)
    return {"deleted": wid}
