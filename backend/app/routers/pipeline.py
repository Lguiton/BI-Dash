"""Pipeline monitor endpoints (see services/pipeline.py)."""
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import cdc, data_issues, de_design, pipeline, readiness
from app.services.datasets import DataError

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


class RunIn(BaseModel):
    source: Literal["clean", "messy", "uploaded"] = "clean"
    reset: bool = False
    gate: bool = False
    only_if_new: bool = False


@router.get("")
def get_status():
    try:
        return pipeline.status()
    except ImportError as e:
        raise HTTPException(501, f"The pipeline monitor needs duckdb: pip install duckdb ({e.name})")


@router.post("/run")
def run(body: RunIn):
    try:
        entry = pipeline.run(body.source, body.reset, gate=body.gate, only_if_new=body.only_if_new)
    except pipeline.PipelineError as e:
        raise HTTPException(e.status, str(e))
    except ImportError as e:
        raise HTTPException(501, f"The pipeline needs duckdb: pip install duckdb ({e.name})")
    return {"run": entry, "status": pipeline.status()}


class StoreIn(BaseModel):
    workload: str = "reporting"
    data: str = "structured"
    volume: str = "small"
    users: str = "few"
    realtime: bool = False


@router.get("/star")
def star(source: str):
    try:
        return de_design.suggest_star(source)
    except DataError as e:
        raise HTTPException(400, str(e)) from None


@router.post("/store")
def store(body: StoreIn):
    try:
        return de_design.choose_store(**body.model_dump())
    except DataError as e:
        raise HTTPException(400, str(e)) from None


@router.get("/metadata")
def metadata(search: str = ""):
    return de_design.metadata_view(search)


@router.get("/readiness")
def get_readiness():
    return {**readiness.scorecard(), "reviews": readiness.history()[::-1], "review_enabled": readiness.enabled()}


@router.post("/readiness/review")
def run_review():
    return readiness.review_now()


@router.put("/readiness/schedule")
def review_schedule(body: dict):
    return readiness.set_enabled(bool(body.get("enabled")))


def _issue(fn, *a):
    try:
        return fn(*a)
    except data_issues.IssueError as e:
        raise HTTPException(e.status, str(e)) from None


@router.get("/issues")
def issues(status: str | None = None):
    return data_issues.listing(status)


@router.post("/issues")
def issue_new(body: dict):
    return _issue(data_issues.create, body)


@router.patch("/issues/{iid}")
def issue_update(iid: str, body: dict):
    return _issue(data_issues.update, iid, body)


@router.delete("/issues/{iid}")
def issue_delete(iid: str):
    _issue(data_issues.delete, iid)
    return {"ok": True}


def _cdc(fn, *a):
    try:
        return fn(*a)
    except DataError as e:
        raise HTTPException(getattr(e, "status", 400), str(e)) from None


@router.post("/cdc/diff")
def cdc_diff(body: dict):
    return _cdc(cdc.snapshot_diff, str(body.get("old") or ""), str(body.get("new") or ""), list(body.get("key") or []), (body.get("create_feed") or None))


@router.post("/cdc/apply")
def cdc_apply(body: dict):
    return _cdc(cdc.apply_changes, str(body.get("feed") or ""), list(body.get("key") or []), str(body.get("op_col") or ""), str(body.get("seq_col") or ""),
                str(body.get("mode") or ""), str(body.get("new_table") or ""))
