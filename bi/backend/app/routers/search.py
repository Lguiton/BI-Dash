from fastapi import APIRouter, Query

from app.services import search

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
def find(q: str = Query("", max_length=100), limit: int = 12):
    return search.search(q, limit)
