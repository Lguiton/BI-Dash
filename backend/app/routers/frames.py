"""Security frameworks (principles, CIA, NIST CSF) and network design/glossary."""
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import net_design as nd, sec_frame as sf

router = APIRouter(prefix="/api/frames", tags=["frames"])


def _w(fn, *a):
    try:
        return fn(*a)
    except (sf.FrameError, nd.DesignError) as e:
        raise HTTPException(e.status, e.message) from e


class TextIn(BaseModel):
    text: str = Field(max_length=25_000)


class AnswersIn(BaseModel):
    answers: dict[str, str]


class PlanIn(BaseModel):
    spec: dict[str, Any]


@router.get("/principles")
def principles():
    return {"principles": sf.PRINCIPLES, "cia": sf.CIA, "slips": sf.SLIPS}


@router.post("/principles/review")
def principles_review(b: TextIn):
    return _w(sf.review, b.text)


@router.post("/cia")
def cia(b: TextIn):
    return _w(sf.classify, b.text)


@router.get("/csf")
def csf():
    return sf.csf_questions()


@router.post("/csf/score")
def csf_score(b: AnswersIn):
    return _w(sf.csf_score, b.answers)


@router.post("/design/plan")
def design_plan(b: PlanIn):
    return _w(nd.plan, b.spec)


@router.get("/design/sample")
def design_sample():
    return {"spec": {"groups": [{"name": "Office", "hosts": 40}, {"name": "Warehouse", "hosts": 15}, {"name": "Reception", "hosts": 6}],
                     "growth_pct": 25, "sites": 1, "base": "10.20.0.0/16", "redundancy": "links", "wifi": True, "guest_wifi": True, "remote_access": True},
            "text": "Admin page lives at a hidden URL so nobody will find it. All staff have full access to the file server. Security will be added before launch.",
            "incident": "A flood of half-open connection requests took the booking site offline for two hours."}


@router.get("/glossary")
def glossary(q: str = ""):
    return nd.glossary(q[:60])


@router.get("/ports")
def ports():
    return nd.ports()


@router.get("/design/steps")
def steps():
    return {"steps": [{"id": a, "step": b, "detail": c} for a, b, c in nd.STEPS], "slips": nd.SLIPS}
