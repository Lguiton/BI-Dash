# Apache practice

| Tool | What it is | Role in a BI stack | Folder |
|---|---|---|---|
| **Spark** | Distributed data processing engine | Transform / analyze data too big for one machine (ELT) | `spark/` |
| **Airflow** | Workflow orchestrator | Schedule and monitor pipelines (the "when and in what order") | `airflow/` |
| **Superset** | BI / visualization web app | Dashboards and exploration for business users | `superset/` |

Typical flow: **Airflow** schedules the pipeline, **Spark** transforms the data, **Superset** visualizes it.

Open the **Apache** page in the dashboard for a dropdown that shows each tool's code and steps.
Backend needs to be running first for the Spark/Airflow scripts to read live data (Spark falls back to the sample CSV).

- Spark: `pip install pyspark` (needs Java 17+), then `python apache_practice/spark/01_spark_basics.py`
- Airflow steps without Airflow: `python apache_practice/airflow/etl_steps.py`. For the real DAG see `airflow/dags/bi_etl_dag.py`
- Superset: follow `superset/README.md`
