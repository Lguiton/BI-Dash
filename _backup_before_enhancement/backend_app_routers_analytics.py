from fastapi import APIRouter
from app.services.db import get_duckdb_connection

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/summary")
def get_kpi_summary():
    conn = get_duckdb_connection()
    query = """
        SELECT 
            ROUND(SUM(revenue), 2) AS total_revenue,
            ROUND(SUM(operational_cost), 2) AS total_cost,
            ROUND(SUM(revenue - operational_cost), 2) AS net_profit,
            ROUND(AVG((revenue - operational_cost) / NULLIF(revenue, 0)) * 100, 2) AS net_margin_pct,
            SUM(units_processed) AS total_units,
            ROUND(SUM(revenue) / NULLIF(SUM(units_processed), 0), 2) AS rev_per_unit
        FROM fact_operations;
    """
    df = conn.execute(query).df()
    conn.close()
    return df.to_dict(orient="records")[0]

@router.get("/timeseries")
def get_performance_trend():
    conn = get_duckdb_connection()
    query = """
        SELECT 
            STRFTIME(record_date, '%Y-%m-%d') as date,
            ROUND(SUM(revenue), 2) AS revenue,
            ROUND(SUM(operational_cost), 2) AS cost,
            ROUND(SUM(revenue - operational_cost), 2) AS profit
        FROM fact_operations
        GROUP BY record_date
        ORDER BY record_date ASC;
    """
    df = conn.execute(query).df()
    conn.close()
    return df.to_dict(orient="records")

@router.get("/by-entity")
def get_dimensional_breakdown():
    conn = get_duckdb_connection()
    query = """
        SELECT 
            e.name AS entity_name,
            e.category,
            ROUND(SUM(f.revenue), 2) AS revenue,
            ROUND(SUM(f.revenue - f.operational_cost), 2) AS profit,
            SUM(f.units_processed) AS volume
        FROM fact_operations f
        JOIN dim_entities e ON f.entity_id = e.entity_id
        GROUP BY e.name, e.category
        ORDER BY revenue DESC;
    """
    df = conn.execute(query).df()
    conn.close()
    return df.to_dict(orient="records")
