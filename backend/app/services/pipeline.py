"""Monitor and run the medallion pipeline in data_engineering/ (bronze -> silver -> gold, DuckDB + Parquet).

Reads the lake's Parquet files with a throw-away in-memory DuckDB (never the dashboard's own database), so monitoring
can't lock or change your data. Running it calls medallion.run() exactly as `python medallion.py` does, and records a
history line so you can see runs over time.
"""
from __future__ import annotations

import importlib
import json
import sys
import threading
import time
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DE_DIR = ROOT / "data_engineering"
LAKE = DE_DIR / "lake"
SOURCES = {"clean": ROOT / "data_samples" / "operations_clean.csv", "messy": ROOT / "data_samples" / "operations_messy.csv"}
UPLOADED_EXPORT = DE_DIR / "landing" / "uploaded_export.csv"
HISTORY_MAX = 25
_run_lock = threading.Lock()


class PipelineError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _medallion():
    if not (DE_DIR / "medallion.py").exists():
        raise PipelineError("data_engineering/medallion.py wasn't found. Is the project folder complete?", 404)
    if str(DE_DIR) not in sys.path:
        sys.path.insert(0, str(DE_DIR))
    return importlib.import_module("medallion")


def _count(con, glob: str) -> int:
    try:
        return int(con.execute(f"SELECT count(*) FROM read_parquet('{glob}')").fetchone()[0])
    except Exception:
        return 0


def status(lake: Path | None = None) -> dict:
    import duckdb
    lake = lake or LAKE
    if not (lake / "state.json").exists():
        return {"exists": False, "message": "The pipeline hasn't run yet. Press Run to build bronze, silver and gold.", "history": _history(lake)}
    state = json.loads((lake / "state.json").read_text())
    con = duckdb.connect()
    p = lambda *a: (lake.joinpath(*a)).as_posix()
    bronze_files = sorted((lake / "bronze").glob("*.parquet"))
    layers = [
        {"layer": "bronze", "label": "Raw, as received", "rows": _count(con, p("bronze", "*.parquet")) if bronze_files else 0, "files": len(bronze_files)},
        {"layer": "silver", "label": "Typed, validated, de-duplicated", "rows": _count(con, p("silver", "ops.parquet")), "files": 1},
        {"layer": "quarantine", "label": "Rejected rows, with a reason", "rows": _count(con, p("silver", "quarantine.parquet")), "files": 1},
        {"layer": "gold", "label": "Business-ready daily totals", "rows": _count(con, p("gold", "daily.parquet")), "files": 2},
    ]
    reasons = []
    if (lake / "silver" / "quarantine.parquet").exists():
        reasons = [{"reason": r, "rows": n} for r, n in con.execute(
            f"SELECT reason, count(*) FROM read_parquet('{p('silver', 'quarantine.parquet')}') GROUP BY 1 ORDER BY 2 DESC").fetchall()]
    newest = state.get("watermark")
    stale = (date.today() - date.fromisoformat(newest)).days if newest else None
    silver = layers[1]["rows"]
    bronze_unique = None
    if bronze_files:
        try:
            bronze_unique = int(con.execute(f"SELECT count(DISTINCT fact_id) FROM read_parquet('{p('bronze', '*.parquet')}')").fetchone()[0])
        except Exception:
            pass
    checks = [
        {"name": "Freshness", "ok": stale is not None and stale <= 2, "detail": f"newest day {newest}, {stale} days old" if newest else "no data"},
        {"name": "Silver has rows", "ok": silver > 0, "detail": f"{silver:,} rows"},
        {"name": "Rows accounted for", "ok": bronze_unique is None or silver + layers[2]["rows"] >= 0.9 * bronze_unique,
         "detail": f"{silver:,} silver + {layers[2]['rows']:,} quarantined from {bronze_unique:,} distinct raw ids" if bronze_unique else "n/a"},
        {"name": "Quarantine under 20%", "ok": silver == 0 or layers[2]["rows"] <= 0.2 * (silver + layers[2]["rows"]),
         "detail": f"{layers[2]['rows']:,} rejected"},
    ]
    return {"exists": True, "watermark": newest, "loads": state.get("loads", 0), "layers": layers, "quarantine_reasons": reasons,
            "checks": checks, "history": _history(lake)}


def _history(lake: Path) -> list[dict]:
    try:
        return json.loads((lake / "history.json").read_text())[-HISTORY_MAX:][::-1]
    except Exception:
        return []


def export_uploaded(dest: Path | None = None) -> tuple[Path, int]:
    """Write the dashboard's current data (whatever was imported) to a CSV in the layout the pipeline expects."""
    import csv
    from app.services.db import fetch_all, get_cursor
    dest = dest or UPLOADED_EXPORT
    with get_cursor() as cur:
        rows = fetch_all(cur, """
            SELECT f.fact_id, STRFTIME(f.record_date, '%Y-%m-%d') AS record_date, f.entity_id,
                   COALESCE(e.name, f.entity_id) AS entity_name, COALESCE(e.category, '') AS category,
                   f.revenue, f.operational_cost, f.units_processed, f.duration_minutes, f.status,
                   e.baseline_target
            FROM fact_operations f LEFT JOIN dim_entities e ON f.entity_id = e.entity_id ORDER BY f.record_date, f.fact_id""")
    if not rows:
        raise PipelineError("The dashboard has no data to send through the pipeline. Import a CSV first.", 400)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cols = list(rows[0])
    with dest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow(["" if r[c] is None else r[c] for c in cols])
    return dest, len(rows)


def run(source: str = "clean", reset: bool = False, lake: Path | None = None) -> dict:
    lake = lake or LAKE
    if source not in SOURCES and source != "uploaded":
        raise PipelineError("source must be 'clean', 'messy' or 'uploaded'.")
    if source == "uploaded":
        path, _ = export_uploaded()
    else:
        path = SOURCES[source]
        if not path.exists():
            raise PipelineError(f"{path.name} wasn't found in data_samples/.", 404)
    if not _run_lock.acquire(blocking=False):
        raise PipelineError("A pipeline run is already in progress.", 409)
    try:
        m = _medallion()
        t0 = time.perf_counter()
        stats = m.run(path, lake, reset=reset)
        entry = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "source": source, "reset": reset,
                 "seconds": round(time.perf_counter() - t0, 2), **{k: stats.get(k) for k in
                 ("bronze_rows", "silver_rows", "quarantined", "gold_rows", "watermark_before", "watermark_after")}}
        hist = []
        try:
            hist = json.loads((lake / "history.json").read_text())
        except Exception:
            pass
        lake.mkdir(parents=True, exist_ok=True)
        (lake / "history.json").write_text(json.dumps((hist + [entry])[-HISTORY_MAX:], indent=1))
        return entry
    finally:
        _run_lock.release()
