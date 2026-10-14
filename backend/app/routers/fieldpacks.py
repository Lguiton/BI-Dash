"""Field packs API: extra professional fields (consulting, IT project management, DevOps, cloud, DevSecOps, security of revenue systems,
computer vision, UI/UX, marketing, revenue operations, health data, statistics, genomics, research)."""
from fastapi import APIRouter, Body, HTTPException

from app.services import fieldpacks as fp

router = APIRouter(prefix="/api/fieldpacks", tags=["fieldpacks"])


def _g(fn, *a):
    try:
        return fn(*a)
    except fp.PackError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("")
def packs():
    return {"packs": fp.listing()}


@router.get("/{pid}")
def pack_schema(pid: str):
    return _g(fp.schema, pid)


@router.post("/{pid}/{tid}")
def run(pid: str, tid: str, body: dict = Body(default={})):
    return _g(fp.run, pid, tid, body)
