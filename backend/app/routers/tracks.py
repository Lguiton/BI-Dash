"""Career-track guide: Data Analyst, Data Scientist, Machine Learning, Data Engineering, AI Engineering.

Each track is a role summary, the real tools that role uses, an ordered learning path that links to things that
exist in this project (pages, notebooks, scripts), and portfolio projects. Files shown in the UI are read from disk
through an allow-list built from this table, so only the listed files can ever be served.
"""
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/tracks", tags=["tracks"])
ROOT = Path(__file__).resolve().parents[3]


def page(label, href, why): return {"kind": "page", "label": label, "href": href, "why": why}
def nb(stem, why): return {"kind": "notebook", "label": stem, "href": "/python", "why": why}
def file(path, why): return {"kind": "file", "label": path, "path": path, "why": why}


TRACKS = [
    {
        "id": "analyst", "name": "Data Analyst",
        "role": "Turn data into decisions people can act on.",
        "summary": "Analysts answer business questions with SQL, spreadsheets and BI tools, then explain the answer clearly. "
                   "The craft is asking the right question, getting the numbers right (hello, ratio of sums), and communicating.",
        "tools": [
            {"name": "SQL (DuckDB here; Postgres/BigQuery/Snowflake at work)", "install": "Built in: open SQL Lab."},
            {"name": "pandas + matplotlib", "install": "pip install -r python_practice/requirements-practice.txt"},
            {"name": "Tableau / Superset / Power BI", "install": "Tableau Public is free; Superset steps are on the Apache page."},
            {"name": "Excel", "install": "Use the Excel report button on the dashboard, then pivot it."},
        ],
        "path": [
            page("Read the dashboard like an analyst", "/", "Which KPI moved? Is it a ratio of sums or a sum?"),
            page("SQL Lab exercises", "/lab", "Window functions, CTEs, margin without averaging ratios."),
            page("Data quality checks", "/quality", "Every analysis starts by asking whether the data can be trusted."),
            nb("02_pandas_explore", "The same questions in pandas."),
            nb("10_analyst_case_study", "A realistic case: who is over budget, by how much, and what do you tell the manager?"),
            nb("11_hypothesis_testing", "Is the weekend premium real or noise? t-test, permutation test, bootstrap."),
            page("Build your own KPI", "/kpis", "Define a metric, set a target, track it."),
            page("Learn the vocabulary", "/glossary", "Every metric and concept on this dashboard, with the SQL behind it."),
            page("Take the quiz", "/quiz", "Check what stuck."),
            file("docs/TABLEAU.md", "Rebuild this dashboard in Tableau."),
            file("docs/BI_TOOLS.md", "Rebuild it in Superset or Power BI and compare the totals."),
        ],
        "projects": [
            "One-page memo: 'Where are we losing money?' with 3 charts and one recommendation.",
            "A Tableau Public dashboard following the Z-pattern, linked from your CV.",
            "A SQL portfolio: 10 queries from SQL Lab with the business question above each.",
        ],
        "files": [],
    },
    {
        "id": "scientist", "name": "Data Scientist",
        "role": "Use statistics and modelling to find out what is true and what will happen.",
        "summary": "Scientists design experiments, test hypotheses, segment populations and build predictive models, "
                   "and are honest about uncertainty. Judgement about what NOT to conclude matters as much as the code.",
        "tools": [
            {"name": "Python: pandas, numpy, scipy", "install": "pip install -r python_practice/requirements-practice.txt"},
            {"name": "scikit-learn", "install": "pip install scikit-learn"},
            {"name": "Jupyter", "install": "pip install jupyterlab, then: jupyter lab"},
            {"name": "statsmodels (next step)", "install": "pip install statsmodels"},
        ],
        "path": [
            nb("02_pandas_explore", "Explore before you model."),
            nb("05_forecast", "Backtest a forecast against a naive baseline."),
            nb("11_hypothesis_testing", "Welch t-test, permutation test, bootstrap interval, pseudo-replication."),
            nb("12_clustering_entities", "Unsupervised: segment entities with KMeans, choose k with silhouette, view with PCA."),
            page("ML Lab", "/ml", "Train a model in the browser and see why the baseline matters."),
            nb("13_ml_regression", "Predict revenue; learn leakage the hard way."),
        ],
        "projects": [
            "An A/B-style analysis write-up: effect size, interval, and what you would NOT claim.",
            "Entity segmentation with names for each segment and an action per segment.",
            "A forecast that beats seasonal-naive on a backtest, with the plot.",
        ],
        "files": [],
    },
    {
        "id": "ml", "name": "Machine Learning",
        "role": "Build, evaluate and track predictive models that survive contact with reality.",
        "summary": "The skill is evaluation: time-aware splits, baselines, the right metric for the cost of mistakes, "
                   "leakage checks, and reproducible experiments. A fancy model that loses to 'predict the average' is a bug.",
        "tools": [
            {"name": "scikit-learn (Pipeline, ColumnTransformer)", "install": "pip install scikit-learn"},
            {"name": "MLflow (experiment tracking)", "install": "pip install mlflow  (large). UI: mlflow ui --backend-store-uri sqlite:///_out/mlflow.db"},
            {"name": "XGBoost / LightGBM (next step)", "install": "pip install xgboost lightgbm"},
            {"name": "SHAP (next step)", "install": "pip install shap"},
        ],
        "path": [
            page("ML Lab", "/ml", "Pick a task, model and features; compare against the naive baseline; read the warnings."),
            nb("13_ml_regression", "Pipelines, time split, leakage demo, permutation importance."),
            nb("14_ml_classification", "Imbalance, precision vs recall, tuning the threshold on a validation split."),
            nb("15_mlflow_tracking", "Log runs, compare, pick the best - reproducibly."),
            file("backend/app/services/ml_lab.py", "Read how the ML Lab guards against shuffled splits and leakage."),
        ],
        "projects": [
            "Predict 'not completed' records with a cost-aware threshold; justify it in dollars.",
            "An MLflow comparison of 5 models with a one-paragraph recommendation.",
            "Add a model (e.g. HistGradientBoosting) to ml_lab.py with a test.",
        ],
        "files": ["backend/app/services/ml_lab.py"],
    },
    {
        "id": "engineering", "name": "Data Engineering",
        "role": "Move data reliably from where it is created to where it is used.",
        "summary": "Engineers build pipelines that are incremental, idempotent, tested and observable. "
                   "Bronze/silver/gold layers, quarantining bad rows, and orchestration are the daily vocabulary.",
        "tools": [
            {"name": "DuckDB + Parquet", "install": "pip install duckdb"},
            {"name": "dbt (dbt-duckdb)", "install": "pip install dbt-duckdb"},
            {"name": "Apache Airflow", "install": "Linux/WSL2/Docker; see the Apache page. Not executed when this lab was built."},
            {"name": "Apache Spark", "install": "Java 17+ and pip install pyspark"},
            {"name": "pytest", "install": "pip install pytest"},
        ],
        "path": [
            nb("04_etl_vs_elt", "ETL vs ELT in practice."),
            nb("03_clean_messy_data", "Clean, quarantine, report."),
            file("data_engineering/medallion.py", "Run it twice: the watermark and idempotency are the point."),
            file("data_engineering/tests/test_medallion.py", "Tests that prove idempotency, incrementality and quarantine."),
            file("data_engineering/dbt_project/models/mart_daily_kpis.sql", "dbt model; then run dbt build."),
            page("Pipeline monitor", "/pipeline", "Run the pipeline from the browser; watch layers, health checks and quarantine."),
            file("postgres_practice/exercises.sql", "A real PostgreSQL: indexes, EXPLAIN, constraints, roles (needs Docker)."),
            page("Apache (Spark, Airflow, Superset)", "/apache", "Orchestration and scale-out."),
        ],
        "projects": [
            "Make medallion.py read from an API with the same watermark logic.",
            "Add a freshness test that fails when the newest day is stale.",
            "Wrap the pipeline in an Airflow DAG and publish the dbt docs site.",
        ],
        "files": ["data_engineering/medallion.py", "data_engineering/tests/test_medallion.py",
                  "data_engineering/dbt_project/models/stg_ops.sql", "data_engineering/dbt_project/models/mart_daily_kpis.sql",
                  "data_engineering/dbt_project/models/schema.yml", "data_engineering/README.md"],
    },
    {
        "id": "ai", "name": "AI Engineering",
        "role": "Build reliable products on top of language models.",
        "summary": "AI engineers wrap models in structure: validated outputs, retrieval, tools, evals and guardrails. "
                   "Everything runs offline with a stub so you can practise for free; add an API key for the real model.",
        "tools": [
            {"name": "Gemini, OpenAI and Claude APIs", "install": "pip install -r backend/requirements.txt; put keys in backend/.env (never commit them). Gemini has a free tier."},
            {"name": "pydantic (structured output)", "install": "pip install pydantic"},
            {"name": "scikit-learn TF-IDF (retrieval)", "install": "pip install scikit-learn"},
            {"name": "MCP SDK", "install": "pip install mcp"},
        ],
        "path": [
            page("AI Lab", "/ai", "Ask a question; watch the agent choose tools and write SQL."),
            file("ai_engineering/01_structured_output.py", "Validate model output; retry with the error."),
            file("ai_engineering/02_rag.py", "Retrieve, cite, and say 'I don't know'."),
            file("ai_engineering/03_evals.py", "A golden-set eval that catches a real bug."),
            file("ai_engineering/04_mcp_server.py", "Expose read-only tools to any MCP client."),
            file("ai_engineering/05_prompt_injection.py", "Deterministic defences for poisoned data."),
            file("backend/app/services/ai_agent.py", "The production-style agent loop behind the AI Lab."),
            file("backend/app/services/llm_router.py", "Routing, daily caps and fallback across Gemini, OpenAI and Claude."),
            file("backend/app/services/providers.py", "Three vendors' tool-calling formats behind one interface."),
        ],
        "projects": [
            "Grow the eval to 30 questions and track the score across prompt versions.",
            "Swap TF-IDF for embeddings in 02_rag.py and compare retrieval hit-rate.",
            "Connect 04_mcp_server.py to Claude Desktop and record a demo.",
        ],
        "files": ["ai_engineering/01_structured_output.py", "ai_engineering/02_rag.py", "ai_engineering/03_evals.py",
                  "ai_engineering/04_mcp_server.py", "ai_engineering/05_prompt_injection.py",
                  "ai_engineering/README.md", "backend/app/services/ai_agent.py",
                  "backend/app/services/llm_router.py", "backend/app/services/providers.py"],
    },
]

