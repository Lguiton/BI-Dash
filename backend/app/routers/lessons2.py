"""Survey statistics, free-course catalog and leadership self-review endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import courses as co
from app.services import leadership as le
from app.services import survey_stats as ss

router = APIRouter(prefix="/api", tags=["lessons2"])


def _w(fn, *a):
    try:
        return fn(*a)
    except (ss.SurveyError, co.CourseError, le.LeaderError) as e:
        raise HTTPException(e.status, e.message) from e


class Prop(BaseModel):
    percent: float
    n: float
    confidence: int = 95


class Cmp(BaseModel):
    percent1: float
    n1: float
    percent2: float
    n2: float
    confidence: int = 95


class Size(BaseModel):
    margin_points: float
    confidence: int = 95
    expected_percent: float = 50


class Multi(BaseModel):
    text: str = Field(max_length=20_000)
    n: float | None = None


class Joint(BaseModel):
    text: str = Field(max_length=20_000)


class Done(BaseModel):
    done: bool


class Ratings(BaseModel):
    ratings: dict[str, list[float]]


@router.get("/surveystats/reference")
def ss_ref():
    return ss.reference()


@router.post("/surveystats/proportion")
def ss_prop(b: Prop):
    return _w(ss.proportion, b.percent, b.n, b.confidence)


@router.post("/surveystats/compare")
def ss_cmp(b: Cmp):
    return _w(ss.compare, b.percent1, b.n1, b.percent2, b.n2, b.confidence)


@router.post("/surveystats/sample-size")
def ss_size(b: Size):
    return _w(ss.sample_size, b.margin_points, b.confidence, b.expected_percent)


@router.post("/surveystats/multi-select")
def ss_multi(b: Multi):
    return _w(ss.multi_select, b.text, b.n)


@router.post("/surveystats/joint")
def ss_joint(b: Joint):
    return _w(ss.joint, b.text)


@router.get("/courses")
def courses(section: int | None = None, q: str = ""):
    return co.catalog(section, q)


@router.get("/courses/reference")
def courses_ref():
    return co.reference()


@router.get("/courses/path/{goal}")
def courses_path(goal: str):
    return _w(co.path, goal)


@router.put("/courses/{course_id}")
def courses_mark(course_id: int, b: Done):
    return _w(co.mark, course_id, b.done)


@router.get("/leadership/reference")
def lead_ref():
    return le.reference()


@router.post("/leadership/review")
def lead_review(b: Ratings):
    return _w(le.review, b.ratings)
