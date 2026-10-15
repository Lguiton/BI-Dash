"""Work log: what you are working on, with a log under each item."""
from fastapi import APIRouter, Body, HTTPException, Query

from app.services import worklog as wl

router = APIRouter(prefix="/api/worklog", tags=["worklog"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except wl.WorkError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("")
def listing(include_done: bool = Query(False)):
    return wl.listing(include_done)


@router.post("")
def add(body: dict = Body(...)):
    return _g(wl.add, body)


@router.put("/{wid}")
def update(wid: int, body: dict = Body(...)):
    return _g(wl.update, wid, body)


@router.post("/{wid}/log")
def log(wid: int, body: dict = Body(...)):
    return _g(wl.add_log, wid, body.get("text"))


@router.post("/{wid}/timer/start")
def timer_start(wid: int):
    return _g(wl.start_timer, wid)


@router.post("/{wid}/timer/stop")
def timer_stop(wid: int):
    return _g(wl.stop_timer, wid)


@router.delete("/{wid}")
def delete(wid: int):
    return _g(wl.delete, wid)
