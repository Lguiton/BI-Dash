"""The Today screen."""
from fastapi import APIRouter

from app.services import today

router = APIRouter(prefix="/api/today", tags=["today"])


@router.get("")
def get():
    return today.build()
