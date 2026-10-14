from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import sql_lab
from app.services.sql_lab import SqlLabError

router = APIRouter(prefix="/api/sql", tags=["sql-lab"])


class Query(BaseModel):
    sql: str = Field(..., max_length=sql_lab.MAX_SQL_CHARS * 2)


def _err(e: SqlLabError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(e))


@router.get("/schema")
def schema():
    """Tables and views (with columns and row counts) available to query."""
    return {"objects": sql_lab.get_schema()}


@router.post("/run")
def run(q: Query):
    try:
        r = sql_lab.run_query(q.sql)
    except SqlLabError as e:
        raise _err(e)
    return {"columns": r.columns, "rows": r.rows, "row_count": r.row_count,
            "truncated": r.truncated, "elapsed_ms": r.elapsed_ms, "max_rows": sql_lab.MAX_ROWS}


@router.get("/exercises")
def exercises():
    return {"exercises": [
        {"id": e.id, "title": e.title, "level": e.level, "concepts": e.concepts,
         "prompt": e.prompt, "hint": e.hint, "ordered": e.ordered}
        for e in sql_lab.EXERCISES]}


def _get(ex_id: str) -> sql_lab.Exercise:
    ex = sql_lab.EXERCISES_BY_ID.get(ex_id)
    if not ex:
        raise HTTPException(404, "Unknown exercise")
    return ex


@router.post("/exercises/{ex_id}/check")
def check(ex_id: str, q: Query):
    ex = _get(ex_id)
    try:
        return sql_lab.check_answer(ex, q.sql)
    except SqlLabError as e:
        raise _err(e)


@router.get("/exercises/{ex_id}/solution")
def solution(ex_id: str):
    return {"id": ex_id, "solution": _get(ex_id).solution}
