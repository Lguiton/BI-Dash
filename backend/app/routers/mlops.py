"""MLOps lab endpoints (promotion gate, champion/challenger, rollout practice, load test, retrain advice, LLM approach, feedback)."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import mlops_lab as ml

router = APIRouter(prefix="/api/mlops", tags=["mlops"])


def _w(fn, *a, **k):
    try:
        return fn(*a, **k)
    except ml.MlopsError as e:
        raise HTTPException(e.status, e.message) from e
    except ImportError as e:
        raise HTTPException(501, f"This needs scikit-learn, pandas and joblib ({e.name}). Run: pip install -r requirements.txt") from e


class GateIn(BaseModel):
    name: str = Field(max_length=60)
    version: int
    min_gain: float = 0.02
    set_alias: bool = True


class PromoteIn(BaseModel):
    name: str = Field(max_length=60)
    confirm: bool = False
    min_gain: float = 0.01


class RollbackIn(BaseModel):
    name: str = Field(max_length=60)
    version: int
    confirm: bool = False


class ShadowIn(BaseModel):
    name: str = Field(max_length=60)
    rows: int = 40


class SplitIn(BaseModel):
    requests: int = 1000
    challenger_pct: float = 10


class RolloutIn(BaseModel):
    steps_pct: list[float] = Field(default_factory=lambda: [5, 25, 50, 100], max_length=8)
    min_requests_per_step: int = 500
    max_error_pct: float = 1.0
    max_metric_drop_pct: float = 3.0


class LoadIn(BaseModel):
    name: str = Field(max_length=60)
    version: int | None = None
    requests: int = 60
    rows_per_request: int = 1
    p95_ms: float = 250
    max_error_pct: float = 1.0


class LlmIn(BaseModel):
    answers: dict = Field(default_factory=dict)


class FeedbackIn(BaseModel):
    kind: str = Field(max_length=20)
    prompt: str = Field(default="", max_length=50)
    version: int | None = None
    note: str = Field(default="", max_length=200)


@router.get("")
def reference():
    return {**ml.reference(), "aliases": ml.aliases()}


@router.post("/gate")
def gate(b: GateIn):
    return _w(ml.gate, b.name, b.version, b.min_gain, b.set_alias)


@router.get("/compare")
def compare(name: str = Query(max_length=60), min_gain: float = 0.01):
    return _w(ml.compare, name, min_gain)


@router.post("/promote")
def promote(b: PromoteIn):
    return _w(ml.promote, b.name, b.confirm, b.min_gain)


@router.post("/rollback")
def rollback(b: RollbackIn):
    return _w(ml.rollback, b.name, b.version, b.confirm)


@router.post("/shadow")
def shadow(b: ShadowIn):
    return _w(ml.shadow, b.name, b.rows)


@router.post("/split")
def split(b: SplitIn):
    return _w(ml.traffic_split, b.requests, b.challenger_pct)


@router.post("/rollout")
def rollout(b: RolloutIn):
    return _w(ml.rollout_plan, b.steps_pct, b.min_requests_per_step, b.max_error_pct, b.max_metric_drop_pct)


@router.post("/load")
def load(b: LoadIn):
    return _w(ml.load_test, b.name, b.version, b.requests, b.rows_per_request, b.p95_ms, b.max_error_pct)


@router.get("/retrain")
def retrain(name: str = Query(max_length=60)):
    return _w(ml.retrain_advice, name)


@router.post("/llm-plan")
def llm_plan(b: LlmIn):
    return _w(ml.llm_plan, b.answers)


@router.get("/feedback")
def feedback():
    return ml.feedback_summary()


@router.post("/feedback")
def feedback_add(b: FeedbackIn):
    return _w(ml.feedback_add, b.kind, b.prompt, b.version, b.note)


@router.delete("/feedback")
def feedback_clear():
    return ml.feedback_clear()
