"""04 - ETL vs ELT on the same messy file.

ETL  (Extract -> Transform -> Load): clean in Python/pandas BEFORE loading anything.
ELT  (Extract -> Load -> Transform): load the raw file as-is into a staging table, then clean with SQL
                                      inside the database (DuckDB here; Snowflake/BigQuery in industry).

Both pipelines should produce the SAME clean rows. This script proves it, and shows the trade-offs.
Run:  python 04_etl_vs_elt.py        (uses an in-memory DuckDB, so it never touches the dashboard's database)
"""
import duckdb
import pandas as pd

from common import OUT, banner, ensure_sample

RAW = ensure_sample(messy=True)
STATUS = {"completed": "Completed", "complete": "Completed", "done": "Completed", "": "Completed",
          "delayed": "Delayed", "cancelled": "Cancelled", "canceled": "Cancelled"}


# ----------------------------------------------------------------------------- ETL
def etl(path) -> pd.DataFrame:
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)            # Extract
    df = raw.copy()                                                      # Transform (in Python, in memory)
    for c in ["fact_id", "entity_id", "entity_name", "category", "status"]:
        df[c] = df[c].str.strip()
    df["category"] = df["category"].str.capitalize()
    df["status"] = df["status"].str.lower().map(STATUS)
    for c in ["revenue", "operational_cost", "baseline_target"]:
        df[c] = pd.to_numeric(df[c].str.replace(r"[$,]", "", regex=True), errors="coerce")
    df["record_date"] = pd.to_datetime(df["record_date"], format="%Y-%m-%d", errors="coerce").fillna(
        pd.to_datetime(df["record_date"], format="%m/%d/%Y", errors="coerce"))
    ok = df["record_date"].notna() & df["revenue"].ge(0) & df["operational_cost"].ge(0)   # NaN fails ge()
    return (df[ok].drop_duplicates("fact_id")
              .assign(record_date=lambda d: d["record_date"].dt.date)
              .sort_values("fact_id").reset_index(drop=True))            # (the Load step is writing/POSTing this)


# ----------------------------------------------------------------------------- ELT
ELT_SQL = """
CREATE TABLE stg_operations_raw AS                      -- LOAD first: everything stays text, nothing is lost
SELECT * FROM read_csv(?, header = true, all_varchar = true);

CREATE TABLE operations_clean AS                        -- then TRANSFORM with SQL, inside the engine
WITH typed AS (
  SELECT
    trim(fact_id)                                        AS fact_id,
    COALESCE(TRY_STRPTIME(record_date, '%Y-%m-%d'),
             TRY_STRPTIME(record_date, '%m/%d/%Y'))::DATE AS record_date,
    trim(entity_id)                                      AS entity_id,
    trim(entity_name)                                    AS entity_name,
    upper(left(trim(category), 1)) || lower(substr(trim(category), 2)) AS category,
    TRY_CAST(replace(replace(revenue, '$', ''), ',', '') AS DOUBLE)           AS revenue,
    TRY_CAST(replace(replace(operational_cost, '$', ''), ',', '') AS DOUBLE)  AS operational_cost,
    TRY_CAST(units_processed AS INTEGER)                 AS units_processed,
    TRY_CAST(duration_minutes AS INTEGER)                AS duration_minutes,
    CASE lower(trim(status))
      WHEN 'completed' THEN 'Completed' WHEN 'complete' THEN 'Completed' WHEN 'done' THEN 'Completed'
      WHEN '' THEN 'Completed' WHEN 'delayed' THEN 'Delayed'
      WHEN 'cancelled' THEN 'Cancelled' WHEN 'canceled' THEN 'Cancelled' END  AS status,
    TRY_CAST(baseline_target AS DOUBLE)                  AS baseline_target
  FROM stg_operations_raw
),
valid AS (
  SELECT * FROM typed
  WHERE record_date IS NOT NULL AND revenue >= 0 AND operational_cost >= 0
),
dedup AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY fact_id ORDER BY record_date) AS rn FROM valid
)
SELECT * EXCLUDE (rn) FROM dedup WHERE rn = 1;
"""


def elt(path) -> pd.DataFrame:
    con = duckdb.connect(":memory:")
    statements = [s for s in ELT_SQL.split(";") if s.strip()]
    con.execute(statements[0], [str(path)])
    con.execute(statements[1])
    out = con.execute("SELECT * FROM operations_clean ORDER BY fact_id").df()
    # Bonus of ELT: the raw data is still there to audit what was rejected, with plain SQL.
    rejected = con.execute("SELECT COUNT(*) FROM stg_operations_raw").fetchone()[0] - len(out)
    print(f"ELT: staging table keeps all {rejected + len(out):,} raw rows; {rejected:,} were filtered or deduplicated.")
    return out


if __name__ == "__main__":
    banner("Run both pipelines on operations_messy.csv")
    a, b = etl(RAW), elt(RAW)
    print(f"ETL result: {len(a):,} rows | ELT result: {len(b):,} rows")

    cols = ["fact_id", "record_date", "entity_id", "category", "status", "revenue", "operational_cost"]
    same_ids = list(a["fact_id"]) == list(b["fact_id"])
    same_rev = abs(a["revenue"].sum() - b["revenue"].sum()) < 0.01
    same_cat = set(a["category"]) == set(b["category"])
    print(f"same fact_ids: {same_ids} | same revenue total: {same_rev} (${a['revenue'].sum():,.2f}) | same categories: {same_cat} {sorted(set(b['category']))}")
    if not (same_ids and same_rev and same_cat):
        raise SystemExit("The two pipelines disagree: that is a bug in one of them. Investigate!")

    b.assign(record_date=pd.to_datetime(b["record_date"]).dt.strftime("%Y-%m-%d")).to_csv(OUT / "operations_from_elt.csv", index=False)
    print(f"\nWrote {OUT / 'operations_from_elt.csv'} (import it into the dashboard to see clean data)")

    banner("Trade-offs to think about")
    print("""ETL  + transformation logic lives in code you can unit-test and version (pandas, dbt-core, Airflow tasks)
     + only clean data reaches the warehouse (good for strict compliance)
     - the raw data is gone; if a rule was wrong you must re-extract from the source
     - limited by the memory of the machine running the transform
ELT  + raw data is preserved in a staging layer, so you can re-run or change rules any time
     + the warehouse engine does the heavy lifting in parallel on huge data
     - raw (possibly sensitive/dirty) data sits in the warehouse; needs governance
     - business logic is SQL, so it needs tests too (dbt tests, data-quality checks)

YOUR TURN
1. Add a rule: also reject rows where operational_cost > 5x the entity's median cost. Do it in BOTH pipelines.
2. Quarantine instead of drop: write the rejected rows (with a reason column) to a CSV in each pipeline.
3. SCD (Slowly Changing Dimension): entity 'Zone North 89011' moves from Logistics to Fleet on 2026-07-01.
   Design a dim_entities table that keeps BOTH versions (valid_from, valid_to, is_current) so past reports
   do not change. Write the SQL that finds the category in effect on each fact's record_date.""")
