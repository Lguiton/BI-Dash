"""Electrical and HVAC calculators for planning, quoting and talking to licensed trades. Reference only.
They do not replace the electrical code, a load calculation or a licensed professional, and they never cover gas or refrigerant work."""
from __future__ import annotations

import math


class ElecError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


LICENSE_NOTE = ("Reference only. Wiring, breaker panels, gas lines and refrigerant must be done by licensed, certified people (in Nevada, a licensed electrician or HVAC contractor, "
                "and EPA Section 608 for refrigerant). Use these numbers to plan, quote and ask the right questions.")

# Copper conductor resistance, ohms per 1000 ft at about 75 C, and 60 C ampacity for common sizes (reference values; the code and local rules decide).
AWG = {14: (3.14, 15), 12: (1.98, 20), 10: (1.24, 30), 8: (0.778, 40), 6: (0.491, 55), 4: (0.308, 70), 3: (0.245, 85), 2: (0.194, 95)}


def _pos(v, name, lo=0.0, hi=1e9) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ElecError(f"{name} must be a number.") from None
    if not lo < x <= hi:
        raise ElecError(f"{name} must be more than {lo:g} and at most {hi:g}.")
    return x


def voltage_drop(amps, length_ft, awg=12, volts=120) -> dict:
    """Single-phase copper run. length_ft is one way (to the load)."""
    i, l, v = _pos(amps, "Current (A)", 0, 400), _pos(length_ft, "Length (ft)", 0, 5000), _pos(volts, "Volts", 0, 600)
    a = int(awg)
    if a not in AWG:
        raise ElecError("Wire size must be one of " + ", ".join(str(k) for k in AWG) + " AWG.")
    drop = 2 * l * AWG[a][0] * i / 1000
    pct = drop / v * 100
    ok = [k for k in sorted(AWG, reverse=True) if 2 * l * AWG[k][0] * i / 1000 / v * 100 <= 3 and AWG[k][1] >= i]
    return {"awg": a, "volts_lost": round(drop, 2), "percent": round(pct, 2), "volts_at_load": round(v - drop, 1),
            "verdict": "Within the common 3% guide for a branch circuit." if pct <= 3 else "Over 3%: expect dim lights, hot wire or motors struggling. A larger wire is needed.",
            "smallest_size_under_3pct": f"{ok[0]} AWG" if ok else "None of the listed sizes; this run needs an electrician's design.",
            "ampacity_60c": AWG[a][1], "note": LICENSE_NOTE}


def circuit_load(volts, breaker_amps, loads, continuous=False) -> dict:
    v, b = _pos(volts, "Volts", 0, 600), _pos(breaker_amps, "Breaker (A)", 0, 400)
    rows, total = [], 0.0
    for ln in (loads if isinstance(loads, list) else str(loads).splitlines()):
        t = str(ln).strip()
        if not t:
            continue
        name, _, w = t.rpartition(",")
        try:
            watts = float(w)
        except ValueError:
            raise ElecError(f"Could not read '{t}'. Use one device per line: name, watts.") from None
        if watts < 0:
            raise ElecError("Watts cannot be negative.")
        rows.append({"device": name.strip() or "device", "watts": watts})
        total += watts
    if not rows:
        raise ElecError("Add at least one device, like: Space heater, 1500")
    amps = total / v
    limit = b * (0.8 if continuous else 1.0)
    pct = amps / limit * 100
    return {"total_watts": round(total), "amps": round(amps, 1), "breaker_amps": b, "usable_amps": round(limit, 1), "percent_of_usable": round(pct),
            "verdict": "Over the limit: remove loads or use another circuit; do not fit a bigger breaker." if pct > 100 else "Close to the limit: leave room, especially for heaters and tools." if pct > 80 else "Within the limit.",
            "rule": "Loads that run 3 hours or more are treated as continuous and limited to 80% of the breaker." if continuous else "Short-use loads can use the full breaker rating; continuous loads (3+ hours) are limited to 80%.",
            "devices": rows, "note": LICENSE_NOTE}


def energy_cost(watts, hours_per_day, rate_per_kwh=0.13, days=30) -> dict:
    w, h, r, d = _pos(watts, "Watts", 0, 1e6), _pos(hours_per_day, "Hours per day", 0, 24), _pos(rate_per_kwh, "Rate ($/kWh)", 0, 5), _pos(days, "Days", 0, 366)
    kwh = w * h * d / 1000
    return {"kwh": round(kwh, 1), "cost": round(kwh * r, 2), "per_year": round(w * h * 365 / 1000 * r, 2), "rate_used": r,
            "note": "Uses the rate you give (the default is only an example; use the rate on your bill). Real usage varies, especially for compressors that cycle on and off."}


