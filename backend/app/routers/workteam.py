"""Work team: three AIs draft a job, one judges. Plus practice kits (materials for practice jobs)."""
from fastapi import APIRouter, Body, HTTPException

from app.services import workteam as wt

router = APIRouter(prefix="/api/workteam", tags=["workteam"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except wt.TeamError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/status")
def status():
    return wt.status()


@router.put("/config")
def config(body: dict = Body(...)):
    return _g(wt.update_config, body)


@router.post("/run")
def run(body: dict = Body(...)):
    try:
        jid = int(body.get("job_id"))
    except (TypeError, ValueError):
        raise HTTPException(400, "Choose a job first.") from None
    return _g(wt.run, jid, str(body.get("instructions") or ""), str(body.get("material") or ""))


@router.get("/kit/{jid}")
def kit(jid: int):
    return {"kit": _g(wt.kit_for_job, jid)}


@router.get("/kit/{jid}/answer")
def kit_answer(jid: int):
    return _g(wt.kit_answer, jid)
