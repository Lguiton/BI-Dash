"""Compliance library: summaries of privacy and security rules with official links."""
from fastapi import APIRouter, HTTPException

from app.services import compliance

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


@router.get("")
def library():
    return compliance.library()


@router.get("/search")
def search(q: str = "", limit: int = 5):
    return compliance.search(q, max(1, min(limit, 20)))


@router.get("/{law_id}")
def one(law_id: str):
    e = compliance.get(law_id)
    if not e:
        raise HTTPException(404, "No such entry.")
    return e
