"""Computer science lab: Big-O estimate, algorithm step-through, cheat sheet. Local, never runs pasted code."""
from fastapi import APIRouter, Body, HTTPException

from app.services import cs_lab

router = APIRouter(prefix="/api/cs", tags=["cs"])


def _g(fn, *a):
    try:
        return fn(*a)
    except cs_lab.CsError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/reference")
def reference():
    return cs_lab.reference()


@router.post("/complexity")
def complexity(body: dict = Body(...)):
    return _g(cs_lab.complexity, str(body.get("code") or ""))


@router.post("/sort")
def sort(body: dict = Body(...)):
    return _g(cs_lab.sort_steps, str(body.get("algorithm") or "bubble"), body.get("data") or "")


@router.post("/search")
def search(body: dict = Body(...)):
    return _g(cs_lab.search_steps, str(body.get("algorithm") or "linear"), body.get("data") or "", body.get("target"))
