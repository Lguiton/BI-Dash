"""ML Lab endpoints. Needs scikit-learn and pandas (pip install scikit-learn pandas)."""
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import ml_lab

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
        return ml_lab.train(body.task, body.model, body.features, body.test_fraction, body.balance_classes, body.threshold)
    except ml_lab.MlError as e:
        raise HTTPException(400, str(e))
    except ImportError as e:
        raise HTTPException(501, f"The ML Lab needs scikit-learn and pandas: pip install scikit-learn pandas ({e.name})")
