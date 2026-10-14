"""AI Lab endpoints: ask a question, the agent queries the data with read-only SQL and answers."""
import threading
import time
from collections import deque
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import ai_policy, inference_lab, llm_router, state, study
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
    t0 = time.perf_counter()
    try:
        r = llm_router.ask(body.question, body.provider, body.effort)
    except AiError as e:
        raise HTTPException(e.status, str(e))
    state.audit("ai_ask", f"[{pol['mode']}] {r.provider}: {body.question[:200]}")
    study.log_ai(body.question, r.provider, r.model, (r.route or {}).get("kind", ""), r.input_tokens, r.output_tokens, True, r.chart is not None, (r.route or {}).get("kind", ""), "", round(time.perf_counter() - t0, 2))
    return {"answer": r.answer, "model": r.model, "provider": r.provider, "stopped_early": r.stopped_early, "chart": r.chart,
            "route": getattr(r, "route", None), "attempts": r.attempts,
            "steps": [{"tool": s.tool, "input": s.input, "output": s.output, "is_error": s.is_error} for s in r.steps],
            "usage": {"input_tokens": r.input_tokens, "output_tokens": r.output_tokens}}


# ---------------------------------------------------------------- Inference Lab (calculators; nothing here calls a model)
def _inf(fn, *a, **k):
    try:
        return fn(*a, **k)
    except inference_lab.InfError as e:
        raise HTTPException(e.status, e.message) from e


@router.get("/inference/catalog")
def inference_catalog():
    return inference_lab.catalog()


@router.post("/inference/fit")
def inference_fit(body: dict):
    return _inf(inference_lab.fit, body.get("params_b"), str(body.get("precision", "fp16")), str(body.get("gpu", "h100")), body.get("n_gpus", 1),
                body.get("custom"), body.get("layers"), body.get("kv_heads"), body.get("head_dim"), body.get("context"), body.get("batch", 1), body.get("kv_precision"))


@router.post("/inference/bottleneck")
def inference_bottleneck(body: dict):
    return _inf(inference_lab.bottleneck, body.get("params_b"), str(body.get("precision", "fp16")), str(body.get("gpu", "h100")), body.get("custom"),
                body.get("input_tokens", 1000), body.get("batch", 1), body.get("active_params_b"), body.get("n_gpus", 1))


@router.post("/inference/latency")
def inference_latency(body: dict):
    return _inf(inference_lab.latency_stats, body.get("text"), None, None, None, body.get("duration_s"))


@router.post("/inference/cost")
def inference_cost(body: dict):
    return _inf(inference_lab.cost, body.get("input_m"), body.get("output_m"), body.get("price_in"), body.get("price_out"), body.get("gpus", 1),
                body.get("gpu_hour", 0), body.get("hours", 730), body.get("total_tps"), body.get("utilization_pct", 50), body.get("eng_hours", 0), body.get("eng_rate", 0))


@router.post("/inference/speculative")
def inference_speculative(body: dict):
    return _inf(inference_lab.speculative, body.get("acceptance"), body.get("draft_len", 4), body.get("draft_cost", 0.1))


@router.post("/inference/scaling")
def inference_scaling(body: dict):
    return _inf(inference_lab.scaling, body.get("requests_per_s"), body.get("avg_latency_s"), body.get("concurrency"), body.get("target_pct", 70),
                body.get("spike", 1), body.get("cold_start_s", 0))


@router.post("/inference/quantization")
def inference_quant(body: dict):
    return _inf(inference_lab.quant_table, body.get("params_b"))
