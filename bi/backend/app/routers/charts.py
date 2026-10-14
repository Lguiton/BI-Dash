"""Data for the dashboard's chart gallery: breakdowns (pie, donut, treemap, funnel, radar, pareto) and
distributions (histogram, box plot). Every query uses the same filters as the rest of the dashboard and only whitelisted
column expressions, never user text."""
from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.services.db import fetch_all, get_cursor
from app.services.filters import FROM_SQL, Filters, get_filters

router = APIRouter(prefix="/api/charts", tags=["charts"])

MEASURES = {
    "revenue": ("f.revenue", "Revenue", "money"),
    "cost": ("f.operational_cost", "Operational cost", "money"),
    "profit": ("(f.revenue - f.operational_cost)", "Profit", "money"),
    "units": ("f.units_processed", "Units processed", "number"),
    "duration": ("f.duration_minutes", "Duration (minutes)", "number"),
}
GROUPS = {
    "entity": ("COALESCE(e.name, f.entity_id)", "Entity"),
    "category": ("COALESCE(e.category, 'Uncategorized')", "Category"),
    "status": ("COALESCE(f.status, 'Unknown')", "Status"),
    "weekday": ("STRFTIME(f.record_date, '%u %a')", "Weekday"),
    "month": ("STRFTIME(f.record_date, '%Y-%m')", "Month"),
}
MAX_GROUPS = 30
MeasureName = Literal["revenue", "cost", "profit", "units", "duration"]
GroupName = Literal["entity", "category", "status", "weekday", "month"]


def _label(group: str, name: str) -> str:
    return name[2:] if group == "weekday" else name  # "1 Mon" sorts Sunday-first by %w; strip the sort prefix for display


@router.get("/breakdown")
def breakdown(by: GroupName = "category", measure: MeasureName = "revenue", flt: Filters = Depends(get_filters)):
    """Total of a measure per group, biggest first. Powers pie, donut, treemap, funnel, radar, pareto and bar charts."""
    expr, label, kind = MEASURES[measure]
    gexpr, glabel = GROUPS[by]
    where, params = flt.where()
    order = "1" if by in ("weekday", "month") else "2 DESC"
    with get_cursor() as cur:
        rows = fetch_all(cur, f"""
            SELECT {gexpr} AS name, ROUND(COALESCE(SUM({expr}), 0), 2) AS value, COUNT(*) AS records,
                   ROUND(SUM(f.revenue), 2) AS revenue, ROUND(SUM(f.operational_cost), 2) AS cost,
                   COALESCE(SUM(f.units_processed), 0) AS units
            {FROM_SQL}{where} GROUP BY 1 ORDER BY {order}""", params)
    truncated = len(rows) > MAX_GROUPS
    if truncated:  # keep the biggest groups and fold the rest into one slice so a pie never has 200 wedges
        rows = sorted(rows, key=lambda r: r["value"], reverse=True)
        keep, rest = rows[:MAX_GROUPS - 1], rows[MAX_GROUPS - 1:]
        keep.append({"name": f"Other ({len(rest)})", "value": round(sum(r["value"] for r in rest), 2),
                     "records": sum(r["records"] for r in rest), "revenue": round(sum(r["revenue"] for r in rest), 2),
                     "cost": round(sum(r["cost"] for r in rest), 2), "units": sum(r["units"] for r in rest)})
        rows = keep
    for r in rows:
        r["name"] = _label(by, str(r["name"]))
    total = round(sum(r["value"] for r in rows), 2)
    return {"by": by, "by_label": glabel, "measure": measure, "measure_label": label, "format": kind,
            "total": total, "grouped_into_other": truncated, "rows": rows}


