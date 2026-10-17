"""Advanced analyst lab: cohorts, funnel, forecast with a range, finance, A/B test, Pareto, star schema, window recipes, DAX map, reviews and templates."""
from fastapi import APIRouter, Body, HTTPException

from app.services import analyst_pro as ap

router = APIRouter(prefix="/api/analystpro", tags=["analystpro"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except ap.AnalystError as e:
        raise HTTPException(e.status, e.message) from None
    except Exception as e:  # noqa: BLE001
        if type(e).__name__ == "DataError":
            raise HTTPException(400, str(e)) from None
        raise


@router.get("/reference")
def reference():
    return ap.reference()


@router.get("/recipes")
def recipes():
    return ap.recipes()


@router.get("/recipes/{rid}")
def recipe(rid: str):
    return _g(ap.run_recipe, rid)


@router.get("/dax")
def dax():
    return ap.dax_map()


@router.post("/cohort")
def cohort(b: dict = Body(...)):
    if b.get("table"):
        return _g(ap.cohort_table, str(b["table"]), str(b.get("id_col") or ""), str(b.get("date_col") or ""))
    return _g(ap.cohort, str(b.get("text") or ""))


@router.post("/funnel")
def funnel(b: dict = Body(...)):
    return _g(ap.funnel, str(b.get("text") or ""))


@router.post("/forecast")
def forecast(b: dict = Body(...)):
    return _g(ap.forecast, b.get("values") or b.get("text") or "", b.get("season", 12), b.get("horizon", 3), b.get("width", 2))


@router.post("/calc/{kind}")
def calc(kind: str, b: dict = Body(default={})):
    fn = {"breakeven": ap.breakeven, "unit": ap.unit_econ, "runway": ap.runway, "cycle": ap.cash_cycle, "npv": ap.npv_irr, "margin": ap.margins, "ab": ap.ab_test, "pareto": ap.pareto, "star": ap.star,
          "review": ap.dashboard_review, "metric": ap.metric_card, "requirements": ap.requirements}.get(kind)
    if not fn:
        raise HTTPException(400, "Unknown calculator.")
    names = fn.__code__.co_varnames[:fn.__code__.co_argcount]
    try:
        return _g(fn, **{k: v for k, v in b.items() if k in names})
    except TypeError as e:
        raise HTTPException(400, "Missing a value: " + str(e).split("argument")[-1].strip(" '")) from None
