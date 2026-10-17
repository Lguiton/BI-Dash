"""Cloud and as-a-service lab: models, responsibility, picker, IaC templates and reviewer, checklist, quiz."""
from fastapi import APIRouter, Body, HTTPException

from app.services import cloud_lab

router = APIRouter(prefix="/api/cloud", tags=["cloud"])


def _g(fn, *a):
    try:
        return fn(*a)
    except cloud_lab.CloudError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/reference")
def reference():
    return cloud_lab.reference()


@router.get("/iac")
def iac():
    return {"lesson": cloud_lab.LESSON, "templates": cloud_lab.TEMPLATES, "checklist": cloud_lab.CHECKLIST, "note": cloud_lab.NOTE}


@router.post("/pick")
def pick(body: dict = Body(...)):
    return _g(cloud_lab.pick, str(body.get("need") or ""))


@router.post("/review")
def review(body: dict = Body(...)):
    return _g(cloud_lab.review, str(body.get("text") or ""))


@router.get("/quiz")
def quiz():
    return cloud_lab.quiz()


@router.post("/quiz/grade")
def grade(body: dict = Body(...)):
    a = body.get("answers")
    return cloud_lab.grade(a if isinstance(a, dict) else {})
