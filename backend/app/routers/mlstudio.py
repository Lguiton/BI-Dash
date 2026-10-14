"""Model Studio: build, compare, tune and explain predictive models. Saved models are listed by the existing /api/biz-models routes."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.services import biz_models, ml_studio

router = APIRouter(prefix="/api/ml-studio", tags=["ml-studio"])


class BuildIn(BaseModel):
    source: str = Field(max_length=60)
    target: str = Field(max_length=80)
    features: list[str] | None = Field(default=None, max_length=60)
    task: str = Field(default="auto", max_length=20)
    models: list[str] | str = "all"
    tune: bool = False
    balance: bool | str = "auto"
    seconds: int = Field(default=75, ge=15, le=120)
    fp_cost: float = Field(default=1.0, ge=0, le=1e9)
    fn_cost: float = Field(default=1.0, ge=0, le=1e9)


class RowsIn(BaseModel):
    rows: list[dict] = Field(max_length=200)


class RowIn(BaseModel):
    row: dict


class ScoreIn(BaseModel):
    csv: str = Field(max_length=5_000_000)


def _wrap(fn, *a):
    try:
        return fn(*a)
    except biz_models.ModelError as e:
        raise HTTPException(e.status, e.message) from e
    except (FileNotFoundError, KeyError) as e:
        raise HTTPException(404, "No such model.") from e


@router.get("/menu")
def menu():
    return ml_studio.menu()


@router.post("/build")
def build(b: BuildIn):
    opts = {"models": b.models, "tune": b.tune, "balance": b.balance, "seconds": b.seconds, "fp_cost": b.fp_cost, "fn_cost": b.fn_cost}
    return _wrap(ml_studio.build, b.source, b.target, b.features, b.task, opts)


@router.post("/{mid}/predict")
def predict(mid: str, b: RowsIn):
    return _wrap(ml_studio.predict_proba, mid, b.rows)


@router.post("/{mid}/explain")
def explain(mid: str, b: RowIn):
    return _wrap(ml_studio.explain_row, mid, b.row)


@router.post("/{mid}/score")
def score(mid: str, b: ScoreIn):
    return _wrap(ml_studio.batch_score, mid, b.csv)


@router.post("/{mid}/score.csv", response_class=PlainTextResponse)
def score_csv(mid: str, b: ScoreIn):
    return PlainTextResponse(_wrap(ml_studio.batch_score, mid, b.csv)["csv"], headers={"Content-Disposition": 'attachment; filename="predictions.csv"'})