def hvac_size(sqft, ceiling_ft=8, sun="average", insulation="average", people=2, kitchen=False) -> dict:
    s, c, p = _pos(sqft, "Floor area (sq ft)", 0, 10000), _pos(ceiling_ft, "Ceiling height (ft)", 0, 20), _pos(people, "People", 0, 50)
    if sun not in ("low", "average", "high") or insulation not in ("poor", "average", "good"):
        raise ElecError("sun is low, average or high; insulation is poor, average or good.")
    btu = s * 20 * (c / 8)
    btu *= {"low": 0.9, "average": 1.0, "high": 1.1}[sun] * {"poor": 1.15, "average": 1.0, "good": 0.9}[insulation]
    btu += max(0, p - 2) * 600 + (4000 if kitchen else 0)
    btu = round(btu / 500) * 500
    return {"btu_per_hour": btu, "tons": round(btu / 12000, 1), "note": "A rule-of-thumb starting point (about 20 BTU per square foot, adjusted). A proper room-by-room load calculation (Manual J) from an HVAC contractor decides the real size. Oversized units cycle on and off and cool poorly.",
            "window_unit_hint": "A window unit rated close to this BTU is a fit for one room; whole homes need a ducted or multi-zone system."}


def ohm(volts=None, amps=None, ohms=None, watts=None) -> dict:
    vals = {"volts": volts, "amps": amps, "ohms": ohms, "watts": watts}
    given = {k: _pos(v, k, 0, 1e9) for k, v in vals.items() if v not in (None, "")}
    if len(given) != 2:
        raise ElecError("Give exactly two of: volts, amps, ohms, watts.")
    v, i, r, p = (given.get(k) for k in ("volts", "amps", "ohms", "watts"))
    if v is not None and i is not None:
        r, p = v / i, v * i
    elif v is not None and r is not None:
        i = v / r; p = v * i
    elif v is not None and p is not None:
        i = p / v; r = v / i
    elif i is not None and r is not None:
        v = i * r; p = v * i
    elif i is not None and p is not None:
        v = p / i; r = v / i
    else:
        v = math.sqrt(p * r); i = v / r
    return {"volts": round(v, 3), "amps": round(i, 3), "ohms": round(r, 3), "watts": round(p, 3)}


def delta_t(supply_f, return_f) -> dict:
    s, r = _pos(supply_f, "Supply air (F)", -50, 250), _pos(return_f, "Return air (F)", -50, 250)
    d = r - s
    if d < 14:
        v = "Low split. Check a dirty filter or coil, low airflow settings, or a possible low refrigerant charge. A technician should check the charge."
    elif d <= 22:
        v = "Normal cooling split (about 16 to 22 F)."
    else:
        v = "High split: usually weak airflow (dirty filter, closed vents, failing blower) or a frozen coil. Fix airflow first."
    return {"split_f": round(d, 1), "verdict": v, "how": "Measure with the system running at least 15 minutes: air going into the return grille versus air at a nearby supply vent. Best in humid, hot conditions.", "note": LICENSE_NOTE}


def reference() -> dict:
    return {"wire": [{"awg": k, "ohms_per_1000ft": v[0], "ampacity_60c": v[1]} for k, v in AWG.items()],
            "typical_circuits": [{"circuit": "General lighting and outlets", "breaker": "15 A, 14 AWG"}, {"circuit": "Kitchen, laundry, bathroom, garage outlets", "breaker": "20 A, 12 AWG"},
                                 {"circuit": "Electric dryer", "breaker": "30 A, 10 AWG (240 V)"}, {"circuit": "Electric range", "breaker": "40 to 50 A, 8 to 6 AWG (240 V)"}],
            "hvac_facts": ["A ton of cooling is 12,000 BTU per hour.", "A normal cooling air split is about 16 to 22 F.", "Change filters every 1 to 3 months.", "Refrigerant is handled only by EPA-certified technicians."],
            "who_does_what": [{"job": "Dirty filter, thermostat batteries, vent cleaning, outdoor coil rinse", "who": "You"}, {"job": "Appliance parts, drains, belts, simple swaps with power off", "who": "You, if comfortable"},
                              {"job": "Wiring, outlets, panels, breakers, new circuits", "who": "Licensed electrician"}, {"job": "Refrigerant, compressors, gas furnaces, gas lines, flues", "who": "Licensed HVAC or gas contractor"}],
            "note": LICENSE_NOTE}
