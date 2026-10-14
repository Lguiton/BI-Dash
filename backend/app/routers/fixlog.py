"""Fix log: record each fix, find past fixes, and write them up."""
from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse

from app.services import fixlog as fl

router = APIRouter(prefix="/api/fixlog", tags=["fixlog"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except fl.FixError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("")
def listing(area: str | None = Query(None, max_length=20)):
    return _g(fl.listing, area)


@router.get("/search")
def search(q: str = Query("", max_length=200), area: str | None = Query(None, max_length=20)):
    return _g(fl.search, q, area)


@router.get("/export")
def export(area: str | None = Query(None, max_length=20)):
    return HTMLResponse(_g(fl.export_all, area))


@router.get("/draft/ticket/{tid}")
def draft(tid: int):
    return _g(fl.draft_from_ticket, tid)


@router.post("")
def add(body: dict = Body(...)):
    return _g(fl.add, body)


@router.get("/{fid}/doc")
def doc(fid: int, format: str = Query("md", pattern="^(md|html)$"), client: bool = False):
    if format == "html":
        return HTMLResponse(_g(fl.page, fid, client))
    return PlainTextResponse(_g(fl.markdown, fid, client), media_type="text/markdown")


@router.get("/{fid}")
def one(fid: int):
    return _g(fl.get, fid)


@router.put("/{fid}")
def put(fid: int, body: dict = Body(...)):
    return _g(fl.update, fid, body)


@router.delete("/{fid}")
def delete(fid: int):
    _g(fl.delete, fid)
    return {"ok": True}
