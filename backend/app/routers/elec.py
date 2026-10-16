"""Electrical and HVAC calculators. Reference only."""
from fastapi import APIRouter, Body, HTTPException

from app.services import elec_calc as ec

router = APIRouter(prefix="/api/elec", tags=["elec"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except ec.ElecError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/reference")
def reference():
    return ec.reference()


@router.post("/voltage-drop")
def voltage_drop(b: dict = Body(...)):
    return _g(ec.voltage_drop, b.get("amps"), b.get("length_ft"), b.get("awg", 12), b.get("volts", 120))


@router.post("/circuit-load")
def circuit_load(b: dict = Body(...)):
    return _g(ec.circuit_load, b.get("volts", 120), b.get("breaker_amps", 15), b.get("loads", ""), bool(b.get("continuous")))


@router.post("/energy")
def energy(b: dict = Body(...)):
    return _g(ec.energy_cost, b.get("watts"), b.get("hours_per_day"), b.get("rate_per_kwh", 0.13), b.get("days", 30))


@router.post("/hvac-size")
def hvac_size(b: dict = Body(...)):
    return _g(ec.hvac_size, b.get("sqft"), b.get("ceiling_ft", 8), b.get("sun", "average"), b.get("insulation", "average"), b.get("people", 2), bool(b.get("kitchen")))


@router.post("/ohm")
def ohm(b: dict = Body(...)):
    return _g(ec.ohm, b.get("volts"), b.get("amps"), b.get("ohms"), b.get("watts"))


@router.post("/delta-t")
def delta_t(b: dict = Body(...)):
    return _g(ec.delta_t, b.get("supply_f"), b.get("return_f"))
