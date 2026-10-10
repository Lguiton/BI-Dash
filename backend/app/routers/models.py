"""Model registry, serving and drift endpoints."""
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import ml_lab, model_registry as mr

router = APIRouter(prefix="/api/models", tags=["model registry"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except mr.ModelError as e:
        raise HTTPException(e.status, str(e)) from e
    except ImportError as e:
        raise HTTPException(501, f"Model serving needs scikit-learn, pandas and joblib ({e.name}). Run: pip install -r requirements.txt") from e


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    task: Literal["revenue", "profit", "not_completed"]
    model: str = Field(max_length=40)
    features: list[str] = Field(min_length=1, max_length=len(ml_lab.FEATURES))
    test_fraction: float = Field(0.2, ge=0.1, le=0.5)
    balance_classes: bool = False
    threshold: float = Field(0.5, ge=0.05, le=0.95)
    note: str = Field("", max_length=300)


class StageIn(BaseModel):
    stage: Literal["none", "staging", "production", "archived"]


class PredictIn(BaseModel):
    rows: list[dict] = Field(min_length=1, max_length=mr.MAX_PREDICT_ROWS)
    version: int | None = None


@router.get("")
def models():
    return {"models": mr.list_models()}


@router.post("")
def register(body: RegisterIn):
    return _g(mr.register, body.name, body.task, body.model, body.features, body.test_fraction, body.balance_classes, body.threshold, body.note)


@router.get("/{name}/card")
def card(name: str, version: int | None = None):
    return _g(mr.card, name, version)


@router.put("/{name}/versions/{version}/stage")
def stage(name: str, version: int, body: StageIn):
    return _g(mr.set_stage, name, version, body.stage)


@router.delete("/{name}/versions/{version}")
def delete(name: str, version: int):
    _g(mr.delete, name, version)
    return {"deleted": f"{name} v{version}"}


@router.post("/{name}/predict")
def predict(name: str, body: PredictIn):
    return _g(mr.predict, name, body.rows, body.version)


@router.get("/{name}/drift")
def drift(name: str, version: int | None = None, recent_days: int = Query(14, ge=1, le=365)):
    return _g(mr.drift, name, version, recent_days)


@router.get("/{name}/drift/history")
def drift_history(name: str, version: int | None = None, limit: int = Query(60, ge=1, le=500)):
    return {"history": _g(mr.drift_history, name, version, limit)}
