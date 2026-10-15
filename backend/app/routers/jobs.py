"""One page per job: overview, close (with optional invoice), and a client summary."""
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import HTMLResponse

from app.services import clients as cl
from app.services import jobpage as jobs

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except cl.ClientError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/{jid}")
def overview(jid: int):
    return _g(jobs.overview, jid)


@router.post("/{jid}/close")
def close(jid: int, body: dict = Body(default={})):
    return _g(jobs.close, jid, str(body.get("bill") or "time"))


@router.get("/{jid}/summary")
def summary(jid: int):
    return HTMLResponse(_g(jobs.summary_html, jid), headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})
