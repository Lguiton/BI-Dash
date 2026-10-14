"""KPI builder: turn a metric into a KPI by giving it a target, a direction and a warning band.

Class concept: a *metric* is just a measurement; a *KPI* is a metric tied to a business goal
(target + threshold + owner). Definitions live in the kpi_defs table, evaluated on demand.
"""
import math
import uuid
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.db import fetch_all, fetch_one, get_cursor
from app.services.filters import FROM_SQL

router = APIRouter(prefix="/api/kpis", tags=["kpis"])
MAX_KPIS = 30

# metric id -> (label, SQL aggregate, unit, default direction, plain-language description)
METRICS = {
    "revenue": ("Revenue", "SUM(f.revenue)", "usd", "higher", "Total revenue (additive)."),
    "cost": ("Operational cost", "SUM(f.operational_cost)", "usd", "lower", "Total operational cost (additive)."),
    "profit": ("Net profit", "SUM(f.revenue - f.operational_cost)", "usd", "higher", "Revenue minus cost (additive)."),
    "margin_pct": ("Net margin %", "100.0 * SUM(f.revenue - f.operational_cost) / NULLIF(SUM(f.revenue), 0)", "pct", "higher",
                   "Total profit / total revenue. A ratio of sums, because margin is non-additive."),
    "units": ("Units processed", "SUM(f.units_processed)", "count", "higher", "Total units (additive)."),
    "records": ("Records", "COUNT(*)", "count", "higher", "Number of fact rows."),
    "rev_per_unit": ("Revenue per unit", "SUM(f.revenue) / NULLIF(SUM(f.units_processed), 0)", "usd", "higher",
                     "Total revenue / total units (non-additive ratio)."),
    "avg_duration": ("Avg duration (min)", "AVG(f.duration_minutes)", "min", "lower", "Average minutes per record. An average is a ratio: never add averages together."),
    "cost_vs_budget_pct": ("Cost vs budget %", "100.0 * (SUM(f.operational_cost) / NULLIF(SUM(e.baseline_target), 0) - 1)", "pct", "lower",
                           "Spend relative to the per-record cost budget (baseline_target). Positive = over budget."),
    "failure_rate_pct": ("Non-completed rate %", "100.0 * SUM(CASE WHEN f.status <> 'Completed' THEN 1 ELSE 0 END) / NULLIF(COUNT(f.status), 0)", "pct", "lower",
                         "Share of records whose status is not 'Completed'."),
}


def ensure_table() -> None:
    with get_cursor() as cur:
        cur.execute(
            """CREATE TABLE IF NOT EXISTS kpi_defs (
                id VARCHAR PRIMARY KEY, name VARCHAR, metric VARCHAR, direction VARCHAR,
                target DOUBLE, warn_pct DOUBLE, window_days INTEGER, created_at TIMESTAMP DEFAULT now())"""
        )


class KpiIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    metric: str
    direction: Literal["higher", "lower"]
    target: float
    warn_pct: float = Field(10, ge=0, le=100)
    window_days: int = Field(30, ge=0, le=3650, description="0 = all data")


def _status(value: float | None, d: dict) -> str:
    if value is None:
        return "nodata"
    t, band = d["target"], abs(d["target"]) * d["warn_pct"] / 100
    if d["direction"] == "higher":
        return "good" if value >= t else "warn" if value >= t - band else "bad"
    return "good" if value <= t else "warn" if value <= t + band else "bad"


def _value(cur, metric: str, start, end):
    sql = f"SELECT {METRICS[metric][1]} AS v {FROM_SQL} WHERE f.record_date >= ? AND f.record_date <= ?"
    v = cur.execute(sql, [start, end]).fetchone()[0]
    return None if v is None else float(v)


