"""AI Lab endpoints: ask a question, the agent queries the data with read-only SQL and answers."""
import threading
import time
from collections import deque
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import ai_policy, llm_router, state, study
from app.services.ai_agent import AiError

router = APIRouter(prefix="/api/ai", tags=["ai"])

# Every question costs real money, so cap the rate: 10 per minute for the whole server.
_LIMIT, _WINDOW = 10, 60.0
_calls: deque[float] = deque()
_lock = threading.Lock()


def _check_rate() -> None:
    now = time.monotonic()
    with _lock:
        while _calls and now - _calls[0] > _WINDOW:
            _calls.popleft()
        if len(_calls) >= _LIMIT:
            raise HTTPException(429, "Slow down: limit is 10 questions per minute.")
        _calls.append(now)


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    provider: Literal["auto", "google", "openai", "anthropic"] = "auto"
    effort: Literal["auto", "simple", "medium", "complex"] = "auto"


@router.get("/status")
def status():
    return {**llm_router.status(), "policy": ai_policy.describe()}


@router.get("/usage")
def usage(days: int = 14):
    from app.services import usage as usage_svc
    return usage_svc.summary(days)


@router.post("/ask")
def ask(body: AskIn):
    pol = ai_policy.describe()
    if not pol["allowed"]:
        state.audit("ai_ask", "blocked: AI is off for this workspace", ok=False)
        raise HTTPException(403, "AI is switched off for the Real workspace. Turn it on in Settings (choose 'summaries only' to keep row-level data private).")
    st = llm_router.status()
    if not st["ready"] and body.provider == "auto":
        raise HTTPException(503, "No AI provider is ready. Put GOOGLE_API_KEY, OPENAI_API_KEY and/or ANTHROPIC_API_KEY in "
                                 "backend/.env, install the SDKs (pip install -r requirements.txt) and restart the backend.")
    _check_rate()
    try:
        r = llm_router.ask(body.question, body.provider, body.effort)
    except AiError as e:
        raise HTTPException(e.status, str(e))
    state.audit("ai_ask", f"[{pol['mode']}] {r.provider}: {body.question[:200]}")
    study.log_ai(body.question, r.provider, r.model, (r.route or {}).get("kind", ""), r.input_tokens, r.output_tokens, True, r.chart is not None, (r.route or {}).get("kind", ""), "")
    return {"answer": r.answer, "model": r.model, "provider": r.provider, "stopped_early": r.stopped_early, "chart": r.chart,
            "route": getattr(r, "route", None), "attempts": r.attempts,
            "steps": [{"tool": s.tool, "input": s.input, "output": s.output, "is_error": s.is_error} for s in r.steps],
            "usage": {"input_tokens": r.input_tokens, "output_tokens": r.output_tokens}}
