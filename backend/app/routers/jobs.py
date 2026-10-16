"""One page per job: overview, close (with optional invoice), and a client summary."""
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import HTMLResponse, Response

from app.services import clients as cl
from app.services import jobfield, job_intake
from app.services.worklog import WorkError
from app.services import jobpage as jobs

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except (cl.ClientError, WorkError) as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/fields/list")
def fields_list():
    return {"fields": [jobfield.info(k) for k in jobfield.keys()]}


@router.get("/fields/guess")
def fields_guess(title: str = ""):
    return {"field": jobfield.info(jobfield.guess(title))}


@router.post("/quick-start")
def quick_start(body: dict = Body(...)):
    return _g(jobs.quick_start, str(body.get("title") or ""), str(body.get("client") or ""), body.get("client_id"), body.get("field") or None, body.get("steps") is not False, body.get("due") or None, body.get("quote") or None)


@router.post("/intake")
def intake_read(body: dict = Body(...)):
    """Read pasted client text into a suggested job. Suggestions only; nothing is created."""
    try:
        return job_intake.read(str(body.get("text") or ""))
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@router.get("/{jid}")
def overview(jid: int):
    return _g(jobs.overview, jid)


@router.post("/{jid}/close")
def close(jid: int, body: dict = Body(default={})):
    return _g(jobs.close, jid, str(body.get("bill") or "time"))


@router.get("/{jid}/summary.pdf")
def summary_pdf(jid: int):
    data, name = _g(jobs.summary_pdf, jid)
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/{jid}/summary")
def summary(jid: int):
    return HTMLResponse(_g(jobs.summary_html, jid), headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})
