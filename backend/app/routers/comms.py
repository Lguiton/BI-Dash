"""Client message and outreach drafts. Nothing is sent."""
from fastapi import APIRouter, Body, HTTPException

from app.services import comms

router = APIRouter(prefix="/api/comms", tags=["comms"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except comms.CommsError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/kinds")
def kinds():
    return {"kinds": [{"id": k, "label": v} for k, v in comms.KINDS.items()]}


@router.post("/draft")
def draft(body: dict = Body(...)):
    return _g(comms.draft, str(body.get("kind") or "reply"), str(body.get("message") or ""), body.get("job_id") or None, str(body.get("name") or ""), bool(body.get("ai")))


@router.get("/week")
def week():
    return comms.week()


@router.post("/outreach")
def outreach(body: dict = Body(...)):
    return _g(comms.outreach, str(body.get("kind") or "checkin"), str(body.get("name") or ""), str(body.get("what") or ""), bool(body.get("ai")))
