"""Windows endpoint hardening audit: a read-only script to run yourself, and a grader for its output."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import endpoint_audit as ea

router = APIRouter(prefix="/api/endpoint", tags=["endpoint"])


class GradeIn(BaseModel):
    text: str = Field(max_length=ea.MAX_CHARS + 1000)


@router.get("/script")
def script():
    return {"script": ea.script(), "checks": len(ea.CHECKS)}


@router.post("/grade")
def grade(b: GradeIn):
    try:
        return ea.grade(b.text)
    except ea.EndpointError as e:
        raise HTTPException(e.status, e.message) from e


@router.get("/reference")
def reference():
    return ea.reference()
