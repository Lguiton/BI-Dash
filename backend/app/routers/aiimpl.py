"""AI implementation planner endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import ai_impl as ai
from app.services import ai_vendor as av

router = APIRouter(prefix="/api/aiimpl", tags=["aiimpl"])


def _w(fn, *a):
    try:
        return fn(*a)
    except ai.ImplError as e:
        raise HTTPException(e.status, e.message) from e


class Scores(BaseModel):
    scores: dict[str, int]


class Checklist(BaseModel):
    done: dict[str, bool]


class Autonomy(BaseModel):
    error_cost: str
    reversible: str
    regulated: bool = False
    correct: int = Field(0, ge=0)
    reviewed: int = Field(0, ge=0)
    exception_pct: float = Field(0, ge=0, le=100)


class Exc(BaseModel):
    text: str = Field(max_length=100_000)


class Value(BaseModel):
    baseline: dict = {}
    current: dict = {}
    adoption_pct: float | None = None
    escalation_pct: float | None = None
    accuracy_pct: float | None = None
    tool_cost_per_month: float = 0
    volume_per_month: float = 0


@router.get("/reference")
def reference():
    return ai.reference()


@router.get("/sample")
def sample():
    return ai.SAMPLE


@router.get("/questions")
def questions():
    return ai.questions()


@router.post("/readiness")
def readiness(b: Scores):
    return _w(ai.readiness, b.scores)


@router.post("/checklist")
def checklist(b: Checklist):
    return _w(ai.checklist, b.done)


@router.post("/autonomy")
def autonomy(b: Autonomy):
    return _w(ai.autonomy, b.error_cost, b.reversible, b.regulated, b.correct, b.reviewed, b.exception_pct)


@router.post("/exceptions")
def exceptions(b: Exc):
    return _w(ai.exceptions, b.text)


@router.post("/value-check")
def value_check(b: Value):
    return _w(ai.value_check, b.baseline, b.current, b.adoption_pct, b.escalation_pct, b.accuracy_pct, b.tool_cost_per_month, b.volume_per_month)


class VendorIn(BaseModel):
    answers: dict[str, str]
    include_extra: bool = True


class VendorsIn(BaseModel):
    vendors: dict[str, dict[str, str]]
    include_extra: bool = True


def _v(fn, *a):
    try:
        return fn(*a)
    except av.VendorError as e:
        raise HTTPException(e.status, e.message) from e


@router.get("/vendor/reference")
def vendor_reference():
    return av.reference()


@router.get("/vendor/sample")
def vendor_sample():
    return av.SAMPLE


@router.post("/vendor/score")
def vendor_score(b: VendorIn):
    return _v(av.score, b.answers, b.include_extra)


@router.post("/vendor/compare")
def vendor_compare(b: VendorsIn):
    return _v(av.compare, b.vendors, b.include_extra)
