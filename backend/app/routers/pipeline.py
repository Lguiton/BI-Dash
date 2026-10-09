"""Pipeline monitor endpoints (see services/pipeline.py)."""
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import pipeline

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


class RunIn(BaseModel):
    source: Literal["clean", "messy", "uploaded"] = "clean"
    reset: bool = False


@router.get("")
def get_status():
    try:
        return pipeline.status()
    except ImportError as e:
        raise HTTPException(501, f"The pipeline monitor needs duckdb: pip install duckdb ({e.name})")


@router.post("/run")
def run(body: RunIn):
    try:
        entry = pipeline.run(body.source, body.reset)
    except pipeline.PipelineError as e:
        raise HTTPException(e.status, str(e))
    except ImportError as e:
        raise HTTPException(501, f"The pipeline needs duckdb: pip install duckdb ({e.name})")
    return {"run": entry, "status": pipeline.status()}
