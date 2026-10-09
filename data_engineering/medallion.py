"""Medallion pipeline (bronze -> silver -> gold) with DuckDB + Parquet.

    python medallion.py                 # load everything new
    python medallion.py --source ../data_samples/operations_messy.csv
    python medallion.py --reset         # wipe the lake and start over

What each layer means
  bronze  raw rows exactly as received (all text) + load metadata. Never edited, so you can always replay.
  silver  typed, de-duplicated, validated. Bad rows go to quarantine with a reason, not into the void.
  gold    business-ready aggregates (what a dashboard reads).

Two properties interviewers love:
  * INCREMENTAL - a watermark (max record_date already loaded) means a re-run only touches new days.
  * IDEMPOTENT  - running the same file twice changes nothing (silver is keyed on fact_id; gold is rebuilt from silver).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
LAKE = HERE / "lake"
DEFAULT_SOURCE = HERE.parent / "data_samples" / "operations_clean.csv"
VALID_STATUS = ("Completed", "Delayed", "Cancelled", "Failed")


def _q(p: Path) -> str:
    return "'" + p.as_posix().replace("'", "''") + "'"


def run(source: Path = DEFAULT_SOURCE, lake: Path = LAKE, reset: bool = False) -> dict:
    if reset and lake.exists():
        shutil.rmtree(lake)
    for layer in ("bronze", "silver", "gold"):
        (lake / layer).mkdir(parents=True, exist_ok=True)
    state_path = lake / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"watermark": None, "loads": 0}
    con = duckdb.connect()  # in-memory engine; the lake is just files
    stats = {"watermark_before": state["watermark"]}

    # ---- BRONZE: read everything as text, keep only rows newer than the watermark ----
    con.execute(f"CREATE TABLE src AS SELECT * FROM read_csv({_q(source)}, header=true, all_varchar=true)")
    wm = state["watermark"]
    con.execute("CREATE TABLE new_rows AS SELECT * FROM src WHERE ? IS NULL OR record_date >= ?", [wm, wm])
    # `>=` re-reads the watermark day on purpose (late rows for that day); silver's key makes that safe.
    stats["bronze_rows"] = con.execute("SELECT count(*) FROM new_rows").fetchone()[0]
    load_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    if stats["bronze_rows"]:
        con.execute(f"COPY (SELECT *, '{load_id}' AS _load_id, now() AS _loaded_at FROM new_rows) "
                    f"TO {_q(lake / 'bronze' / f'ops_{load_id}.parquet')} (FORMAT parquet)")

    # ---- SILVER: rebuild from ALL bronze files, so the result never depends on how many runs it took ----
    bronze_glob = _q(lake / "bronze" / "*.parquet")
    if not list((lake / "bronze").glob("*.parquet")):
        stats.update(silver_rows=0, quarantined=0, gold_rows=0)
        return stats
    con.execute(f"""
        CREATE TABLE typed AS
        SELECT fact_id,
               TRY_CAST(record_date AS DATE)            AS record_date,
               upper(trim(entity_id))                   AS entity_id,
               trim(entity_name)                        AS entity_name,
               trim(category)                           AS category,
               TRY_CAST(revenue AS DOUBLE)              AS revenue,
               TRY_CAST(operational_cost AS DOUBLE)     AS operational_cost,
               TRY_CAST(units_processed AS INTEGER)     AS units_processed,
               TRY_CAST(duration_minutes AS INTEGER)    AS duration_minutes,
               trim(status)                             AS status,
               TRY_CAST(baseline_target AS DOUBLE)      AS baseline_target,
               _loaded_at
        FROM read_parquet({bronze_glob})""")
    con.execute(f"""
        CREATE TABLE verdict AS
        SELECT *, CASE
            WHEN fact_id IS NULL OR fact_id = ''                       THEN 'missing fact_id'
            WHEN record_date IS NULL                                   THEN 'unparseable date'
            WHEN revenue IS NULL OR revenue < 0                        THEN 'bad revenue'
            WHEN operational_cost IS NULL OR operational_cost < 0      THEN 'bad cost'
            WHEN status NOT IN {VALID_STATUS}                          THEN 'unknown status'
            ELSE NULL END AS reason
        FROM typed""")
    # Latest copy of each fact_id wins (this is the de-duplication / upsert rule).
    con.execute("""
        CREATE TABLE silver AS
        SELECT * EXCLUDE (_loaded_at, reason, rn) FROM (
            SELECT *, row_number() OVER (PARTITION BY fact_id ORDER BY _loaded_at DESC) AS rn
            FROM verdict WHERE reason IS NULL) WHERE rn = 1""")
    con.execute(f"COPY silver TO {_q(lake / 'silver' / 'ops.parquet')} (FORMAT parquet)")
    con.execute(f"COPY (SELECT * EXCLUDE (_loaded_at) FROM verdict WHERE reason IS NOT NULL) "
                f"TO {_q(lake / 'silver' / 'quarantine.parquet')} (FORMAT parquet)")
    stats["silver_rows"] = con.execute("SELECT count(*) FROM silver").fetchone()[0]
    stats["quarantined"] = con.execute("SELECT count(*) FROM verdict WHERE reason IS NOT NULL").fetchone()[0]

    # ---- GOLD: aggregates, always rebuilt from silver ----
    con.execute("""
        CREATE TABLE gold_daily AS
        SELECT record_date, sum(revenue) AS revenue, sum(operational_cost) AS cost,
               sum(revenue - operational_cost) AS profit,
               sum(revenue - operational_cost) / nullif(sum(revenue), 0) AS margin,
               count(*) AS records
        FROM silver GROUP BY 1 ORDER BY 1""")
    con.execute("""
        CREATE TABLE gold_entity AS
        SELECT entity_id, entity_name, sum(revenue) AS revenue, sum(revenue - operational_cost) AS profit,
               sum(operational_cost) / nullif(sum(baseline_target), 0) AS cost_vs_budget
        FROM silver GROUP BY 1, 2 ORDER BY profit DESC""")
    con.execute(f"COPY gold_daily TO {_q(lake / 'gold' / 'daily.parquet')} (FORMAT parquet)")
    con.execute(f"COPY gold_entity TO {_q(lake / 'gold' / 'entity.parquet')} (FORMAT parquet)")
    stats["gold_rows"] = con.execute("SELECT count(*) FROM gold_daily").fetchone()[0]

    state["watermark"] = con.execute("SELECT max(record_date)::VARCHAR FROM silver").fetchone()[0]
    state["loads"] += 1
    state_path.write_text(json.dumps(state, indent=2))
    stats["watermark_after"] = state["watermark"]
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument("--reset", action="store_true")
    a = ap.parse_args()
    for k, v in run(a.source, reset=a.reset).items():
        print(f"{k:18s} {v}")
    sys.exit(0)
