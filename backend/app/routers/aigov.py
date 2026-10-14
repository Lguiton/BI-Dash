"""AI governance lab and the Python libraries tour."""
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import ai_gov as g, pylib_map as pm

router = APIRouter(prefix="/api", tags=["aigov"])


def _w(fn, *a, **k):
    try:
        return fn(*a, **k)
    except g.GovError as e:
        raise HTTPException(e.status, e.message) from e


class AssetIn(BaseModel):
    name: str = Field(max_length=80)
    kind: str
    owner: str = ""
    purpose: str = ""
    provider: str = "internal"
    data_class: str = "internal"
    pii: bool = False
    actions: list[str] = []
    autonomy: str = "suggest"
    human_oversight: bool = False
    approved: bool = False
    traced: bool = False
    last_review: str = ""


class ObservedIn(BaseModel):
    names: list[str] = Field(max_length=500)


class TierIn(BaseModel):
    answers: dict[str, bool]


class SimIn(BaseModel):
    rules: str = Field(max_length=20_000)
    requests: str = Field(max_length=20_000)
    default: str = "deny"


class SpendIn(BaseModel):
    usage: str = Field(max_length=5_000_000)
    prices: dict[str, Any]
    budgets: Optional[dict[str, Any]] = None
    cheap_model: str = ""
    rate_limit_tpm: int = Field(0, ge=0, le=10**9)


@router.get("/aigov/reference")
def reference():
    return g.reference()


@router.get("/aigov/sample")
def sample():
    return g.sample()


@router.get("/aigov/assets")
def assets():
    return g.assets()


@router.post("/aigov/assets")
def register(b: AssetIn):
    return _w(g.register, b.model_dump())


@router.put("/aigov/assets/{aid}")
def update(aid: str, b: AssetIn):
    return _w(g.update, aid, b.model_dump())


@router.delete("/aigov/assets/{aid}")
def remove(aid: str):
    return _w(g.remove, aid)


@router.post("/aigov/shadow")
def shadow(b: ObservedIn):
    return _w(g.shadow_check, b.names)


@router.post("/aigov/risk-tier")
def tier(b: TierIn):
    return _w(g.risk_tier, b.answers)


@router.post("/aigov/policy")
def policy(b: SimIn):
    return _w(g.simulate_text, b.rules, b.requests, b.default)


@router.post("/aigov/spend")
def spend(b: SpendIn):
    return _w(g.spend, b.usage, b.prices, b.budgets, b.cheap_model, b.rate_limit_tpm)


@router.get("/pylib")
def libs():
    return {**pm.libraries(), "slips": pm.SLIPS}


@router.post("/pylib/{key}/demo")
def demo(key: str):
    r = pm.demo(key)
    if r.get("status") == 404:
        raise HTTPException(404, r["error"])
    return r
