"""ML by hand: step-by-step worked examples with a sandbox (nothing is saved)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import biz_packs, ml_by_hand

router = APIRouter(prefix="/api/ml-hand", tags=["mlhand"])


class RunIn(BaseModel):
    method: str = Field(max_length=20)
    data: str = Field(max_length=20000)
    query: str = Field(default="", max_length=500)
    params: dict = Field(default_factory=dict)


@router.get("/presets")
def presets():
    return {"methods": list(ml_by_hand.METHODS), "presets": ml_by_hand.PRESETS, "limits": {"rows": ml_by_hand.MAX_ROWS, "features": ml_by_hand.MAX_FEATURES}}


@router.post("/run")
def run(b: RunIn):
    try:
        return ml_by_hand.run(b.method, b.data, b.query, b.params)
    except ml_by_hand.HandError as e:
        raise HTTPException(e.status, e.message) from e


@router.get("/from-pack")
def from_pack(pid: str, columns: str, rows: int = 8):
    """Copy a few real rows from one of your dashboards into the sandbox as text. Read-only."""
    cols = [c.strip() for c in columns.split(",") if c.strip()][:ml_by_hand.MAX_FEATURES + 1]
    if len(cols) < 2:
        raise HTTPException(400, "Choose at least two columns.")
    try:
        b = biz_packs.browse(pid, "", cols[0], "asc", max(2, min(rows, ml_by_hand.MAX_ROWS)), 0)
    except biz_packs.PackError as e:
        raise HTTPException(e.status if hasattr(e, "status") else 400, str(e)) from e
    have = [c for c in b["columns"]]
    if any(c not in have for c in cols):
        raise HTTPException(400, "Unknown column. Available: " + ", ".join(have))
    ix = [have.index(c) for c in cols]
    lines = [",".join(cols)] + [",".join(str(r["values"][i]) for i in ix) for r in b["rows"]]
    return {"data": "\n".join(lines), "rows": len(b["rows"]), "available": have}
