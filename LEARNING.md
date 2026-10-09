# Learning guide: BI practice lab

This project is a small but real BI stack (database, ETL, API, dashboard) that you can poke at while you study.
Everything below maps to the topics in your class notes.

## Where each topic is practiced

| Topic from your notes | Practice it here |
|---|---|
| **Metrics vs KPIs** | The **KPIs** page: pick a metric, add a target, direction, window and warning band, and watch the status change. On the dashboard, revenue is a metric; "cost vs budget" becomes a KPI once it has a target. |
| **Descriptive: what happened?** | KPI cards, trend chart, entity table. the Beginner SQL Lab exercises. `python_practice/02_pandas_explore.py` |
| **Diagnostic: why?** | Insights panel (anomalies, over-budget, margin gaps), click a bar to drill down, the Records table. SQL Lab `cost-spikes`. `05_predictive_stats.py` §1 |
| **Predictive: what's likely?** | The dashed forecast with its 95% range and backtest. `GET /api/analytics/forecast`. `05_predictive_stats.py` §3 (model competition) |
| **Prescriptive: what to do?** | Insights → Prescriptive, with the arithmetic in each recommendation. `GET /api/analytics/recommendations`. Open `backend/app/services/recommendations.py` and read the rules. |
| **Quantitative vs qualitative** | The app is quantitative. Qualitative practice: pick a flagged anomaly day, then write a 5-line post-mortem of what operational causes could explain it and what evidence you would collect. |
| **ETL vs ELT** | `python_practice/04_etl_vs_elt.py` runs both on the same messy file and proves identical output. |
| **Data prep: dedupe, type casting, imputation** | `03_clean_messy_data.py` (exercise), the import validator (try uploading `data_samples/operations_messy.csv` and read the line-numbered errors), SQL Lab `dedupe`. |
| **Slowly Changing Dimensions** | The **SCD lab** page: change an entity's category and compare Type 1 vs Type 2 revenue by category. Then query `scd_type1` / `scd_type2` in SQL Lab and write the date-range join yourself. |
| **Star schema, grain, fact vs dimension, conformed dimensions** | The **Star schema** page (diagram, grain, flat-table trade-off), then SQL Lab → Schema. `fact_operations` (grain: one row per entity per day), `dim_entities`, `dim_date` (shared date dimension). `v_operations_flat` is the denormalized table BI tools like. |
| **Additive vs non-additive measures** | SQL Lab `non-additive`. `02_pandas_explore.py` §2. The margin bug fixed in this project's first review is exactly this trap. |
| **Time intelligence (PoP, MTD, YTD, rolling)** | KPI deltas (period over period). SQL Lab `moving-avg`, `mom-growth`, `ytd`, `running-profit`. `02_pandas_explore.py` §5. |
| **Visualization & UX** | Dashboard layout is Z-pattern (KPIs, then trend, then detail). Cross-filtering by clicking a bar/row. Every KPI carries a prior-period delta (contextual benchmarking). `06_visualization.py` rebuilds it in matplotlib. |
| **File formats (CSV, TSV, XLSX, XML, JSON)** | SQL Lab → Practice files (download all of them). `01_file_formats.py` writes and re-reads each and compares size and type fidelity. Plus Parquet. |
| **Languages: SQL** | SQL Lab: sandbox + 16 graded exercises, easy to hard. |
| **Languages: Python** | The **Python** page: 8 Jupyter notebooks with self-checking exercises (`python_practice/notebooks/`), plus the six scripts. The backend itself is Python/FastAPI. |
| **Languages: Shell** | `bash scripts/etl_demo.sh`: a four-step ETL pipeline with curl. |
| **Languages: R** | Download `operations` as CSV, then in R: `readr::read_csv()`, then redo the trend and heatmap with `ggplot2`. |
| **Tableau / Power BI** | `docs/TABLEAU.md` (calculated fields, LODs, table calcs, dashboard checklist). |
| **Apache** | The **Apache** page: Spark, Airflow and Superset examples. See "Apache tools" below. |
| **Data quality / data prep** | The **Data quality** page: run the checks, then break the data on purpose (import the messy file) and watch which checks fail. |
| **Reporting and presenting** | Download the **Excel / PDF report** from the dashboard for a filtered view and critique it: what would a manager need that is missing? |
| **Exam prep** | The **Quiz** page, by topic. Retry the ones you missed. |

## Career tracks (beyond the class topics)
The **Company** page (`/company`) strings all of them into one job: Discover, Design, Build, Operate. Start there if you want to practise doing every discipline for one company.

Open the **Tracks** page for a dropdown of Data Analyst, Data Scientist, Machine Learning, Data Engineering, AI Engineering, Project & Product, Systems Analyst and Full Stack Developer. Each lists the real tools, an ordered path through this project, and portfolio ideas.

