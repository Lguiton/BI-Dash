"""Cookbook: cleaning recipes, SQL interview practice, pandas cheat sheet, learning sites. Runs only on a built-in sample."""
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import cookbook

router = APIRouter(prefix="/api/cookbook", tags=["cookbook"])


class RunIn(BaseModel):
    kind: Literal["recipe", "interview"]
    id: str


@router.get("")
def get_all():
    return cookbook.catalog()


@router.get("/sample/{table}")
def sample(table: str):
    try:
        return cookbook.sample_preview(table)
    except cookbook.CookError as e:
        raise HTTPException(404, str(e))


@router.post("/run")
def run(b: RunIn):
    try:
        return cookbook.run(b.kind, b.id)
    except cookbook.CookError as e:
        raise HTTPException(400, str(e))