@router.get("/distribution")
def distribution(measure: MeasureName = "revenue", by: Literal["none", "entity", "category", "status"] = "none",
                 bins: int = Query(20, ge=5, le=60), flt: Filters = Depends(get_filters)):
    """Per-record distribution of a measure: histogram bins plus box-plot statistics (overall or per group)."""
    expr, label, kind = MEASURES[measure]
    where, params = flt.where()
    cond = f"{expr} IS NOT NULL" + (f" AND {where[7:]}" if where else "")
    gexpr = GROUPS[by][0] if by != "none" else "'All records'"
    with get_cursor() as cur:
        span = cur.execute(f"SELECT MIN({expr}), MAX({expr}), COUNT(*) {FROM_SQL} WHERE {cond}", params).fetchone()
        lo, hi, n = span
        if not n:
            return {"measure": measure, "measure_label": label, "format": kind, "count": 0, "histogram": [], "boxes": []}
        lo, hi = float(lo), float(hi)
        width = (hi - lo) / bins if hi > lo else 1.0
        counts = dict(cur.execute(f"""
            SELECT LEAST(CAST(FLOOR(({expr} - ?) / ?) AS INTEGER), {bins - 1}) AS b, COUNT(*)
            {FROM_SQL} WHERE {cond} GROUP BY 1""", [lo, width, *params]).fetchall())
        hist = [{"from": round(lo + i * width, 2), "to": round(lo + (i + 1) * width, 2), "count": int(counts.get(i, 0))}
                for i in range(bins)]
        stats = fetch_all(cur, f"""
            SELECT {gexpr} AS name, COUNT(*) AS n, MIN({expr}) AS lo, MAX({expr}) AS hi,
                   QUANTILE_CONT({expr}, 0.25) AS q1, QUANTILE_CONT({expr}, 0.5) AS med,
                   QUANTILE_CONT({expr}, 0.75) AS q3, AVG({expr}) AS mean
            {FROM_SQL} WHERE {cond} GROUP BY 1 ORDER BY 2 DESC LIMIT 12""", params)
        boxes = []
        for s in stats:
            iqr = s["q3"] - s["q1"]
            f_lo, f_hi = s["q1"] - 1.5 * iqr, s["q3"] + 1.5 * iqr
            gcond = f"{cond} AND {gexpr} = ?"
            inside = cur.execute(f"SELECT MIN({expr}), MAX({expr}) {FROM_SQL} WHERE {gcond} AND {expr} BETWEEN ? AND ?",
                                 [*params, s["name"], f_lo, f_hi]).fetchone()
            outl = cur.execute(f"""SELECT {expr} {FROM_SQL} WHERE {gcond} AND ({expr} < ? OR {expr} > ?)
                                   ORDER BY ABS({expr} - ?) DESC LIMIT 25""",
                               [*params, s["name"], f_lo, f_hi, s["med"]]).fetchall()
            n_out = cur.execute(f"SELECT COUNT(*) {FROM_SQL} WHERE {gcond} AND ({expr} < ? OR {expr} > ?)",
                                [*params, s["name"], f_lo, f_hi]).fetchone()[0]
            boxes.append({"name": str(s["name"]), "n": s["n"], "whisker_low": round(float(inside[0] if inside[0] is not None else s["lo"]), 2),
                          "q1": round(s["q1"], 2), "median": round(s["med"], 2), "q3": round(s["q3"], 2),
                          "whisker_high": round(float(inside[1] if inside[1] is not None else s["hi"]), 2),
                          "mean": round(s["mean"], 2), "outliers": [round(float(o[0]), 2) for o in outl], "outlier_count": int(n_out)})
    return {"measure": measure, "measure_label": label, "format": kind, "count": int(n), "bins": bins, "histogram": hist, "boxes": boxes}


@router.get("/bubble")
def bubble(flt: Filters = Depends(get_filters)):
    """One bubble per entity: cost (x), revenue (y), size = units."""
    where, params = flt.where()
    with get_cursor() as cur:
        rows = fetch_all(cur, f"""
            SELECT COALESCE(e.name, f.entity_id) AS name, COALESCE(e.category, 'Uncategorized') AS category,
                   ROUND(SUM(f.operational_cost), 2) AS cost, ROUND(SUM(f.revenue), 2) AS revenue,
                   COALESCE(SUM(f.units_processed), 0) AS units
            {FROM_SQL}{where} GROUP BY 1, 2 ORDER BY 4 DESC LIMIT 40""", params)
    return {"rows": rows}