| Track | Where to practice |
|---|---|
| Data Analyst | Dashboard, SQL Lab, `/quality`, notebooks 02, 10 (case study), 11 (is the effect real?) |
| Project & Product | `/tracks/pm`: RICE/WSJF, sprints, critical path, earned value, risks, OKRs; docs/PROJECT_PRODUCT_MANAGEMENT.md |
| Systems Analyst | `/tracks/sysanalyst`: requirements, data dictionary, queueing, availability, cost-benefit, TELOS; docs/SYSTEMS_ANALYSIS.md |
| Full Stack Developer | `/tracks/fullstack`: API tester, scaffolds, codebase; docs/FULL_STACK_DEVELOPMENT.md |
| Data Scientist | Notebooks 11 (hypothesis tests), 12 (clustering), 13 (modelling), ML Lab |
| Machine Learning | ML Lab (`/ml`), notebooks 13-15 (regression, classification, MLflow) |
| Data Engineering | `data_engineering/` (medallion pipeline, dbt, tests), Apache page |
| AI Engineering | AI Lab (`/ai`), `ai_engineering/` exercises (they run offline) |

Honest limits: the AI Lab and live model steps need an API key and cost money; Airflow and Superset need Linux/Docker and were not executed when this lab was built.

## Suggested order (about 4 weeks, 3-4 hours a week)
1. **Week 1: look and describe.** Use the dashboard. Generate the big dataset and import it (below). Do the Beginner SQL exercises and the first Intermediate ones. Run Python scripts 01-02.
2. **Week 2: model and prepare.** Study the schema. Finish the Intermediate SQL exercises (joins, HAVING, non-additive, dedupe). Python exercise 03 (cleaning), then 04 (ETL vs ELT). Run `etl_demo.sh`.
3. **Week 3: analyze and predict.** The Advanced SQL exercises (window functions, CTEs, LAG). Script 05. Read `forecast.py`, then try to beat it.
4. **Week 4: visualize and present.** Script 06, then the Tableau guide. Build the same dashboard in Tableau and compare it with this one.

## Load the big practice dataset
```
python scripts/generate_sample_data.py          # 3,650 rows: 10 entities x 365 days
```
Then in the dashboard: **Import data (CSV)** → mode **Replace** → `data_samples/operations_clean.csv`.
The data has trend, weekday patterns, noise, a few injected anomalies, and some entities built to run over budget,
so every insight has something real to find. Same `--seed` gives the same data. Use `--messy` for the cleaning exercise.

## Apache tools
All three live in `apache_practice/` and in the dashboard's **Apache** page (dropdown).
- **Spark**: `python apache_practice/spark/01_spark_basics.py` (needs Java 17+ and `pip install pyspark`). Redoes SQL Lab questions with the DataFrame API and Spark SQL, shows a query plan, writes partitioned Parquet. Notebook version: `notebooks/07_spark.ipynb`.
- **Airflow**: `apache_practice/airflow/` has a DAG (extract, transform, quality gate, load, verify) whose logic you can also run without Airflow: `python apache_practice/airflow/etl_steps.py`. Airflow itself needs Linux, WSL2 or Docker.
- **Superset**: a step-by-step guide in `apache_practice/superset/README.md` (Docker, upload the CSV export, add metrics, build six charts). DuckDB allows one process at a time on its file, so Superset works from the exports, never the live `.duckdb` file.

Typical flow: **Airflow** schedules the pipeline, **Spark** transforms, **Superset** visualizes.

## Ground rules that keep the practice honest
- The SQL Lab is read-only and has a 5-second timeout; the import validates before it loads. You cannot break your data from the lab.
- Insights, forecasts and recommendations are computed and show their arithmetic. If a number looks off, check it with SQL: that habit is the point.
- `baseline_target` is treated as a *cost budget per record* (inferred from the data). If your own data uses it differently, change `_by_entity` in `backend/app/routers/analytics.py`.

## Study loop
1. Open the main dashboard; the study widget shows where you are in each career and a Continue button.
2. Work the step (a page, notebook, script or doc), then tick it on that career's dashboard (`/tracks/<career>`).
3. Look up unfamiliar terms in `/glossary`; run the pipeline in `/pipeline`; practise Postgres with `postgres_practice/exercises.sql`.
4. Ask the AI Lab for a chart ("chart weekly revenue as a line") and check its SQL yourself.

## Chart gallery: which chart for which question
- Parts of a whole (pie, donut, treemap): only when the parts add up to something meaningful and there are few of them.
- Ranking (ranked bar, Pareto): the most accurate to read; Pareto shows how concentrated the total is.
- Distribution (histogram, box plot): shape, spread and outliers. Try profit by category, then ask why Fleet has so many high outliers.
- Relationships (bubble): cost vs revenue vs size. Try the same chart with different filters.
