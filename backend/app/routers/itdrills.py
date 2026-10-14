"""Graded IT fundamentals drills."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import it_drills as d

router = APIRouter(prefix="/api/itdrills", tags=["itdrills"])


def _w(fn, *a):
    try:
        return fn(*a)
    except d.DrillError as e:
        raise HTTPException(e.status, e.message) from e


class GradeIn(BaseModel):
    answers: dict[str, str] = Field(max_length=60)


@router.get("")
def questions(kind: str = Query("", max_length=12), n: int = Query(10, ge=1, le=30), seed: int = 0):
    return _w(d.questions, kind, n, seed)


@router.post("/grade")
def grade(b: GradeIn):
    return _w(d.grade, b.answers)


@router.get("/progress")
def progress():
    return d.progress()


@router.delete("/results")
def reset():
    return d.reset()
