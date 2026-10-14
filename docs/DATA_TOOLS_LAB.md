# Data tools lab

Data engineering > Data tools lab. Small, safe versions of tools data teams use. They teach how the tools decide; for production use the real ones.

- **Model builder (dbt-style):** seeds as pasted CSV, models as SELECTs that read each other with `ref()`, tests (not_null, unique, accepted_values, relationships, row_count_min). Builds in a private in-memory DuckDB with file and network access off; it never touches your data. Shows build order, compiled SQL, previews and "what depends on this".
- **Formula engine:** one cell per line; references, ranges, SUM AVERAGE MIN MAX COUNT IF AND OR NOT ROUND IFERROR SUMIF COUNTIF VLOOKUP and text functions; calculation order and circular-reference detection.
- **Task scheduler:** a time simulation of a task graph with workers, retries and failures; shows the critical path and which tasks are skipped.
- **Cron:** next run times; warns about the "either day field" rule.
- **Stream simulator:** partitions by key, consumer groups, tumbling/sliding/session windows, watermark and late events.

Not built: real dbt (macros, incremental models, snapshots), Excel's grid, dates and pivots, a Kafka or Flink cluster, running real jobs (the Pipelines page does that). Files: `services/data_dbt.py`, `data_calc.py`, `data_flow.py`, `routers/datalab.py`, `panels/DataLab.tsx`, `tests/test_data_lab.py`.
