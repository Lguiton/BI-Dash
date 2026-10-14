"""Cowrie honeypot log reader."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import honeypot as h

router = APIRouter(prefix="/api/honeypot", tags=["honeypot"])


class LogIn(BaseModel):
    text: str = Field(max_length=h.MAX_CHARS + 1000)


@router.post("/analyze")
def analyze(b: LogIn):
    try:
        return h.analyze(b.text)
    except h.HpError as e:
        raise HTTPException(e.status, e.message) from e


@router.get("/reference")
def reference():
    return h.reference()
