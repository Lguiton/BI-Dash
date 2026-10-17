"""Robotics lab: calculators, simulators and reference."""
from fastapi import APIRouter, Body, HTTPException

from app.services import robotics

router = APIRouter(prefix="/api/robotics", tags=["robotics"])


@router.get("/reference")
def reference():
    return robotics.reference()


@router.post("/calc/{kind}")
def calc(kind: str, body: dict = Body(default={})):
    try:
        return robotics.calc(kind, body)
    except robotics.RoboError as e:
        raise HTTPException(e.status, e.message) from None
