"""Project and product management endpoints."""
from datetime import date, datetime

from fastapi import APIRouter, Body, HTTPException, Query

from app.services import pm

router = APIRouter(prefix="/api/pm", tags=["project-product"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except pm.PmError as e:
        raise HTTPException(e.status, e.message) from e


def _as_of(v: str | None) -> date | None:
    if not v:
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "as_of must be YYYY-MM-DD.") from None


@router.get("")
def overview(as_of: str | None = Query(None)):
    return pm.overview(_as_of(as_of))


@router.get("/product-analytics")
def product_analytics():
    return pm.product_analytics()


@router.post("/example")
def example():
    return _g(pm.load_example)


@router.post("/items")
def add_item(body: dict = Body(...)):
    return _g(pm.create_item, body)


@router.patch("/items/{iid}")
def edit_item(iid: int, body: dict = Body(...)):
    return _g(pm.update_item, iid, body)


@router.delete("/items/{iid}")
def remove_item(iid: int):
    _g(pm.delete_item, iid)
    return {"deleted": iid}


@router.post("/sprints")
def add_sprint(body: dict = Body(...)):
    return _g(pm.save_sprint, body)


@router.put("/sprints/{sid}")
def edit_sprint(sid: int, body: dict = Body(...)):
    return _g(pm.save_sprint, body, sid)


@router.delete("/sprints/{sid}")
def remove_sprint(sid: int):
    pm.delete_sprint(sid)
    return {"deleted": sid}


@router.post("/risks")
def add_risk(body: dict = Body(...)):
    return _g(pm.save_risk, body)


@router.put("/risks/{rid}")
def edit_risk(rid: int, body: dict = Body(...)):
    return _g(pm.save_risk, body, rid)


@router.delete("/risks/{rid}")
def remove_risk(rid: int):
    pm.delete_risk(rid)
    return {"deleted": rid}


@router.post("/okrs")
def add_okr(body: dict = Body(...)):
    return _g(pm.save_okr, body)


@router.put("/okrs/{oid}")
def edit_okr(oid: int, body: dict = Body(...)):
    return _g(pm.save_okr, body, oid)


@router.delete("/okrs/{oid}")
def remove_okr(oid: int):
    pm.delete_okr(oid)
    return {"deleted": oid}


@router.get("/time")
def time_get():
    return pm.time_view()


@router.post("/time")
def time_add(body: dict = Body(...)):
    _g(pm.time_log, body.get("item_id"), body.get("day"), body.get("hours"), body.get("note", ""))
    return pm.time_view()


@router.delete("/time/{tid}")
def time_del(tid: int):
    _g(pm.time_delete, tid)
    return pm.time_view()


@router.put("/rate")
def rate_put(body: dict = Body(...)):
    _g(pm.set_rate, body.get("rate"))
    return pm.time_view()