def _evaluate(cur, d: dict, max_date, min_date) -> dict:
    out = {**d, "label": METRICS[d["metric"]][0], "unit": METRICS[d["metric"]][2]}
    if max_date is None:
        return {**out, "value": None, "status": "nodata", "previous_value": None, "gap": None}
    if d["window_days"] == 0:
        start, end, pstart, pend = min_date, max_date, None, None
    else:
        end = max_date
        start = end - timedelta(days=d["window_days"] - 1)
        pend = start - timedelta(days=1)
        pstart = pend - timedelta(days=d["window_days"] - 1)
    value = _value(cur, d["metric"], start, end)
    prev = _value(cur, d["metric"], pstart, pend) if pstart else None
    gap = None if value is None else value - d["target"]
    return {**out, "value": None if value is None else round(value, 2),
            "previous_value": None if prev is None else round(prev, 2),
            "gap": None if gap is None else round(gap, 2),
            "status": _status(value, d), "window_start": str(start), "window_end": str(end)}


def _list() -> list[dict]:
    ensure_table()
    with get_cursor() as cur:
        defs = fetch_all(cur, "SELECT id, name, metric, direction, target, warn_pct, window_days FROM kpi_defs ORDER BY created_at, id")
        r = cur.execute("SELECT MAX(record_date), MIN(record_date) FROM fact_operations").fetchone()
        mx, mn = r
        return [_evaluate(cur, d, mx, mn) for d in defs]


@router.get("/metrics")
def metrics():
    return {"metrics": [{"id": k, "label": v[0], "unit": v[2], "default_direction": v[3], "description": v[4]}
                        for k, v in METRICS.items()]}


@router.get("")
def list_kpis():
    return {"kpis": _list()}


@router.post("")
def create_kpi(body: KpiIn):
    ensure_table()
    if body.metric not in METRICS:
        raise HTTPException(422, f"Unknown metric '{body.metric}'.")
    if not math.isfinite(body.target):
        raise HTTPException(422, "Target must be a finite number.")
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "Name can't be blank.")
    with get_cursor() as cur:
        if cur.execute("SELECT COUNT(*) FROM kpi_defs").fetchone()[0] >= MAX_KPIS:
            raise HTTPException(400, f"Limit of {MAX_KPIS} KPIs reached. Delete one first.")
        kid = uuid.uuid4().hex[:10]
        cur.execute("INSERT INTO kpi_defs (id, name, metric, direction, target, warn_pct, window_days) VALUES (?,?,?,?,?,?,?)",
                    [kid, name, body.metric, body.direction, body.target, body.warn_pct, body.window_days])
    return {"id": kid}


@router.post("/examples")
def add_examples():
    """Add three starter KPIs with targets derived from the current data, so you see all three statuses."""
    ensure_table()
    with get_cursor() as cur:
        if cur.execute("SELECT COUNT(*) FROM kpi_defs").fetchone()[0]:
            raise HTTPException(400, "You already have KPIs. Starter KPIs are only added to an empty list.")
        mx, mn = cur.execute("SELECT MAX(record_date), MIN(record_date) FROM fact_operations").fetchone()
        if mx is None:
            raise HTTPException(400, "Load some data first.")
        start = mx - timedelta(days=29)
        rev = _value(cur, "revenue", start, mx) or 0
        margin = _value(cur, "margin_pct", start, mx) or 0
        cvb = _value(cur, "cost_vs_budget_pct", start, mx) or 0
        rows = [
            ("Monthly revenue", "revenue", "higher", round(rev * 1.08, 0), 10),            # slightly above reality -> warn
            ("Net margin", "margin_pct", "higher", round(margin - 2, 1), 5),                # just under reality -> good
            ("Stay within cost budget", "cost_vs_budget_pct", "lower", round(min(cvb, 0) - 10, 1), 15),  # strict -> bad
        ]
        for n, m, d, t, w in rows:
            cur.execute("INSERT INTO kpi_defs (id, name, metric, direction, target, warn_pct, window_days) VALUES (?,?,?,?,?,?,30)",
                        [uuid.uuid4().hex[:10], n, m, d, t, w])
    return {"added": len(rows)}


@router.delete("/{kpi_id}")
def delete_kpi(kpi_id: str):
    ensure_table()
    with get_cursor() as cur:
        n = cur.execute("SELECT COUNT(*) FROM kpi_defs WHERE id = ?", [kpi_id]).fetchone()[0]
        if not n:
            raise HTTPException(404, "KPI not found.")
        cur.execute("DELETE FROM kpi_defs WHERE id = ?", [kpi_id])
    return {"deleted": kpi_id}
