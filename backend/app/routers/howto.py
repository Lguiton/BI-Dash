"""How-to videos: links, chapters, notes, watched flags."""
from fastapi import APIRouter, Body, HTTPException

from app.services import howto as ht

router = APIRouter(prefix="/api/howto", tags=["howto"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except ht.HowtoError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("")
def listing():
    return ht.listing()


@router.get("/for-job/{job_id}")
def for_job(job_id: int):
    return _g(ht.for_job, job_id)


@router.post("/link")
def add_link(body: dict = Body(...)):
    return _g(ht.add_link, body)


@router.put("/{vid}")
def update(vid: int, body: dict = Body(...)):
    return _g(ht.update, vid, body)


@router.delete("/{vid}")
def delete(vid: int):
    return _g(ht.delete, vid)
