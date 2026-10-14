"""DuckDB access.

One process-wide connection, with a short-lived cursor per request. This avoids
re-opening the database file on every call and the file-lock conflicts that come
with multiple read-write connections. Cursors are always closed, even on errors.
"""
import threading
from contextlib import contextmanager

import duckdb

from app.config import db_path, seed_demo_enabled

_lock = threading.RLock()
_conn: duckdb.DuckDBPyConnection | None = None
_path: "str | None" = None          # set by workspaces.activate(); falls back to the Practice file


def _root() -> duckdb.DuckDBPyConnection:
    global _conn
    with _lock:
        if _conn is None:
            from pathlib import Path
            path = Path(_path) if _path else db_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            _conn = duckdb.connect(str(path))
            # The SQL Lab runs user-written queries. Turn off file/network access for the whole
            # engine (read_csv('/etc/passwd'), COPY ... TO, ATTACH, httpfs...). All app I/O
            # (CSV import/export) is done in Python, so nothing legitimate needs it. This
            # setting cannot be switched back on without reopening the database.
            _conn.execute("SET enable_external_access = false")
        return _conn


@contextmanager
def get_cursor():
    cur = _root().cursor()
    try:
        yield cur
    finally:
        cur.close()


def close_connection() -> None:
    """Close the shared connection (shutdown, and between tests)."""
    global _conn, _path
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None
        _path = None


def use_path(path) -> None:
    """Point the shared connection at another database file (workspace switch). The old one is closed first."""
    global _conn, _path
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None
        _path = str(path)


@contextmanager
def exclusive():
    """Close the connection while the caller copies/replaces the database file (backup, restore). It reopens on next use."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None
        yield


def fetch_all(cur, sql: str, params: list | None = None) -> list[dict]:
    """Run a query and return rows as plain dicts (no pandas needed)."""
    res = cur.execute(sql, params or [])
    cols = [d[0] for d in res.description]
    return [dict(zip(cols, row)) for row in res.fetchall()]


def fetch_one(cur, sql: str, params: list | None = None) -> dict:
    rows = fetch_all(cur, sql, params)
    return rows[0] if rows else {}


SEED_ENTITIES = [
    ("ENT-01", "Zone North 89011", "Logistics", 120.0),
    ("ENT-02", "Zone West Central", "Express", 95.0),
    ("ENT-03", "Downtown Corridor", "Fleet", 140.0),
    ("ENT-04", "Henderson South", "Logistics", 110.0),
]
SEED_FACTS = [
    ("F-101", "2026-10-01", "ENT-01", 450.00, 112.50, 48, 240, "Completed"),
    ("F-102", "2026-10-02", "ENT-01", 520.00, 130.00, 52, 260, "Completed"),
    ("F-103", "2026-10-03", "ENT-02", 380.00, 95.00, 40, 210, "Completed"),
    ("F-104", "2026-10-04", "ENT-03", 610.00, 180.00, 65, 300, "Completed"),
    ("F-105", "2026-10-05", "ENT-04", 490.00, 115.00, 50, 250, "Completed"),
    ("F-106", "2026-10-06", "ENT-01", 540.00, 125.00, 56, 270, "Completed"),
]


def init_bi_schema(seed: bool | None = None) -> None:
    """Create the tables and views. `seed` defaults to the BI_SEED_DEMO setting; the Real workspace passes False."""
    with get_cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS dim_entities (
                entity_id VARCHAR PRIMARY KEY,
                name VARCHAR,
                category VARCHAR,
                baseline_target DOUBLE
            );
            CREATE TABLE IF NOT EXISTS fact_operations (
                fact_id VARCHAR PRIMARY KEY,
                record_date DATE,
                entity_id VARCHAR,
                revenue DOUBLE,
                operational_cost DOUBLE,
                units_processed INTEGER,
                duration_minutes INTEGER,
                status VARCHAR
            );
            CREATE TABLE IF NOT EXISTS app_meta (
                key VARCHAR PRIMARY KEY,
                value VARCHAR
            );
            """
        )
        _create_views(cur)

        # Seed demo rows once, only into a brand-new empty warehouse. The marker
        # stops demo data from coming back after you replace it with real data.
        seeded = cur.execute("SELECT 1 FROM app_meta WHERE key = 'seeded'").fetchone()
        n_facts = cur.execute("SELECT COUNT(*) FROM fact_operations").fetchone()[0]
        if not seeded:
            if n_facts == 0 and (seed_demo_enabled() if seed is None else seed):
                cur.executemany("INSERT INTO dim_entities VALUES (?, ?, ?, ?)", SEED_ENTITIES)
                cur.executemany("INSERT INTO fact_operations VALUES (?, ?, ?, ?, ?, ?, ?, ?)", SEED_FACTS)
            cur.execute("INSERT INTO app_meta VALUES ('seeded', '1')")


def _create_views(cur) -> None:
    """Views for SQL practice: a generated date dimension and a denormalized "flat" table.

    dim_date mirrors the date dimension you build in a real star schema; v_operations_flat is
    the wide, one-row-per-fact table BI tools like Tableau prefer. Both are recreated on startup.
    """
    cur.execute(
        """
        CREATE OR REPLACE VIEW dim_date AS
        SELECT CAST(d AS DATE)            AS date_key,
               YEAR(d)                    AS year,
               QUARTER(d)                 AS quarter,
               MONTH(d)                   AS month,
               MONTHNAME(d)               AS month_name,
               WEEKOFYEAR(d)              AS week_of_year,
               DAYOFWEEK(d)               AS day_of_week,   -- 0 = Sunday
               DAYNAME(d)                 AS day_name,
               DAYOFWEEK(d) IN (0, 6)     AS is_weekend
        FROM generate_series(
               (SELECT MIN(record_date) FROM fact_operations),
               (SELECT MAX(record_date) FROM fact_operations),
               INTERVAL 1 DAY) AS t(d)
        """
    )
    cur.execute(
        """
        CREATE OR REPLACE VIEW v_operations_flat AS
        SELECT f.fact_id,
               f.record_date,
               dd.year, dd.quarter, dd.month, dd.month_name, dd.day_name, dd.is_weekend,
               f.entity_id,
               COALESCE(e.name, f.entity_id)                AS entity_name,
               e.category,
               e.baseline_target                            AS cost_budget_per_record,
               f.revenue,
               f.operational_cost,
               f.revenue - f.operational_cost               AS profit,
               (f.revenue - f.operational_cost) / NULLIF(f.revenue, 0) AS margin,
               f.units_processed,
               f.duration_minutes,
               f.status
        FROM fact_operations f
        LEFT JOIN dim_entities e  ON f.entity_id = e.entity_id
        LEFT JOIN dim_date dd     ON f.record_date = dd.date_key
        """
    )
