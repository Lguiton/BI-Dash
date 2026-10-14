import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.services.db import fetch_all, fetch_one, get_cursor
from app.services.filters import FROM_SQL, Filters, get_filters
from app.services.forecast import forecast_series
from app.services.insights import build_insights, pct_change
from app.services.recommendations import build_recommendations

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

KPI_SQL = f"""
    SELECT
        COUNT(*) AS record_count,
        ROUND(COALESCE(SUM(f.revenue), 0), 2) AS total_revenue,
        ROUND(COALESCE(SUM(f.operational_cost), 0), 2) AS total_cost,
        ROUND(COALESCE(SUM(f.revenue - f.operational_cost), 0), 2) AS net_profit,
        -- Weighted margin: total profit over total revenue. (Averaging per-row
        -- margins would let a tiny day count as much as a huge one.)
        ROUND(SUM(f.revenue - f.operational_cost) / NULLIF(SUM(f.revenue), 0) * 100, 2) AS net_margin_pct,
        COALESCE(SUM(f.units_processed), 0) AS total_units,
        ROUND(SUM(f.revenue) / NULLIF(SUM(f.units_processed), 0), 2) AS rev_per_unit,
        ROUND(AVG(f.duration_minutes), 1) AS avg_duration_minutes
    {FROM_SQL}
"""

# Sort keys the records endpoint will accept (whitelist, never interpolate user input).
RECORD_SORTS = {
    "record_date": "f.record_date",
    "entity_name": "e.name",
    "revenue": "f.revenue",
    "operational_cost": "f.operational_cost",
    "profit": "(f.revenue - f.operational_cost)",
    "units_processed": "f.units_processed",
    "status": "f.status",
}

RECORD_COLS = """
    f.fact_id, STRFTIME(f.record_date, '%Y-%m-%d') AS record_date, f.entity_id,
    COALESCE(e.name, f.entity_id) AS entity_name, e.category,
    f.revenue, f.operational_cost, ROUND(f.revenue - f.operational_cost, 2) AS profit,
    f.units_processed, f.duration_minutes, f.status
"""


def _kpis(cur, flt: Filters) -> dict:
    where, params = flt.where()
    return fetch_one(cur, KPI_SQL + where, params)


def _previous_period(cur, flt: Filters) -> Filters | None:
    """The window of equal length immediately before the selected one.

    Needs an explicit date range; with no dates selected there is no "previous".
    """
    if not flt.date_from or not flt.date_to:
        return None
    span = (flt.date_to - flt.date_from).days + 1
    prev_to = flt.date_from - timedelta(days=1)
    prev_from = prev_to - timedelta(days=span - 1)
    return flt.with_dates(prev_from, prev_to)


def _daily(cur, flt: Filters) -> list[dict]:
    where, params = flt.where()
    return fetch_all(
        cur,
        f"""
        SELECT STRFTIME(f.record_date, '%Y-%m-%d') AS date,
               ROUND(SUM(f.revenue), 2) AS revenue,
               ROUND(SUM(f.operational_cost), 2) AS cost,
               ROUND(SUM(f.revenue - f.operational_cost), 2) AS profit,
               SUM(f.units_processed) AS units
        {FROM_SQL}{where}
        GROUP BY f.record_date ORDER BY f.record_date
        """,
        params,
    )


# baseline_target is treated as a COST BUDGET per record (inferred from the data:
# the seed entities' average cost per record is ~equal to their baseline). So
# vs_baseline_pct > 0 means the entity is spending MORE than budget (bad).
def _by_entity(cur, flt: Filters) -> list[dict]:
    where, params = flt.where()
    rows = fetch_all(
        cur,
        f"""
        SELECT f.entity_id,
               COALESCE(e.name, f.entity_id) AS entity_name,
               COALESCE(e.category, 'Uncategorized') AS category,
               ROUND(SUM(f.revenue), 2) AS revenue,
               ROUND(SUM(f.revenue - f.operational_cost), 2) AS profit,
               ROUND(SUM(f.revenue - f.operational_cost) / NULLIF(SUM(f.revenue), 0) * 100, 2) AS margin_pct,
               COALESCE(SUM(f.units_processed), 0) AS volume,
               COUNT(*) AS records,
               ROUND(AVG(f.revenue), 2) AS avg_revenue_per_record,
               ROUND(AVG(f.operational_cost), 2) AS avg_cost_per_record,
               e.baseline_target
        {FROM_SQL}{where}
        GROUP BY f.entity_id, e.name, e.category, e.baseline_target
        ORDER BY revenue DESC
        """,
        params,
    )
    for r in rows:
        r["margin_pct"] = r["margin_pct"] if r["margin_pct"] is not None else 0.0
        bt = r["baseline_target"]
        r["vs_baseline_pct"] = round((r["avg_cost_per_record"] / bt - 1) * 100, 1) if bt else None
    return rows


