"""Data-quality report: the checks you would run before trusting a dashboard.

Each check returns a status (ok / warn / bad), how many rows are affected, and a few sample rows.
Mirrors the quality gate in apache_practice/airflow/etl_steps.py.
"""
from fastapi import APIRouter

from app.services.db import fetch_all, get_cursor

router = APIRouter(prefix="/api/quality", tags=["quality"])

FACT_COLS = ["fact_id", "record_date", "entity_id", "revenue", "operational_cost",
             "units_processed", "duration_minutes", "status"]


def _check(cur, cid, title, why, sql, sample_sql, bad_if_any=True, total_sql=None):
    count = cur.execute(sql).fetchone()[0]
    sample = fetch_all(cur, sample_sql) if count else []
    status = "ok" if count == 0 else ("bad" if bad_if_any else "warn")
    return {"id": cid, "title": title, "why": why, "status": status, "count": count,
            "sample": [{k: (str(v) if not isinstance(v, (int, float, str, type(None))) else v) for k, v in r.items()} for r in sample]}


@router.get("")
def report():
    with get_cursor() as cur:
        facts = cur.execute("SELECT COUNT(*) FROM fact_operations").fetchone()[0]
        entities = cur.execute("SELECT COUNT(*) FROM dim_entities").fetchone()[0]
        nulls = []
        for c in FACT_COLS:
            n = cur.execute(f"SELECT COUNT(*) FROM fact_operations WHERE {c} IS NULL").fetchone()[0]
            nulls.append({"column": c, "nulls": n, "null_pct": round(100 * n / facts, 2) if facts else 0.0})
        checks = [
            _check(cur, "missing_required", "Missing required values",
                   "Rows without a date, entity, revenue or cost can't be aggregated correctly.",
                   "SELECT COUNT(*) FROM fact_operations WHERE record_date IS NULL OR entity_id IS NULL OR revenue IS NULL OR operational_cost IS NULL",
                   "SELECT * FROM fact_operations WHERE record_date IS NULL OR entity_id IS NULL OR revenue IS NULL OR operational_cost IS NULL LIMIT 5"),
            _check(cur, "negative_values", "Negative revenue, cost or units",
                   "Usually a sign error or a refund recorded in the wrong column.",
                   "SELECT COUNT(*) FROM fact_operations WHERE revenue < 0 OR operational_cost < 0 OR units_processed < 0",
                   "SELECT * FROM fact_operations WHERE revenue < 0 OR operational_cost < 0 OR units_processed < 0 LIMIT 5"),
            _check(cur, "bad_duration", "Zero or negative duration",
                   "A record can't take 0 minutes or less.",
                   "SELECT COUNT(*) FROM fact_operations WHERE duration_minutes <= 0",
                   "SELECT * FROM fact_operations WHERE duration_minutes <= 0 LIMIT 5"),
            _check(cur, "loss_rows", "Cost higher than revenue",
                   "Not necessarily wrong, but worth a look: these rows lose money.",
                   "SELECT COUNT(*) FROM fact_operations WHERE operational_cost > revenue",
                   "SELECT * FROM fact_operations WHERE operational_cost > revenue ORDER BY operational_cost - revenue DESC LIMIT 5",
                   bad_if_any=False),
            _check(cur, "orphan_facts", "Facts with no matching entity",
                   "Referential integrity: every fact's entity_id should exist in dim_entities.",
                   "SELECT COUNT(*) FROM fact_operations f LEFT JOIN dim_entities e USING (entity_id) WHERE e.entity_id IS NULL",
                   "SELECT f.* FROM fact_operations f LEFT JOIN dim_entities e USING (entity_id) WHERE e.entity_id IS NULL LIMIT 5"),
            _check(cur, "unused_entities", "Entities with no facts",
                   "Dimension rows nothing refers to. Harmless, but often leftovers.",
                   "SELECT COUNT(*) FROM dim_entities e WHERE NOT EXISTS (SELECT 1 FROM fact_operations f WHERE f.entity_id = e.entity_id)",
                   "SELECT * FROM dim_entities e WHERE NOT EXISTS (SELECT 1 FROM fact_operations f WHERE f.entity_id = e.entity_id) LIMIT 5",
                   bad_if_any=False),
            _check(cur, "duplicate_business_key", "Several rows for the same entity and day",
                   "Different fact_ids but the same entity and date can mean the same event was loaded twice.",
                   "SELECT COUNT(*) FROM (SELECT entity_id, record_date FROM fact_operations GROUP BY 1, 2 HAVING COUNT(*) > 1)",
                   "SELECT entity_id, STRFTIME(record_date, '%Y-%m-%d') AS record_date, COUNT(*) AS rows FROM fact_operations GROUP BY 1, 2 HAVING COUNT(*) > 1 LIMIT 5",
                   bad_if_any=False),
            _check(cur, "date_gaps", "Entities with missing days",
                   "Days between an entity's first and last record that have no record. Gaps distort trends and forecasts.",
                   """SELECT COUNT(*) FROM (
                        SELECT entity_id FROM fact_operations GROUP BY entity_id
                        HAVING DATE_DIFF('day', MIN(record_date), MAX(record_date)) + 1 > COUNT(DISTINCT record_date))""",
                   """SELECT entity_id,
                             DATE_DIFF('day', MIN(record_date), MAX(record_date)) + 1 - COUNT(DISTINCT record_date) AS missing_days
                      FROM fact_operations GROUP BY entity_id
                      HAVING DATE_DIFF('day', MIN(record_date), MAX(record_date)) + 1 > COUNT(DISTINCT record_date)
                      ORDER BY missing_days DESC LIMIT 5""",
                   bad_if_any=False),
            _check(cur, "no_budget", "Entities without a usable cost budget",
                   "baseline_target must be above 0 for the 'cost vs budget' measures to work.",
                   "SELECT COUNT(*) FROM dim_entities WHERE baseline_target IS NULL OR baseline_target <= 0",
                   "SELECT * FROM dim_entities WHERE baseline_target IS NULL OR baseline_target <= 0 LIMIT 5",
                   bad_if_any=False),
        ]
        statuses = fetch_all(cur, "SELECT COALESCE(status, '(missing)') AS status, COUNT(*) AS rows FROM fact_operations GROUP BY 1 ORDER BY 2 DESC")
    passed = sum(1 for c in checks if c["status"] == "ok")
    return {"facts": facts, "entities": entities, "nulls": nulls, "checks": checks, "statuses": statuses,
            "score_pct": round(100 * passed / len(checks)), "passed": passed, "total_checks": len(checks)}
