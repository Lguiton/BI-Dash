"""Advanced labs for the Computer Engineer, Full-stack, PM, Systems Analyst, AI, ML, Data Engineer and Data Scientist dashboards."""
from fastapi import APIRouter, Body, HTTPException

from app.services import prolab, prolab_all  # noqa: F401  (prolab_all registers every lab)

router = APIRouter(prefix="/api/prolab", tags=["prolab"])


@router.get("")
def index():
    return {"tracks": prolab.tracks()}


@router.get("/{track}")
def spec(track: str):
    try:
        return prolab.spec(track)
    except prolab.ProError as e:
        raise HTTPException(e.status, e.message) from None


@router.post("/{track}/run/{tid}")
def run(track: str, tid: str, b: dict = Body(default={})):
    try:
        return prolab.run(track, tid, b or {})
    except prolab.ProError as e:
        raise HTTPException(e.status, e.message) from None