@router.get("/meta")
def get_meta():
    """Available filter values and the data's date range."""
    with get_cursor() as cur:
        rng = fetch_one(
            cur,
            "SELECT STRFTIME(MIN(record_date), '%Y-%m-%d') AS min_date, "
            "STRFTIME(MAX(record_date), '%Y-%m-%d') AS max_date, COUNT(*) AS record_count FROM fact_operations",
        )
        entities = fetch_all(
            cur,
            "SELECT entity_id, COALESCE(name, entity_id) AS name, category FROM dim_entities ORDER BY name",
        )
        categories = [r[0] for r in cur.execute(
            "SELECT DISTINCT category FROM dim_entities WHERE category IS NOT NULL ORDER BY category").fetchall()]
        statuses = [r[0] for r in cur.execute(
            "SELECT DISTINCT status FROM fact_operations WHERE status IS NOT NULL ORDER BY status").fetchall()]
    return {**rng, "entities": entities, "categories": categories, "statuses": statuses}


@router.get("/summary")
def get_kpi_summary(flt: Filters = Depends(get_filters)):
    """KPIs for the selection, plus the previous equal-length period and % changes."""
    with get_cursor() as cur:
        current = _kpis(cur, flt)
        prev_flt = _previous_period(cur, flt)
        previous = _kpis(cur, prev_flt) if prev_flt else None
    deltas = None
    if previous and previous["record_count"]:
        deltas = {
            "total_revenue": pct_change(current["total_revenue"], previous["total_revenue"]),
            "total_cost": pct_change(current["total_cost"], previous["total_cost"]),
            "net_profit": pct_change(current["net_profit"], previous["net_profit"]),
            "total_units": pct_change(current["total_units"], previous["total_units"]),
            "rev_per_unit": pct_change(current["rev_per_unit"], previous["rev_per_unit"]),
            # margin change is in percentage points, not percent
            "net_margin_pct": (
                round(current["net_margin_pct"] - previous["net_margin_pct"], 2)
                if current["net_margin_pct"] is not None and previous["net_margin_pct"] is not None else None
            ),
        }
    return {**current, "previous": previous, "deltas": deltas,
            "previous_range": ({"date_from": str(prev_flt.date_from), "date_to": str(prev_flt.date_to)} if prev_flt else None)}


@router.get("/timeseries")
def get_performance_trend(flt: Filters = Depends(get_filters)):
    with get_cursor() as cur:
        return _daily(cur, flt)


@router.get("/by-entity")
def get_dimensional_breakdown(flt: Filters = Depends(get_filters)):
    with get_cursor() as cur:
        return _by_entity(cur, flt)


