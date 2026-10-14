"""Airflow DAG: a daily extract -> transform -> quality gate -> load -> verify pipeline.

    extract >> transform >> validate >> load >> verify

Setup (Airflow runs on Linux/macOS/WSL; on Windows use WSL2 or Docker):
    # Use a fresh virtualenv and Airflow's constraints file. A plain `pip install apache-airflow` pulls a newer
    # SQLAlchemy than Airflow supports and crashes on start (this was hit when testing this project).
    V=3.1.8; PY=$(python -c 'import sys;print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
    pip install "apache-airflow==$V" --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-$V/constraints-$PY.txt"
    export AIRFLOW_HOME=~/airflow
    export BI_API_URL=http://localhost:8020      # the dashboard backend must be running
    mkdir -p $AIRFLOW_HOME/dags
    cp apache_practice/airflow/etl_steps.py apache_practice/airflow/dags/bi_etl_dag.py $AIRFLOW_HOME/dags/
    airflow standalone                           # prints an admin password; UI at http://localhost:8080

Tested without the UI: `airflow db migrate && airflow dags reserialize && airflow dags test bi_daily_etl 2026-10-08`
runs all five tasks (extract, transform, validate, load, verify) and ends in state=success.

Then open the DAG "bi_daily_etl", un-pause it, and trigger a run. Try breaking it on purpose:
set BI_API_URL to a wrong port and watch retries, the failed task, and the skipped downstream tasks.

Concepts from class this maps to: ETL stages, scheduling, idempotent loads (INSERT OR REPLACE by
fact_id means re-running a day is safe), data-quality gates, monitoring.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow.sdk import dag, task  # Airflow 3. On Airflow 2.x use: from airflow.decorators import dag, task

import etl_steps  # sits next to this file in $AIRFLOW_HOME/dags


@dag(
    dag_id="bi_daily_etl",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,                      # don't backfill every day since start_date
    default_args={"retries": 2, "retry_delay": timedelta(minutes=1)},
    tags=["bi", "practice"],
)
def bi_daily_etl():
    @task
    def extract(run_id=None) -> str:
        return etl_steps.extract(run_id or "scheduled")

    @task
    def transform(raw_path: str, run_id=None) -> dict:
        return etl_steps.transform(raw_path, run_id or "scheduled")

    @task
    def validate(stats: dict) -> dict:
        return etl_steps.validate(stats)

    @task
    def load(stats: dict) -> dict:
        return etl_steps.load(stats["path"], mode="append")

    @task
    def verify(stats: dict, load_result: dict) -> dict:
        return etl_steps.verify(stats["rows_out"])

    raw = extract()
    cleaned = transform(raw)
    checked = validate(cleaned)
    loaded = load(checked)
    verify(checked, loaded)


bi_daily_etl()
