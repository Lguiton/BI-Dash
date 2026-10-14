from fastapi import APIRouter, Body, HTTPException

from app.services import sysdesign as sd

router = APIRouter(prefix="/api/sysdesign", tags=["sysdesign"])


def _g(fn, *a):
    try:
        return fn(*a)
    except sd.DesignError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/options")
def options():
    return {"kinds": sd.KINDS, "needs": sd.NEEDS, "uptime": list(sd.UPTIME), "cases": {k: v["title"] for k, v in sd.CASES.items()}}


@router.post("/design")
def design(body: dict = Body(...)):
    return _g(sd.design, body)


@router.post("/capacity")
def capacity(body: dict = Body(...)):
    return _g(sd.capacity, body)


@router.post("/tradeoffs")
def tradeoffs(body: dict = Body(...)):
    return _g(sd.tradeoffs, body)


@router.post("/review")
def review(body: dict = Body(...)):
    return _g(sd.review, body)


@router.get("/practice")
def practice(kind: str = "booking", reveal: bool = False):
    return _g(sd.practice, kind, reveal)


@router.post("/practice/grade")
def grade(body: dict = Body(...)):
    return _g(sd.grade, body.get("kind"), body.get("answer"))
