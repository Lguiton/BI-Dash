from fastapi import APIRouter, Body, HTTPException

from app.services import company

router = APIRouter(prefix="/api/company", tags=["company"])


def _g(fn, *a):
    try:
        return fn(*a)
    except company.CoError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("")
def overview():
    return company.overview()


@router.put("/brief")
def brief(body: dict = Body(...)):
    return company.brief_save(body)


@router.put("/deliverables/{did}")
def deliverable(did: str, body: dict = Body(...)):
    return _g(company.set_done, did, bool(body.get("done")))
