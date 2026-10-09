# Data engineering lab

Two real tools, one idea: **raw -> trusted -> business-ready**, repeatably.

## 1. Medallion pipeline (DuckDB + Parquet)
```bash
pip install duckdb pytest
python medallion.py                 # first run loads everything
python medallion.py                 # second run: watermark means only the last day is re-read
python medallion.py --source ../data_samples/operations_messy.csv --reset   # watch quarantine work
python -m pytest tests -q
```
Output lands in `lake/{bronze,silver,gold}/*.parquet` (open them with `SELECT * FROM 'lake/gold/daily.parquet'` in DuckDB or the SQL Lab's sibling notebooks).

Things to try:
1. Add a rule to the `verdict` table (say, `duration_minutes <= 0`) and a test proving it quarantines.
2. Break idempotency on purpose (append to silver instead of de-duplicating) and watch `test_rerun_is_idempotent` fail.
3. Why does the watermark filter use `>=` instead of `>`? (Answer is in the code comments.)

## 2. dbt (dbt-duckdb)
```bash
pip install dbt-duckdb
python medallion.py --reset         # dbt reads lake/silver/ops.parquet
cd dbt_project
dbt build --profiles-dir .          # runs 3 models and 8 tests
dbt docs generate --profiles-dir . && dbt docs serve --profiles-dir .   # lineage graph in the browser
```
Always run dbt from inside `dbt_project/` (the model reads the Parquet by relative path).
Models: `stg_ops` (clean rename) -> `mart_daily_kpis`, `mart_entity_scorecard`. Tests: unique / not_null / accepted_values plus one singular SQL test.

## 3. Orchestration
`../apache_practice/` already has an Airflow DAG and Spark job. A natural exercise: wrap `medallion.run()` in an Airflow `PythonOperator` with a daily schedule. Airflow itself needs Docker or Linux and was **not** executed in the environment this lab was built in, so treat that step as untested.

## 4. Portfolio ideas
- Add a `--source` that reads from an API instead of a CSV and keep the watermark logic.
- Add data-freshness checks (fail if the newest day is older than N days).
- Publish the dbt docs site on GitHub Pages and link it in your CV.