@router.get("/records")
def get_records(
    flt: Filters = Depends(get_filters),
    limit: int = Query(25, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort: str = Query("record_date"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
):
    """Row-level drill-down behind every aggregate."""
    sort_expr = RECORD_SORTS.get(sort, RECORD_SORTS["record_date"])
    where, params = flt.where()
    with get_cursor() as cur:
        total = cur.execute(f"SELECT COUNT(*) {FROM_SQL}{where}", params).fetchone()[0]
        rows = fetch_all(
            cur,
            f"SELECT {RECORD_COLS} {FROM_SQL}{where} ORDER BY {sort_expr} {order.upper()}, f.fact_id LIMIT ? OFFSET ?",
            params + [limit, offset],
        )
    return {"total": total, "limit": limit, "offset": offset, "rows": rows}


@router.get("/records/export")
def export_records(flt: Filters = Depends(get_filters)):
    """CSV download of every record matching the filters."""
    where, params = flt.where()
    with get_cursor() as cur:
        rows = fetch_all(cur, f"SELECT {RECORD_COLS} {FROM_SQL}{where} ORDER BY f.record_date, f.fact_id", params)
    buf = io.StringIO()
    cols = ["fact_id", "record_date", "entity_id", "entity_name", "category", "revenue",
            "operational_cost", "profit", "units_processed", "duration_minutes", "status"]
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="bi_records.csv"'},
    )


def _weekday_rows(cur, flt: Filters) -> list[dict]:
    where, params = flt.where()
    return fetch_all(
        cur,
        f"""
        SELECT f.entity_id, DAYOFWEEK(f.record_date) IN (0, 6) AS is_weekend,
               COUNT(*) AS records, AVG(f.revenue) AS avg_revenue
        {FROM_SQL}{where}
        GROUP BY f.entity_id, DAYOFWEEK(f.record_date) IN (0, 6)
        """,
        params,
    )


def _forecast(daily: list[dict], horizon: int) -> dict:
    series = [(date.fromisoformat(d["date"]), float(d["revenue"])) for d in daily]
    return forecast_series(series, horizon)


SCATTER_MAX_POINTS = 2000
ISO_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@router.get("/scatter")
def get_scatter(flt: Filters = Depends(get_filters)):
    """Cost vs revenue per record, coloured by category. Large selections are sampled deterministically."""
    where, params = flt.where()
    with get_cursor() as cur:
        total = cur.execute(f"SELECT COUNT(*) {FROM_SQL}{where}", params).fetchone()[0]
        pts = fetch_all(
            cur,
            f"""
            SELECT f.revenue, f.operational_cost AS cost, f.units_processed AS units,
                   COALESCE(e.name, f.entity_id) AS entity_name, COALESCE(e.category, 'Uncategorized') AS category
            {FROM_SQL}{where}
            ORDER BY hash(f.fact_id) LIMIT {SCATTER_MAX_POINTS}
            """,
            params,
        )
    return {"total": total, "sampled": total > len(pts), "points": pts}


@router.get("/heatmap")
def get_heatmap(flt: Filters = Depends(get_filters)):
    """Average revenue per record for every entity x weekday: a classic heatmap."""
    where, params = flt.where()
    with get_cursor() as cur:
        cells = fetch_all(
            cur,
            f"""
            SELECT COALESCE(e.name, f.entity_id) AS entity_name,
                   ISODOW(f.record_date) AS dow,
                   ROUND(AVG(f.revenue), 2) AS avg_revenue, COUNT(*) AS records
            {FROM_SQL}{where}
            GROUP BY 1, 2 ORDER BY 1, 2
            """,
            params,
        )
    entities = sorted({c["entity_name"] for c in cells})
    for c in cells:
        c["day"] = ISO_DAYS[c["dow"] - 1]
    return {"days": ISO_DAYS, "entities": entities, "cells": cells}


@router.get("/forecast")
def get_forecast(flt: Filters = Depends(get_filters), horizon: int = Query(14, ge=1, le=90)):
    """Predictive analytics: revenue forecast with a prediction interval and a 7-day backtest."""
    with get_cursor() as cur:
        daily = _daily(cur, flt)
    return _forecast(daily, horizon)


@router.get("/recommendations")
def get_recommendations(flt: Filters = Depends(get_filters)):
    """Prescriptive analytics: what to do, estimated impact, and how the estimate was computed."""
    with get_cursor() as cur:
        entities = _by_entity(cur, flt)
        weekday = _weekday_rows(cur, flt)
    return {"recommendations": build_recommendations(entities, weekday)}


@router.get("/insights")
def get_insights(flt: Filters = Depends(get_filters)):
    """All four analytics types in one list, each tagged with `analytics_type`:
    descriptive (what happened), diagnostic (why), predictive (what's likely), prescriptive (what to do)."""
    with get_cursor() as cur:
        kpis = _kpis(cur, flt)
        prev_flt = _previous_period(cur, flt)
        prev = _kpis(cur, prev_flt) if prev_flt else None
        daily = _daily(cur, flt)
        entities = _by_entity(cur, flt)
        weekday = _weekday_rows(cur, flt)
    insights = build_insights(kpis, prev, daily, entities)

    fc = _forecast(daily, 7)
    if fc["available"]:
        nxt = sum(p["forecast"] for p in fc["points"])
        last7 = sum(d["revenue"] for d in daily[-7:])
        ch = pct_change(nxt, last7)
        bt = fc["backtest"]
        insights.append({
            "analytics_type": "predictive", "type": "forecast", "severity": "info",
            "title": f"Next 7 days: about ${nxt:,.0f} revenue" + (f" ({ch:+.1f}% vs the last 7 days)" if ch is not None else ""),
            "detail": f"{fc['method']}. " + (f"Backtest error on the last {bt['days']} days: {bt['mape_pct']}% (MAPE)." if bt else "Not enough history for a backtest."),
        })
    else:
        insights.append({"analytics_type": "predictive", "type": "forecast", "severity": "info",
                         "title": "Forecast unavailable", "detail": fc["reason"]})

    for r in build_recommendations(entities, weekday)[:3]:
        insights.append({
            "analytics_type": "prescriptive", "type": r["kind"], "severity": "info",
            "title": r["title"], "detail": f"{r['action']} Estimated impact {_fmt_money(r['impact_usd'])} ({r['basis']})",
        })
    return {"insights": insights}


def _fmt_money(v: float) -> str:
    return f"${v:,.0f}"
