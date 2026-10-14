"""ML Lab endpoints. Needs scikit-learn and pandas (pip install scikit-learn pandas)."""
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from app.config import state_path
from app.services import experiments, ml_lab, state, study

router = APIRouter(prefix="/api/ml", tags=["ml"])


class TrainIn(BaseModel):
    task: Literal["revenue", "profit", "not_completed"]
    model: str = Field(max_length=40)
    features: list[str] = Field(min_length=1, max_length=len(ml_lab.FEATURES))
    test_fraction: float = Field(0.2, ge=0.1, le=0.5)
    balance_classes: bool = False
    threshold: float = Field(0.5, ge=0.05, le=0.95)


@router.get("/options")
def options():
    return ml_lab.options()


@router.post("/train")
def train(body: TrainIn):
    try:
        res = ml_lab.train(body.task, body.model, body.features, body.test_fraction, body.balance_classes, body.threshold)
    except ml_lab.MlError as e:
        raise HTTPException(400, str(e))
    except ImportError as e:
        raise HTTPException(501, f"The ML Lab needs scikit-learn and pandas: pip install scikit-learn pandas ({e.name})")
    study.log_ml_run(res)      # every training run goes into the experiment log shown on the Machine Learning dashboard
    return res


class CompareIn(BaseModel):
    task: Literal["revenue", "profit", "not_completed"]
    features: list[str] = Field(min_length=1, max_length=len(ml_lab.FEATURES))
    test_fraction: float = Field(0.2, ge=0.1, le=0.5)
    balance_classes: bool = False
    threshold: float = Field(0.5, ge=0.05, le=0.95)


@router.post("/compare")
def compare(body: CompareIn):
    """Train every model that fits the task on the same split and rank them. Each model is also logged as a run."""
    try:
        res = ml_lab.compare(body.task, body.features, body.test_fraction, body.balance_classes, body.threshold)
    except ml_lab.MlError as e:
        raise HTTPException(400, str(e))
    except ImportError as e:
        raise HTTPException(501, f"The ML Lab needs scikit-learn and pandas: pip install scikit-learn pandas ({e.name})")
    batch = state.now()
    for m in res["models"]:
        m["run_id"] = study.log_ml_run(m["result"], batch=batch)
        del m["result"]            # keep the response small: the full detail is one "Train" away
    return res


def _exp(fn, *a, **k):
    try:
        return fn(*a, **k)
    except experiments.ExperimentError as e:
        raise HTTPException(e.status, str(e)) from e


class RunPatch(BaseModel):
    note: str | None = Field(None, max_length=1000)
    starred: bool | None = None


class RunsIn(BaseModel):
    ids: list[int] = Field(min_length=2, max_length=6)


@router.get("/runs")
def runs(limit: int = Query(50, ge=1, le=200), task: str | None = None, starred: bool = False):
    return {"runs": experiments.list_runs(limit, task, starred)}


@router.get("/runs/export.csv")
def runs_csv():
    return Response(experiments.export_csv(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="ml_runs.csv"'})


@router.post("/runs/compare")
def runs_compare(body: RunsIn):
    return _exp(experiments.compare_runs, body.ids)


@router.post("/runs/mlflow")
def runs_mlflow():
    """Copy the runs into ./mlruns next to the databases, only if MLflow is installed."""
    out = _exp(experiments.to_mlflow, str(state_path().parent / "mlruns"))
    state.audit("mlflow_export", f"{out['copied']} runs")
    return out


@router.patch("/runs/{run_id}")
def run_update(run_id: int, body: RunPatch):
    return _exp(experiments.update, run_id, body.note, body.starred)


@router.delete("/runs/{run_id}")
def run_delete(run_id: int):
    _exp(experiments.delete, run_id)
    return {"deleted": run_id}
