"""Portfolio of completed practice and case-study notes."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.services import manuals, portfolio

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class CaseIn(BaseModel):
    track: str
    title: str = Field(max_length=200)
    problem: str = Field("", max_length=3000)
    actions: str = Field("", max_length=4000)
    result: str = Field("", max_length=3000)
    skills: str = Field("", max_length=600)


def _w(fn, *a, **k):
    try:
        return fn(*a, **k)
    except portfolio.PortfolioError as e:
        raise HTTPException(e.status, e.message) from e


@router.get("")
def get_portfolio():
    return portfolio.build()


@router.get("/markdown", response_class=PlainTextResponse)
def get_markdown(track: str | None = None):
    return PlainTextResponse(_w(portfolio.markdown, track), headers={"Content-Disposition": 'attachment; filename="skills-portfolio.md"'})


@router.get("/prompts/{track}")
def get_prompts(track: str):
    if track not in manuals.MANUALS:
        raise HTTPException(404, "No such discipline.")
    return {"prompts": portfolio.prompts(track)}


@router.get("/cases")
def list_cases(track: str | None = None):
    return {"cases": portfolio.cases(track)}


@router.post("/cases")
def add_case(b: CaseIn):
    return _w(portfolio.add_case, b.model_dump())


@router.put("/cases/{cid}")
def update_case(cid: str, b: CaseIn):
    return _w(portfolio.update_case, cid, b.model_dump())


@router.delete("/cases/{cid}")
def delete_case(cid: str):
    return _w(portfolio.delete_case, cid)
