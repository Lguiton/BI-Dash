"""Data tools lab: dbt-style models, spreadsheet formulas, task graph scheduler, cron and stream simulators."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import data_calc, data_dbt, data_flow
from app.services.data_dbt import DataLabError

router = APIRouter(prefix="/api/datalab", tags=["datalab"])


def _w(fn, *a, **k):
    try:
        return fn(*a, **k)
    except DataLabError as e:
        raise HTTPException(e.status, e.message) from e


class Dbt(BaseModel):
    seeds: str = Field(default="", max_length=60000)
    models: str = Field(max_length=60000)
    tests: str = Field(default="", max_length=10000)


class Cells(BaseModel):
    cells: str = Field(max_length=40000)


class Dag(BaseModel):
    tasks: str = Field(max_length=10000)
    workers: int = 2


class Cron(BaseModel):
    expression: str = Field(max_length=100)
    start: str = Field(default="", max_length=30)
    count: int = 5


class Stream(BaseModel):
    events: str = Field(max_length=20000)
    partitions: int = 3
    consumers: int = 2
    window: int = 10
    kind: str = "tumbling"
    lateness: int = 2
    slide: int = 5
    gap: int = 4


@router.get("/reference")
def reference():
    return data_dbt.reference()


@router.post("/dbt")
def dbt(b: Dbt):
    return _w(data_dbt.run, b.seeds, b.models, b.tests)


@router.post("/formulas")
def formulas(b: Cells):
    return _w(data_calc.evaluate, b.cells)


@router.post("/dag")
def dag(b: Dag):
    return _w(data_flow.dag, b.tasks, b.workers)


@router.post("/cron")
def cron(b: Cron):
    return _w(data_flow.cron, b.expression, b.start, b.count)


@router.post("/stream")
def stream(b: Stream):
    return _w(data_flow.stream, **b.model_dump())
