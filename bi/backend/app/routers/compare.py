from fastapi import APIRouter

from app.services import compare

router = APIRouter(prefix="/api/compare", tags=["compare"])


@router.get("")
def get_compare():
    return compare.compare()
