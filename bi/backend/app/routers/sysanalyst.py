"""Systems analyst endpoints."""
from fastapi import APIRouter, Body, HTTPException, Query

from app.services import sysanalysis as sa

router = APIRouter(prefix="/api/sysanalyst", tags=["systems-analyst"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except sa.SaError as e:
        raise HTTPException(e.status, e.message) from e


@router.get("")
def overview():
    return sa.overview()


@router.get("/dictionary")
def dictionary():
    return sa.data_dictionary()


@router.get("/process")
def process():
    return sa.process_analysis()


@router.post("/requirements")
def add_req(body: dict = Body(...)):
    return _g(sa.save_requirement, body)


@router.put("/requirements/{rid}")
def edit_req(rid: int, body: dict = Body(...)):
    return _g(sa.save_requirement, body, rid)


@router.delete("/requirements/{rid}")
def del_req(rid: int):
    sa.delete_requirement(rid)
    return {"deleted": rid}


@router.post("/requirements/example")
def example():
    return {"loaded": _g(sa.load_example_requirements)}


@router.put("/feasibility")
def feasibility(body: dict = Body(...)):
    return _g(sa.feasibility_save, body)


@router.get("/calc/queue")
def calc_queue(arrival_rate: float = Query(gt=0), service_rate: float = Query(gt=0), servers: int = Query(1, ge=1, le=500), target_wait: float | None = Query(None, ge=0)):
    return _g(sa.queue, arrival_rate, service_rate, servers, target_wait)


@router.get("/calc/availability")
def calc_availability(slo: float = Query(99.9), window_days: float = Query(30, gt=0), used_minutes: float = Query(0, ge=0),
                      parts: str = Query(""), mode: str = Query("serial", pattern="^(serial|parallel)$")):
    try:
        vals = [float(x) for x in parts.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(400, "parts must be numbers separated by commas, like 99.9,99.5.") from None
    return _g(sa.availability, slo, window_days, used_minutes, vals or None, mode)


@router.get("/calc/cost-benefit")
def calc_cb(initial: float = Query(ge=0), annual_benefit: float = Query(ge=0), annual_cost: float = Query(0, ge=0), years: int = Query(3, ge=1, le=30), rate: float = Query(10, ge=0, le=100)):
    return _g(sa.cost_benefit, initial, annual_benefit, annual_cost, years, rate)


@router.get("/calc/capacity")
def calc_capacity(load: float = Query(gt=0), capacity: float = Query(gt=0), growth: float = Query(), headroom: float = Query(80, gt=0, le=100)):
    return _g(sa.capacity, load, capacity, growth, headroom)
