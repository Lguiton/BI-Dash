"""Spaced review of the track quizzes: daily session, answering, weak spots."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import review

router = APIRouter(prefix="/api/review", tags=["review"])


class AnswerIn(BaseModel):
    id: str
    picked: int


def _w(fn, *a, **k):
    try:
        return fn(*a, **k)
    except review.ReviewError as e:
        raise HTTPException(e.status, e.message) from e


@router.get("/summary")
def summary():
    return review.summary()


@router.get("/session")
def session(n: int = 10, track: str | None = None):
    return _w(review.session, n, track)


@router.post("/answer")
def answer(b: AnswerIn):
    return _w(review.answer, b.id, b.picked)


@router.get("/weak")
def weak():
    return {"weak": review.weak_spots(30)}
