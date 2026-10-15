"""Lead tracker."""
from fastapi import APIRouter, Body, HTTPException

from app.services import clients as cl
from app.services import leads

router = APIRouter(prefix="/api/leads", tags=["leads"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except cl.ClientError as e:
        raise HTTPException(e.status, e.message) from None
    except (TypeError, ValueError):
        raise HTTPException(400, "Check the numbers and ids you sent.") from None


@router.get("")
def listing():
    return leads.listing()


@router.get("/stats")
def stats():
    return leads.stats()


@router.post("")
def add(body: dict = Body(...)):
    return _g(leads.add, body)


@router.put("/{lid}")
def update(lid: int, body: dict = Body(...)):
    return _g(leads.update, lid, body)


@router.delete("/{lid}")
def delete(lid: int):
    return _g(leads.delete, lid)


@router.post("/{lid}/win")
def win(lid: int, body: dict = Body(default={})):
    return _g(leads.win, lid, body)