def _slug(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


# every step gets a stable id like "analyst:sql-lab-exercises" so progress survives edits to the wording of other steps
STEP_IDS: set[str] = set()
for _t in TRACKS:
    for _s in _t["path"]:
        _s["id"] = f"{_t['id']}:{_slug(_s['label'])}"
        STEP_IDS.add(_s["id"])

_LANG = {".py": "python", ".sql": "sql", ".md": "markdown", ".yml": "yaml"}


def _allowed() -> set[str]:
    out = set()
    for t in TRACKS:
        out.update(t["files"])
        out.update(s["path"] for s in t["path"] if s["kind"] == "file")
    return out


@router.get("")
def list_tracks():
    return {"tracks": [{k: v for k, v in t.items() if k != "files"} for t in TRACKS]}


@router.get("/{track_id}/dashboard")
def dashboard(track_id: str):
    from app.services import track_dash
    build = track_dash.BUILDERS.get(track_id)
    if build is None:
        raise HTTPException(404, "Unknown track.")
    return {"track": track_id, **build()}


@router.get("/file")
def read_file(path: str = Query(min_length=1, max_length=200)):
    if path not in _allowed():
        raise HTTPException(404, "That file isn't part of a track.")
    p = (ROOT / path).resolve()
    if ROOT not in p.parents or not p.is_file():
        raise HTTPException(404, "File not found (is the project folder complete?).")
    return {"path": path, "language": _LANG.get(p.suffix, "text"), "content": p.read_text(encoding="utf-8")}
