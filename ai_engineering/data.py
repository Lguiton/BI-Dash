"""Shared: an in-memory DuckDB with the demo operations data (reads data_samples/operations_clean.csv)."""
from pathlib import Path
import duckdb

CSV = Path(__file__).resolve().parent.parent / "data_samples" / "operations_clean.csv"
SCHEMA = ("operations(fact_id, record_date DATE, entity_id, entity_name, category, revenue, operational_cost, "
          "units_processed, duration_minutes, status, baseline_target)")


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(f"CREATE VIEW operations AS SELECT * FROM read_csv('{CSV.as_posix()}', header=true)")
    return con


def is_select_only(sql: str) -> bool:
    """Guardrail #1 for any LLM-written SQL: single statement, SELECT/WITH only. (The dashboard's SQL Lab does the same.)"""
    s = sql.strip().rstrip(";").strip()
    if ";" in s:
        return False
    head = s.split(None, 1)[0].lower() if s else ""
    banned = ("insert", "update", "delete", "drop", "alter", "create", "copy", "attach", "pragma", "install", "load")
    return head in ("select", "with") and not any(f" {b} " in f" {s.lower()} " for b in banned)
