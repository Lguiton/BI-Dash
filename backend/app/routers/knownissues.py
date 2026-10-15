"""Known issues (CISA KEV) and support dates (endoflife.date)."""
from fastapi import APIRouter, HTTPException, Query

from app.services import knownissues as ki

router = APIRouter(prefix="/api/known-issues", tags=["known-issues"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except ki.IssueError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/kev")
def kev(q: str = Query("", max_length=120), limit: int = Query(25, ge=1, le=100)):
    return _g(ki.kev_search, q, limit)


@router.get("/eol")
def eol(product: str = Query(..., max_length=60), cycle: str = Query("", max_length=40)):
    return _g(ki.eol_lookup, product, cycle)


@router.get("/products")
def products():
    return {"products": ki.PRODUCTS}
