"""NLP + deep-learning agents workspace, and the 'type what you need' router."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import concierge, nlp_dl_studio as st

router = APIRouter(tags=["nlpdl"])


class RunIn(BaseModel):
    prompt: str = Field(default="", max_length=600)
    data: str = Field(default="", max_length=3_000_000)
    source: str = Field(default="", max_length=60)
    text_col: str = Field(default="", max_length=80)
    label_col: str = Field(default="", max_length=80)
    target: str = Field(default="", max_length=80)
    query: str = Field(default="", max_length=1000)
    agent: str = Field(default="", max_length=4)
    task: str = Field(default="", max_length=20)


@router.get("/api/nlp-dl/examples")
def examples():
    return {"examples": st.examples(), "limits": {"rows": st.MAX_ROWS, "mb": st.MAX_BYTES // 1_000_000}}


@router.post("/api/nlp-dl/run")
def run(b: RunIn):
    try:
        return st.run(b.prompt, b.data, b.source, b.text_col, b.label_col, b.target, b.query, b.agent, b.task)
    except st.StudioError as e:
        raise HTTPException(e.status, e.message) from e


@router.get("/api/concierge")
def ask(q: str = Query("", max_length=300)):
    return concierge.route(q)
