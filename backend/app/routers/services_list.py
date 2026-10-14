"""Your service list and a quick quote builder."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import service_catalog

router = APIRouter(prefix="/api/service-list", tags=["services"])


class Line(BaseModel):
    id: str = Field(max_length=40)
    qty: int = Field(default=1, ge=1, le=50)


class QuoteIn(BaseModel):
    lines: list[Line] = Field(max_length=40)
    client: str = Field(default="", max_length=80)
    discount_pct: float = Field(default=0, ge=0, le=50)


@router.get("")
def get_catalog():
    return service_catalog.catalog()


@router.put("/rates")
def put_rates(body: dict[str, float]):
    try:
        service_catalog.set_rates(body)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return service_catalog.catalog()


@router.post("/quote")
def post_quote(b: QuoteIn):
    try:
        return service_catalog.quote([x.model_dump() for x in b.lines], b.client, b.discount_pct)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
