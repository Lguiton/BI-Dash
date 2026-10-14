"""More ML tools: drift, automatic search, neural network, attention, tokenizer and semantic search."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import ml_build as mb
from app.services.ml_tools import MlToolError

router = APIRouter(prefix="/api/mlbuild", tags=["mlbuild"])


def _w(fn, *a, **k):
    try:
        return fn(*a, **k)
    except MlToolError as e:
        raise HTTPException(e.status, str(e)) from e


class Drift(BaseModel):
    reference: str = Field(max_length=400000)
    current: str = Field(max_length=400000)
    kind: str = "numeric"


class Perf(BaseModel):
    rows: str = Field(max_length=10000)


class Auto(BaseModel):
    csv: str = Field(max_length=1_500_000)
    target: str = Field(max_length=100)
    max_features: int = 6


class Nn(BaseModel):
    data: str = "xor"
    hidden: str = Field(default="8", max_length=20)
    activation: str = "tanh"
    lr: float = 0.1
    epochs: int = 300
    seed: int = 3
    n: int = 200


class Att(BaseModel):
    text: str = Field(max_length=400)
    dim: int = 8
    causal: bool = False


class Bpe(BaseModel):
    text: str = Field(max_length=50000)
    merges: int = 20
    test: str = Field(default="", max_length=500)


class Lsa(BaseModel):
    docs: str = Field(max_length=100000)
    query: str = Field(max_length=300)
    k: int = 2


@router.get("/reference")
def reference():
    return mb.reference()


@router.post("/drift")
def drift(b: Drift):
    return _w(mb.drift, b.reference, b.current, b.kind)


@router.post("/performance-drift")
def perf(b: Perf):
    return _w(mb.perf_drift, b.rows)


@router.post("/automl")
def automl(b: Auto):
    return _w(mb.automl, b.csv, b.target, b.max_features)


@router.post("/neural-net")
def nn(b: Nn):
    return _w(mb.nn_train, **b.model_dump())


@router.get("/gradient-check")
def gc():
    return mb.grad_check()


@router.post("/attention")
def att(b: Att):
    return _w(mb.attention, b.text, b.dim, b.causal)


@router.post("/bpe")
def bpe(b: Bpe):
    return _w(mb.bpe, b.text, b.merges, b.test)


@router.post("/lsa")
def lsa(b: Lsa):
    return _w(mb.lsa, b.docs, b.query, b.k)
