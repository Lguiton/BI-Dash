"""Saved data sources and their refresh history."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import source_dirs
from app.services import sources

router = APIRouter(prefix="/api/sources", tags=["sources"])


class SourceBody(BaseModel):
    name: str
    kind: str
    config: dict
    target: str = ""
    load: str = "table"
    mode: str = "replace"
    interval_minutes: int = 0


class TestBody(BaseModel):
    kind: str
    config: dict


class WebBody(BaseModel):
    url: str


@router.post("/web-tables")
def web_tables(body: WebBody):
    """List the tables found on a public https page, so you can pick the table number."""
    from app.services import webtable
    try:
        return webtable.preview(body.url)
    except webtable.WebTableError as e:
        raise HTTPException(e.status, e.message) from e


class PatchBody(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    interval_minutes: int | None = None


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except sources.SourceError as e:
        raise HTTPException(e.status, e.message) from e


@router.get("")
def list_all():
    return {"sources": sources.list_sources()}


@router.get("/files")
def files():
    out = []
    for root in source_dirs():
        if root.is_dir():
            for p in sorted(root.iterdir()):
                if p.is_file() and p.suffix.lower() in (".csv", ".tsv", ".txt", ".xlsx", ".xlsm", ".json", ".sqlite", ".db"):
                    out.append({"name": p.name, "folder": str(root), "path": p.name if root == source_dirs()[0] else str(p), "size_bytes": p.stat().st_size})
    return {"folders": [str(r) for r in source_dirs()], "files": out}


@router.post("/test")
def test(body: TestBody):
    return _g(sources.preview, body.kind, body.config)


@router.post("")
def create(body: SourceBody):
    return _g(sources.create, body.name, body.kind, body.config, body.target, body.load, body.mode, body.interval_minutes)


@router.patch("/{sid}")
def patch(sid: int, body: PatchBody):
    return _g(sources.update, sid, body.model_dump(exclude_none=True))


@router.delete("/{sid}")
def remove(sid: int):
    _g(sources.delete, sid)
    return {"deleted": sid}


@router.post("/{sid}/run")
def run(sid: int):
    return _g(sources.run_source, sid)


@router.get("/{sid}/runs")
def history(sid: int):
    return {"runs": _g(sources.runs, sid)}
