"""Load the practice data into PostgreSQL: a real star schema with keys, constraints and types.

    docker compose up -d
    pip install "psycopg[binary]"
    python load_data.py                 # reads ../data_samples/operations_clean.csv (use --messy for the dirty file)

Safe to re-run: it rebuilds the `bi` schema each time. Connection comes from PG_DSN (default: the docker-compose database).
"""
import argparse
import csv
import os
import sys
from pathlib import Path

import psycopg

DSN = os.environ.get("PG_DSN", "postgresql://postgres:bi_practice@127.0.0.1:5433/bi")
DATA = Path(__file__).resolve().parent.parent / "data_samples"

DDL = """
DROP SCHEMA IF EXISTS bi CASCADE;
CREATE SCHEMA bi;
CREATE TABLE bi.dim_entities (
    entity_id        text PRIMARY KEY,
    name             text NOT NULL,
    category         text,
    baseline_target  numeric(10,2) NOT NULL CHECK (baseline_target >= 0)   -- cost budget per record
);
CREATE TABLE bi.fact_operations (
    fact_id           text PRIMARY KEY,
    record_date       date NOT NULL,
    entity_id         text NOT NULL REFERENCES bi.dim_entities(entity_id),
    revenue           numeric(12,2) NOT NULL CHECK (revenue >= 0),
    operational_cost  numeric(12,2) NOT NULL CHECK (operational_cost >= 0),
    units_processed   integer,
    duration_minutes  integer,
    status            text
);
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--messy", action="store_true", help="load operations_messy.csv (expect constraint violations: that's the lesson)")
    ap.add_argument("--analyze", action="store_true", default=True)
    a = ap.parse_args()
    path = DATA / ("operations_messy.csv" if a.messy else "operations_clean.csv")
    if not path.exists():
        sys.exit(f"{path} not found. Run: python scripts/generate_sample_data.py{' --messy' if a.messy else ''}")
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    with psycopg.connect(DSN) as conn:
        conn.execute(DDL)
        ents = {}
        for r in rows:
            ents.setdefault(r["entity_id"], (r["entity_id"], r["entity_name"], r["category"] or None, r["baseline_target"]))
        with conn.cursor() as cur:
            cur.executemany("INSERT INTO bi.dim_entities VALUES (%s,%s,%s,%s)", list(ents.values()))
            try:
                with cur.copy("COPY bi.fact_operations FROM STDIN") as cp:
                    for r in rows:
                        cp.write_row((r["fact_id"], r["record_date"], r["entity_id"], r["revenue"], r["operational_cost"],
                                      r["units_processed"] or None, r["duration_minutes"] or None, r["status"] or None))
            except psycopg.Error as e:
                conn.rollback()
                sys.exit(f"Load rejected by the database (that is constraints doing their job):\n  {str(e).splitlines()[0]}\n"
                         "Clean the data first (notebook 03 or the medallion pipeline) and try again.")
        conn.execute("ANALYZE bi.fact_operations")
        n = conn.execute("SELECT count(*) FROM bi.fact_operations").fetchone()[0]
    print(f"Loaded {n:,} facts and {len(ents)} entities into schema bi at {DSN.split('@')[-1]}")


if __name__ == "__main__":
    main()
