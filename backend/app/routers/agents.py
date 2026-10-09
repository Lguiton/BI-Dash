from typing import Literal

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from app.routers import ai as ai_router
from app.services import agent_evals, agents, manuals, quizzes

router = APIRouter(tags=["agents"])


class Msg(BaseModel):
    role: Literal["user", "agent"]
    content: str = Field(max_length=4000)


class ChatIn(BaseModel):
    message: str = Field(min_length=2, max_length=1200)
    history: list[Msg] = Field(default_factory=list, max_length=20)
    step_id: str | None = None
    provider: Literal["auto", "google", "openai", "anthropic"] = "auto"
    effort: Literal["auto", "simple", "medium", "complex"] = "auto"


@router.get("/api/manuals/{track}")
def manual(track: str):
    m = manuals.get(track)
    if not m:
        raise HTTPException(404, "No manual for that discipline.")
    return m


@router.put("/api/manuals/{track}/steps/{step}")
def tick(track: str, step: str, body: dict = Body(...)):
    m = manuals.set_done(track, step, bool(body.get("done")))
    if not m:
        raise HTTPException(404, "No such step.")
    return m


@router.get("/api/agents/{track}")
def agent_info(track: str):
    if track not in agents.AGENTS:
        raise HTTPException(404, "No agent for that discipline.")
    return agents.info(track)


@router.post("/api/agents/{track}/chat")
def chat(track: str, body: ChatIn):
    if track not in agents.AGENTS:
        raise HTTPException(404, "No agent for that discipline.")
    pol_ok = agents.ai_policy.describe()["allowed"]
    if pol_ok:
        ai_router._check_rate()
    try:
        r = agents.chat(track, body.message, [m.model_dump() for m in body.history], body.step_id, body.provider, None, body.effort)
    except agents.AgentError as e:
        raise HTTPException(e.status, e.message) from None
    return {"reply": r.reply, "provider": r.provider, "model": r.model, "route": r.route, "proposals": r.proposals, "actions": r.actions,
            "tools_used": r.tools_used, "stopped_early": r.stopped_early, "usage": {"input_tokens": r.input_tokens, "output_tokens": r.output_tokens}}


class EvalIn(BaseModel):
    track: str
    mode: Literal["route", "live"] = "route"
    provider: Literal["auto", "google", "openai", "anthropic"] = "auto"
    confirm: bool = False


@router.get("/api/agent-evals")
def evals_overview():
    return agent_evals.overview()


@router.post("/api/agent-evals/run")
def evals_run(body: EvalIn):
    try:
        return agent_evals.run(body.track, body.mode, body.provider, body.confirm)
    except agent_evals.EvalError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/api/quizzes/{track}")
def quiz_get(track: str):
    try:
        return quizzes.get(track)
    except quizzes.QuizError as e:
        raise HTTPException(e.status, e.message) from None


@router.post("/api/quizzes/{track}")
def quiz_submit(track: str, body: dict = Body(...)):
    try:
        return quizzes.submit(track, body.get("answers"))
    except quizzes.QuizError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/api/quizzes")
def quiz_all():
    r = quizzes._results()
    return {"tracks": {t: {"questions": len(q), "result": r.get(t)} for t, q in quizzes.QUIZZES.items()}, "pass_pct": quizzes.PASS_PCT}
