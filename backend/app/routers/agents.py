from typing import Literal

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from app.routers import ai as ai_router
from app.services import agent_debate, agent_evals, agents, manuals, quizzes

router = APIRouter(tags=["agents"])


class Msg(BaseModel):
    role: Literal["user", "agent"]
    content: str = Field(max_length=4000)


class ChatIn(BaseModel):
    message: str = Field(min_length=2, max_length=1200)
    history: list[Msg] = Field(default_factory=list, max_length=20)
    step_id: str | None = None
    persona: Literal["default", "cfo", "math", "engmath"] = "default"
    provider: Literal["auto", "google", "openai", "anthropic", "ollama"] = "auto"
    effort: Literal["auto", "simple", "medium", "complex"] = "auto"
    source_text: str | None = Field(default=None, max_length=4000)      # text copied from a web page, labelled as an outside source
    source_url: str | None = Field(default=None, max_length=300)
    job_id: int | None = None                                           # the job pinned in the job bar, read-only for the agent


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
        r = agents.chat(track, body.message, [m.model_dump() for m in body.history], body.step_id, body.provider, None, body.effort, body.persona, body.source_text, body.source_url, body.job_id)
    except agents.AgentError as e:
        raise HTTPException(e.status, e.message) from None
    return {"reply": r.reply, "provider": r.provider, "model": r.model, "route": r.route, "proposals": r.proposals, "actions": r.actions,
            "tools_used": r.tools_used, "past_work": r.past_work, "examples": r.examples, "stopped_early": r.stopped_early, "usage": {"input_tokens": r.input_tokens, "output_tokens": r.output_tokens}}


class DebateIn(BaseModel):
    message: str = Field(min_length=2, max_length=1200)
    history: list[Msg] = Field(default_factory=list, max_length=20)
    job_id: int | None = None


def _dg(fn, *a, **k):
    try:
        return fn(*a, **k)
    except agent_debate.DebateError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/api/debate/status")
def debate_status():
    return agent_debate.status()


@router.put("/api/debate/config")
def debate_config(body: dict = Body(...)):
    return _dg(agent_debate.update_config, body)


@router.post("/api/agents/{track}/debate")
def debate(track: str, body: DebateIn):
    if track not in agents.AGENTS:
        raise HTTPException(404, "No agent for that discipline.")
    if agents.ai_policy.describe()["allowed"]:
        ai_router._check_rate()
    return _dg(agent_debate.run, track, body.message, [m.model_dump() for m in body.history], body.job_id)


class EvalIn(BaseModel):
    track: str
    mode: Literal["route", "knowledge", "live", "field"] = "route"
    provider: Literal["auto", "google", "openai", "anthropic", "ollama"] = "auto"
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


# ------------------------------------------------------------------ full work: the AI does the whole job
from app.services import ai_work  # noqa: E402


class WorkIn(BaseModel):
    question: str = Field(default="", max_length=600)
    source: str = Field(default="operations", min_length=1, max_length=120)
    provider: Literal["auto", "google", "openai", "anthropic", "ollama"] = "auto"
    kind: str = Field(default="complete", max_length=30)


@router.get("/api/agents/work/types")
def work_types():
    return {"types": [{"id": k, "label": v["label"]} for k, v in ai_work.TYPES.items()]}


@router.post("/api/agents/{role}/complete")
def complete(role: str, body: WorkIn):
    if role not in ai_work.ROLES:
        raise HTTPException(404, "Pick analyst, scientist or bi.")
    if agents.ai_policy.describe()["allowed"]:
        ai_router._check_rate()
    try:
        return ai_work.run(role, body.question, body.source, body.provider, kind=body.kind)
    except agents.AgentError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/api/agents/{role}/work")
def work_list(role: str):
    if role not in ai_work.ROLES:
        raise HTTPException(404, "Pick analyst, scientist or bi.")
    return {"items": ai_work.list_work(role)}


@router.delete("/api/agents/work/{work_id}")
def work_delete(work_id: str):
    ai_work.delete_work(work_id)
    return {"ok": True}


@router.get("/api/consistency")
def consistency_report():
    from app.services import consistency
    return consistency.run()


@router.get("/api/known-errors")
def known_errors_list(track: str | None = None):
    from app.services import known_errors
    return {"items": known_errors.public(track), "count": len(known_errors.public(track))}
