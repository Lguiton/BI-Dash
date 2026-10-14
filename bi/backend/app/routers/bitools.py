"""BI toolkit: DAX lab, forecast backtest, variance, scenarios, distributions, document reader."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import bi_calc as bc, dax_lab as dx, doc_reader as dr

router = APIRouter(prefix="/api/bitools", tags=["bitools"])


def _w(fn, *a, **k):
    try:
        return fn(*a, **k)
    except (dx.DaxError, bc.CalcError, dr.DocError) as e:
        status = getattr(e, "status", 400)
        raise HTTPException(status, getattr(e, "message", str(e))) from e


class Measure(BaseModel):
    name: str = Field(max_length=40)
    formula: str = Field(max_length=600)


class DaxIn(BaseModel):
    measures: list[Measure] = Field(max_length=12)
    group_by: list[str] = Field(default_factory=list, max_length=2)
    csv_text: str | None = Field(default=None, max_length=400000)


@router.post("/dax")
def dax(b: DaxIn):
    return _w(dx.run, [m.model_dump() for m in b.measures], b.group_by, b.csv_text)


@router.get("/dax/reference")
def dax_ref():
    return dx.reference()


class ForecastIn(BaseModel):
    values: list[float] | str
    horizon: int = Field(6, ge=1, le=24)
    holdout: int | None = Field(None, ge=1, le=100)
    season: int = Field(0, ge=0, le=52)
    alpha: float | None = Field(None, gt=0, lt=1)


@router.post("/forecast")
def forecast(b: ForecastIn):
    return _w(bc.forecast_compare, b.values, b.horizon, b.holdout, b.season, b.alpha)


@router.get("/forecast/sample")
def forecast_sample():
    return {"values": bc.INFOGRAPHIC_SERIES}


class VarianceIn(BaseModel):
    rows: list[dict] = Field(max_length=200)
    threshold_pct: float = Field(10.0, ge=0, le=100)


@router.post("/variance")
def variance(b: VarianceIn):
    return _w(bc.variance, b.rows, b.threshold_pct)


class ScenarioIn(BaseModel):
    price: float
    volume: float
    unit_cost: float
    fixed_cost: float = 0
    scenarios: list[dict] | None = Field(default=None, max_length=10)
    shock_pct: float = Field(10.0, ge=1, le=50)


@router.post("/scenario")
def scenario(b: ScenarioIn):
    return _w(bc.scenario, b.price, b.volume, b.unit_cost, b.fixed_cost, b.scenarios, b.shock_pct)


class FitIn(BaseModel):
    values: list[float] | str


@router.post("/dist/fit")
def dist_fit(b: FitIn):
    return _w(bc.dist_fit, b.values)


class CalcIn(BaseModel):
    kind: str = Field(max_length=20)
    params: dict
    x: float | None = None
    p: float | None = None


@router.post("/dist/calc")
def dist_calc(b: CalcIn):
    return _w(bc.dist_calc, b.kind, b.params, b.x, b.p)


@router.get("/dist/reference")
def dist_ref():
    return bc.dist_reference()


class DocIn(BaseModel):
    text: str = Field(max_length=dr.MAX_CHARS + 1000)
    kind: str = "auto"
    seen: list[str] = Field(default_factory=list, max_length=500)
    csv: bool = False


@router.post("/doc")
def doc(b: DocIn):
    r = _w(dr.parse, b.text, b.kind, b.seen)
    if b.csv:
        r["csv"] = dr.to_csv(r)
    return r


@router.get("/doc/info")
def doc_info():
    return {"samples": dr.SAMPLES, "slips": dr.SLIPS, "not_built": dr.NOT_BUILT}
