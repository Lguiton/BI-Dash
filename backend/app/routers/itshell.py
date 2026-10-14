"""Practice shell endpoints (simulated; nothing touches the real system)."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import it_shell as s

router = APIRouter(prefix="/api/itshell", tags=["itshell"])


def _w(fn, *a):
    try:
        return fn(*a)
    except s.ShellError as e:
        raise HTTPException(e.status, e.message) from e


class RunIn(BaseModel):
    command: str = Field(max_length=400)


@router.get("")
def view():
    return s.view()


@router.post("/run")
def run(b: RunIn):
    return _w(s.run, b.command)


@router.post("/reset")
def reset():
    return s.reset()


@router.get("/solution")
def solution(task: str = Query(max_length=20)):
    return _w(s.solution, task)
