# Business Intelligence Dashboard

![CI](https://github.com/<you>/<repo>/actions/workflows/ci.yml/badge.svg)

![Dashboard](docs/screenshots/dashboard.png)

FastAPI + DuckDB analytics engine (`backend/`) and a Next.js dashboard (`frontend/`).

## Run it

**Backend** (port 8020)
```
cd backend
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
uvicorn app.main:app --port 8020 --reload
```

**Frontend** (port 3012)
```
cd frontend
npm install
npm run dev
```
Open http://localhost:3012. Set `NEXT_PUBLIC_API_URL` (see `frontend/.env.example`) if the API is elsewhere.

## Learning lab
See **LEARNING.md** for how this project maps to BI topics (SQL, Python, Tableau, ETL/ELT, forecasting...).
* **Dashboard**: KPIs, filters, trend + forecast, insights, drill-down, and **Excel / PDF reports** of the current view.
* **KPIs** (`/kpis`): turn a metric into a KPI with a target, direction, window and warning band.
* **Data quality** (`/quality`): nine checks (nulls, negatives, orphans, duplicates, date gaps...) with sample rows.
* **Study widget** (main dashboard): progress bars for the five careers and a **Continue** button to your next step. Progress is stored in the DuckDB file.
* **Career dashboards** (`/tracks/analyst`, `/scientist`, `/ml`, `/engineering`, `/ai`): a practice dashboard per career (analyst KPIs and quality score; weekend t-test, KMeans segments and correlations; ML experiment log; pipeline health; AI usage) plus a learning-path checklist and portfolio ideas.
* **Tracks** (`/tracks`): Data Analyst, Data Scientist, Machine Learning, Data Engineering and AI Engineering, each with real tools, an ordered path through this project, and portfolio projects.
* **Labs** menu:
  * **SQL Lab** (`/lab`): read-only SQL console, 16 graded exercises, and saved queries (kept in your browser).
  * **Python** (`/python`): Jupyter launch card and 14 notebooks in `python_practice/notebooks/` (basics 00-07; analyst, statistics, clustering, ML and MLflow 10-15) with self-checking exercises.
  * **ML Lab** (`/ml`): train regression/classification models (scikit-learn) with a time-based split, baselines, cross-validation, permutation importance and plain-English warnings.
  * **AI Lab** (`/ai`): an agent that answers questions by writing read-only SQL. Put any of `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` in `backend/.env` (see `.env.example`). Simple questions go to Gemini first (free tier), then OpenAI; complex or code questions go to Claude first. Daily caps and automatic fallback spread the load; you can also force one model.
  * **Glossary** (`/glossary`): 18 metrics and concepts with formula, runnable SQL and common pitfalls.
  * **Pipeline monitor** (`/pipeline`): run the medallion pipeline (clean or messy data) and watch freshness, quarantine and health checks.
  * **Apache** (`/apache`): Spark, Airflow and Superset examples in a dropdown (`apache_practice/`).
  * **Star schema** (`/schema`): fact/dimension diagram, grain, additive vs non-additive measures.
  * **SCD lab** (`/scd`): change a category and compare Type 1 (overwrite) with Type 2 (history kept).
  * **Quiz** (`/quiz`): 25 questions from your class topics, with explanations and best scores.
* `python_practice/`: six runnable scripts (file formats, pandas, data cleaning, ETL vs ELT, forecasting, charts).
* `data_engineering/`: a medallion pipeline (DuckDB + Parquet, incremental and idempotent, with tests) and a dbt-duckdb project. See its README.
* `ai_engineering/`: five exercises (structured output, RAG, evals, MCP server, prompt injection) that run offline with a stub or live with an API key.
* `postgres_practice/`: the same star schema in Postgres 16 via Docker (constraints, indexes, read-only role). See its README.
* `.github/workflows/ci.yml`: backend, labs, Postgres and frontend jobs.
* `scripts/send_report.py`: emails the report; schedule it with cron or Task Scheduler (set `BI_SMTP_*` and `BI_REPORT_TO` in `backend/.env`).
* `scripts/generate_sample_data.py`: a realistic year of data (clean or messy) for practice.
* `docs/TABLEAU.md`: a Tableau practice guide. `docs/BI_TOOLS.md`: Superset, Power BI and Metabase notes (untested).

## Load your own data
Use **Import data (CSV)** on the dashboard (or `POST /api/ingest/csv`). Download the template from the same panel.
Required columns: `record_date, entity_id, revenue, operational_cost, units_processed`.
Optional: `entity_name, category, baseline_target, duration_minutes, status, fact_id`.
Files are fully validated first; a bad row rejects the whole file with line-numbered errors, so you never get a half-import.
* **Add / update**: upserts by `fact_id` (auto-generated from the row content when absent, so re-uploading the same file doesn't duplicate).
* **Replace**: deletes all existing records and entities first (this also removes the demo data).

## API
| Endpoint | Purpose |
|---|---|
| `GET /api/analytics/meta` | filter options, date range |
| `GET /api/analytics/summary` | KPIs + previous-period comparison |
| `GET /api/analytics/timeseries` | daily revenue / cost / profit / units |
| `GET /api/analytics/by-entity` | per-entity totals, margin, cost vs budget |
| `GET /api/analytics/records` | paginated, sortable row-level drill-down |
| `GET /api/analytics/records/export` | CSV download |
| `GET /api/analytics/insights` | insights across the four analytics types |
| `GET /api/analytics/forecast` | revenue forecast with 95% range and backtest |
| `GET /api/analytics/recommendations` | prescriptive actions with estimated impact |
| `GET /api/analytics/scatter`, `/heatmap` | data for the extra chart types |
| `POST /api/sql/run`, `GET /api/sql/schema` | read-only SQL Lab |
| `GET /api/sql/exercises`, `POST .../{id}/check` | graded SQL exercises |
| `GET /api/export/{operations\|facts\|entities\|dates}?format=csv\|tsv\|json\|xml\|xlsx\|parquet` | downloads |
| `GET /api/report?format=xlsx\|pdf` | report of the filtered view |
| `GET/POST /api/kpis`, `DELETE /api/kpis/{id}`, `GET /api/kpis/metrics` | KPI builder |
| `GET /api/quality` | data-quality checks |
| `GET /api/scd/state`, `/compare`, `POST /api/scd/change`, `/reset` | slowly changing dimension sandbox |
| `GET /api/python/notebooks[/{file}]`, `GET /api/apache/tools` | notebook and Apache examples |
| `GET /api/ml/options`, `POST /api/ml/train` | ML Lab |
| `GET /api/ai/status`, `POST /api/ai/ask` | AI Lab (needs API key) |
| `GET /api/tracks`, `GET /api/tracks/file?path=` | career tracks |
| `GET /api/tracks/{id}/dashboard` | per-career practice dashboard |
| `GET/PUT /api/progress` | study progress |
| `GET /api/glossary` | metrics glossary |
| `GET /api/pipeline`, `POST /api/pipeline/run` | pipeline monitor |
| `GET /api/report/email/status`, `POST /api/report/email` | emailed report |
| `POST /api/ingest/csv?mode=append\|replace` | CSV import |
| `GET /api/ingest/template` | CSV template |

All analytics endpoints accept `date_from, date_to, entity_id, category, status`. Interactive docs at `/docs`.

## Tests
```
cd backend
pip install -r requirements-dev.txt
pytest
```

## Notes
* Margin is **total profit / total revenue** (weighted), not an average of per-row margins.
* Insights are computed (period change, linear trend, median/MAD outliers, entity highlights), never LLM-estimated.
* `baseline_target` is treated as a **cost budget per record** (inferred: in the demo data each entity's average cost per record ≈ its baseline). "Cost vs budget" is average cost ÷ budget − 1, so positive = over budget. Change `_by_entity` in `backend/app/routers/analytics.py` if it means something else.
* Config via env vars: `BI_DB_PATH`, `BI_CORS_ORIGINS`, `BI_SEED_DEMO` (see `backend/.env.example`).
