"""One view of "your data" and which parts of the project can use it right now.

Every page reads the same DuckDB tables, so importing a CSV feeds all five careers at once. This endpoint states that
plainly and checks, per career, whether the data you have is big enough for that career's exercises."""
from fastapi import APIRouter

from app.services import llm_router
from app.services.db import fetch_one, get_cursor

router = APIRouter(prefix="/api/dataset", tags=["dataset"])


def _ai_ready() -> bool:
    try:
        return any(p["configured"] for p in llm_router.status()["providers"])
    except Exception:
        return False


@router.get("")
def dataset():
    with get_cursor() as cur:
        info = fetch_one(cur, """
            SELECT COUNT(*) AS rows, COUNT(duration_minutes) AS with_duration, COUNT(DISTINCT entity_id) AS entities, COUNT(DISTINCT record_date) AS days,
                   STRFTIME(MIN(record_date), '%Y-%m-%d') AS date_min, STRFTIME(MAX(record_date), '%Y-%m-%d') AS date_max,
                   COUNT(DISTINCT CASE WHEN ISODOW(record_date) >= 6 THEN record_date END) AS weekend_days,
                   COUNT(DISTINCT CASE WHEN ISODOW(record_date) < 6 THEN record_date END) AS weekday_days
            FROM fact_operations""")
    n, ents, days = info["rows"], info["entities"], info["days"]

    def check(ok: bool, need: str, have: str) -> dict:
        return {"ok": ok, "need": need, "have": have}

    careers = [
        {"id": "analyst", "name": "Data Analyst", "uses": "KPIs, trends, quality checks, SQL Lab, reports",
         "checks": [check(n > 0, "at least 1 record", f"{n:,} records")]},
        {"id": "scientist", "name": "Data Scientist", "uses": "Weekend t-test, entity clusters, correlations",
         "checks": [check(info["weekend_days"] >= 5 and info["weekday_days"] >= 5, "5+ weekend days and 5+ weekdays",
                          f"{info['weekend_days']} weekend, {info['weekday_days']} weekday days"),
                    check(ents >= 4, "4+ entities to cluster", f"{ents} entities"),
                    check(n >= 10, "10+ records for correlations", f"{n:,} records")]},
        {"id": "ml", "name": "Machine Learning", "uses": "ML Lab models, experiment log",
         "checks": [check(n >= 100, "100+ records", f"{n:,} records"), check(days >= 20, "20+ distinct days for a time split", f"{days} days")]},
        {"id": "engineering", "name": "Data Engineering", "uses": "Pipeline monitor (choose \"Your uploaded data\"), exports, Postgres lab",
         "checks": [check(n > 0, "at least 1 record to send through the pipeline", f"{n:,} records")]},
        {"id": "pm", "name": "Project & Product", "uses": "Board and metrics (your own items), product analytics from your records",
         "checks": [check(n >= 20 and days >= 7, "20+ records over 7+ days for activity and retention", f"{n:,} records, {days} days")]},
        {"id": "sysanalyst", "name": "Systems Analyst", "uses": "Data dictionary, process analysis, calculators, requirements",
         "checks": [check(info["with_duration"] >= 10, "10+ records with duration_minutes for process analysis", f"{info['with_duration']:,} with a duration")]},
        {"id": "fullstack", "name": "Full Stack Developer", "uses": "API map and tester, scaffolds from your tables, codebase and stack facts",
         "checks": [check(n > 0, "at least 1 record so the scaffolds have a table to work on", f"{n:,} records")]},
        {"id": "ai", "name": "AI Engineering", "uses": "AI Lab questions and charts over your tables",
         "checks": [check(n > 0, "at least 1 record", f"{n:,} records"), check(_ai_ready(), "an API key in backend/.env", "key found" if _ai_ready() else "no key yet")]},
    ]
    for c in careers:
        c["ready"] = all(k["ok"] for k in c["checks"])
    return {**info, "careers": careers}
