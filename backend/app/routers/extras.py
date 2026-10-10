"""Small read-only helpers: knowledge search, tool map, LLM monitoring."""
from fastapi import APIRouter, Query

from app.services import kb, metrics, toolmap

router = APIRouter(prefix="/api", tags=["extras"])


@router.get("/kb")
def kb_search(q: str = Query("", max_length=200), limit: int = Query(8, ge=1, le=20)):
    return kb.search(q, limit)


@router.get("/toolmap")
def tool_map():
    return toolmap.tool_map()


@router.get("/ops/llm")
def llm_monitor(days: int = Query(7, ge=1, le=90)):
    return metrics.llm_summary(days)


from pydantic import BaseModel, Field  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from app.services import webreader, webtable  # noqa: E402


class UrlIn(BaseModel):
    url: str = Field(min_length=8, max_length=500)


class BookmarksIn(BaseModel):
    items: list[dict] = Field(max_length=webreader.MAX_BOOKMARKS)


@router.post("/web/read")
def web_read(body: UrlIn):
    """Text reader view of a public https page (the live panel in the browser doesn't use this)."""
    try:
        return webreader.read(body.url)
    except webtable.WebTableError as e:
        raise HTTPException(e.status, e.message) from e


@router.get("/web/bookmarks")
def web_bookmarks():
    return {"items": webreader.bookmarks()}


@router.put("/web/bookmarks")
def web_bookmarks_save(body: BookmarksIn):
    try:
        return {"items": webreader.save_bookmarks(body.items)}
    except webtable.WebTableError as e:
        raise HTTPException(e.status, e.message) from e
