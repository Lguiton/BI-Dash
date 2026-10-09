"""Serves the Apache practice material (Spark, Airflow, Superset) to the dashboard's Apache page.

The code shown in the UI is read straight from apache_practice/ so what you see is exactly what runs.
"""
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(prefix="/api/apache", tags=["apache"])
BASE = Path(__file__).resolve().parents[3] / "apache_practice"

TOOLS = [
    {
        "id": "spark", "name": "Apache Spark", "role": "Transform / analyze (ELT)",
        "summary": "A distributed data-processing engine. Same questions as SQL Lab, written as DataFrame code or Spark SQL, "
                   "built to scale from this laptop dataset to billions of rows.",
        "concepts": ["ETL vs ELT", "Window functions", "Non-additive measures", "Parquet / data lake layout", "Lazy evaluation"],
        "steps": [
            "Install Java 17+ and run: pip install pyspark",
            "Start the backend (optional: Spark falls back to the sample CSV).",
            "From the project root run: python apache_practice/spark/01_spark_basics.py",
            "Compare each printed result with the matching SQL Lab exercise.",
            "Challenge: add a 'cost spikes' query (SQL Lab exercise cost-spikes) using F.avg + a window.",
        ],
        "files": [("spark/01_spark_basics.py", "python")],
    },
    {
        "id": "airflow", "name": "Apache Airflow", "role": "Orchestrate / schedule (ETL)",
        "summary": "A workflow orchestrator. It doesn't crunch data; it runs your steps in order, on a schedule, with retries "
                   "and monitoring. The DAG calls plain Python functions that you can also run without Airflow.",
        "concepts": ["ETL stages", "Scheduling & retries", "Data-quality gate", "Idempotent loads", "Monitoring"],
        "steps": [
            "Try the logic first, no Airflow needed: python apache_practice/airflow/etl_steps.py",
            "Airflow needs Linux/macOS/WSL2 or Docker: pip install \"apache-airflow==3.*\" (see Airflow docs for constraints).",
            "Copy etl_steps.py and dags/bi_etl_dag.py into $AIRFLOW_HOME/dags, then run: airflow standalone",
            "Open http://localhost:8080, un-pause 'bi_daily_etl' and trigger it.",
            "Break it on purpose (wrong BI_API_URL) and watch retries and skipped downstream tasks.",
        ],
        "files": [("airflow/etl_steps.py", "python"), ("airflow/dags/bi_etl_dag.py", "python")],
    },
    {
        "id": "superset", "name": "Apache Superset", "role": "Visualize (BI front end)",
        "summary": "An open-source BI web app, in the same family as Tableau. Point it at the exported data, define metrics, "
                   "build charts and a filtered dashboard.",
        "concepts": ["KPIs & metrics", "Dashboard design (Z-pattern)", "Time grains", "Non-additive measures", "Drill-down"],
        "steps": [
            "Download http://localhost:8020/api/export/operations?format=csv",
            "Run Superset in Docker (commands in the guide), log in at http://localhost:8088",
            "Upload the CSV to a SQLite database and mark record_date as temporal.",
            "Add the margin_pct metric as SUM(profit)/SUM(revenue), not an average of margins.",
            "Build the six charts in the table and combine them in one dashboard with native filters.",
        ],
        "files": [("superset/README.md", "markdown")],
    },
]


@router.get("/tools")
def list_tools():
    out = []
    for t in TOOLS:
        files = [{"path": p, "language": lang, "content": (BASE / p).read_text(encoding="utf-8")} for p, lang in t["files"]]
        out.append({**{k: v for k, v in t.items() if k != "files"}, "files": files})
    return {"tools": out}
