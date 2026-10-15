"""Triage checklists you tick off on a job."""
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import Response

from app.services import checklists as ck
from app.services import pdfdocs

router = APIRouter(prefix="/api/checklists", tags=["checklists"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except ck.CheckError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("")
def templates():
    return ck.templates()


@router.get("/job/{job_id}")
def for_job(job_id: int):
    return _g(ck.for_job, job_id)


@router.post("/job/{job_id}/{tid}")
def start(job_id: int, tid: str):
    return _g(ck.start, job_id, tid)


@router.put("/job/{job_id}/{tid}")
def save(job_id: int, tid: str, body: dict = Body(...)):
    return _g(ck.save, job_id, tid, body)


@router.delete("/job/{job_id}/{tid}")
def remove(job_id: int, tid: str):
    return _g(ck.remove, job_id, tid)


@router.get("/job/{job_id}/{tid}/pdf")
def job_pdf(job_id: int, tid: str):
    """The checklist as it stands on this job: ticks, notes and the job title."""
    j = _g(ck._job, job_id)
    t = _g(ck._tpl, tid)
    st = ck._state().get(str(job_id), {}).get(tid)
    if st is None:
        raise HTTPException(404, "Start this checklist on the job first.")
    data, name = pdfdocs.checklist(t, set(st.get("checked", [])), st.get("notes", ""), j.get("title", ""))
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/{tid}/pdf")
def blank_pdf(tid: str):
    """A blank copy to print and fill in by hand."""
    data, name = pdfdocs.checklist(_g(ck._tpl, tid))
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})
