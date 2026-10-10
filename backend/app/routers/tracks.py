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
            file("docs/DBA_AND_GOVERNANCE.md", "The DBA and data-governance vocabulary: RPO/RTO, WAL, integrity checks, catalog, PII, retention, lineage."),
            page("Settings & backups", "/settings", "Take a backup, restore it, set AI access and blocked columns. Then verify the backup on this track's Database admin tab."),
            page("Activity log", "/activity", "The audit trail: what changed data or left the computer."),
            file("backend/app/services/dba.py", "Read how health checks, benchmarks and backup verification work."),
            file("backend/app/services/governance.py", "Read the PII scanner, catalog, lineage and controls checklist."),
        ],
        "projects": [
            "Make medallion.py read from an API with the same watermark logic.",
            "Add a freshness test that fails when the newest day is stale.",
            "Wrap the pipeline in an Airflow DAG and publish the dbt docs site.",
            "Write a one-page backup and recovery plan with your RPO and RTO, then prove it by restoring a backup and running the verify check.",
            "Classify every table, set owners and retention, and get the governance checklist to 8 of 8.",
        ],
        "files": ["data_engineering/medallion.py", "data_engineering/tests/test_medallion.py",
                  "data_engineering/dbt_project/models/stg_ops.sql", "data_engineering/dbt_project/models/mart_daily_kpis.sql",
                  "data_engineering/dbt_project/models/schema.yml", "data_engineering/README.md",
                  "docs/DBA_AND_GOVERNANCE.md", "backend/app/services/dba.py", "backend/app/services/governance.py"],
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
    {
        "id": "pm", "name": "Project & Product",
        "role": "Decide what to build, in what order, and keep the work on time and on budget.",
        "summary": "Project managers plan and control scope, schedule, cost and risk; product managers decide what is worth building and prove it worked. "
                   "Both live on numbers: prioritisation scores, velocity, cycle time, the critical path, earned value, expected risk cost and retention.",
        "tools": [
            {"name": "A board and backlog (Jira, Linear, Azure DevOps, Trello)", "install": "Use the board on this track's dashboard to practise, then map the same ideas to the tool your team uses."},
            {"name": "Roadmapping and docs (Notion, Confluence, Productboard)", "install": "Write a one-page PRD in any doc tool."},
            {"name": "Product analytics (Amplitude, Mixpanel, PostHog)", "install": "The dashboard computes active accounts, stickiness, funnel and retention cohorts from your own data."},
            {"name": "MS Project / spreadsheets for schedules", "install": "The dashboard computes the critical path and earned value; rebuild one in Excel to check it."},
        ],
        "path": [
            file("docs/PROJECT_PRODUCT_MANAGEMENT.md", "The vocabulary: RICE, WSJF, MoSCoW, velocity, burndown, cycle time, Little's law, CPM, EVM, EMV, OKRs, retention."),
            page("Define a North Star and guardrail KPIs", "/kpis", "A product needs one number that says users get value, plus numbers that must not get worse."),
            page("Bring in activity data", "/data", "Import real activity (or use Practice) so the product-analytics section has something to measure."),
            file("backend/tests/test_pm.py", "Hand-worked examples of every formula: check the arithmetic yourself."),
            file("backend/app/services/pm.py", "How each metric is computed, in readable Python."),
            page("Read the glossary", "/glossary", "Margin, cost vs budget and the other measures a manager gets asked about."),
            page("Activity log", "/activity", "Change history is how you answer 'what happened and when?'"),
        ],
        "projects": [
            "Run a real two-week project on the board: 10 items with RICE scores, one sprint, one burndown, and a retro note on what you'd change.",
            "A one-page PRD for a feature: problem, who has it, how you will measure success, what you will NOT build.",
            "A risk register with expected costs and a contingency reserve you can defend in two sentences.",
            "Explain your project's CPI and SPI to a non-technical sponsor without using the acronyms.",
        ],
        "files": ["docs/PROJECT_PRODUCT_MANAGEMENT.md", "backend/tests/test_pm.py", "backend/app/services/pm.py"],
    },
    {
        "id": "sysanalyst", "name": "Systems Analyst",
        "role": "Work out what a system must do, model how it works today, and show that what was built meets the need.",
        "summary": "Systems analysts bridge the business and the builders: gathering requirements, modelling processes and data, sizing capacity, "
                   "checking feasibility and tracing every requirement to a test. Precision and traceability are the craft.",
        "tools": [
            {"name": "SQL for investigating real data", "install": "Built in: open SQL Lab."},
            {"name": "ER and process diagrams (Mermaid, draw.io, Lucidchart)", "install": "The dashboard outputs Mermaid text for the data model: paste it into mermaid.live."},
            {"name": "Requirements and test tools (Jira, Azure DevOps, TestRail)", "install": "The dashboard's traceability matrix practises the same links."},
            {"name": "Spreadsheets for sizing and cost-benefit", "install": "The calculators here show the formulas; rebuild one in Excel."},
        ],
        "path": [
            file("docs/SYSTEMS_ANALYSIS.md", "The vocabulary: requirements, traceability, data dictionary, queueing, availability, NPV, TELOS."),
            page("Read the data model", "/schema", "Facts, dimensions, keys and grain: the analyst's picture of the data."),
            page("Check the data is fit to model", "/quality", "Findings here become requirements for the source system."),
            page("Verify requirements with SQL", "/lab", "Turn 'the report must show X' into a query that proves it."),
            page("Model change over time", "/scd", "Slowly changing dimensions: how history is kept when something is renamed."),
            page("Trace the data flow", "/pipeline", "Landing to bronze to silver to gold, and where bad rows go."),
            file("backend/tests/test_sysanalyst.py", "Worked queueing, availability, NPV and capacity examples to check by hand."),
            file("backend/app/services/sysanalysis.py", "How the dictionary, process analysis and calculators work."),
        ],
        "projects": [
            "Write 10 testable requirements for a system you know, with acceptance criteria, and link each to a test.",
            "Draw the as-is process from the data: where does time go, and what is the bottleneck?",
            "A feasibility memo with TELOS scores and the one risk you would raise first.",
            "Size a service desk: arrival rate, service time, and the smallest team that keeps the average wait under five minutes.",
        ],
        "files": ["docs/SYSTEMS_ANALYSIS.md", "backend/tests/test_sysanalyst.py", "backend/app/services/sysanalysis.py"],
    },
    {
        "id": "fullstack", "name": "Full Stack Developer",
        "role": "Build the whole product: database access, API, user interface, tests and release.",
        "summary": "A full stack developer owns a feature from the table to the screen. The craft is the contract between layers: "
                   "a typed API, validated input, bound SQL parameters, a UI that handles loading and errors, and tests that prove it.",
        "tools": [
            {"name": "Python and FastAPI", "install": "Already installed with backend/requirements.txt. The API docs live at http://localhost:8020/docs."},
            {"name": "TypeScript, React and Next.js", "install": "Already installed with npm install in frontend/."},
            {"name": "pytest and a TestClient", "install": "pip install pytest; the project's tests show the fixture pattern."},
            {"name": "Git and GitHub", "install": "git is on most machines; this repo is the practice project."},
            {"name": "A REST client (Postman, curl)", "install": "The API tester on this page does the same job inside the app."},
        ],
        "path": [
            file("docs/FULL_STACK_DEVELOPMENT.md", "The vocabulary and a checklist for one vertical slice."),
            page("Read the data model you build on", "/schema", "Every feature starts with the tables."),
            page("Prototype queries before coding them", "/lab", "Get the SQL right in SQL Lab, then move it into the API."),
            file("backend/app/main.py", "How routers, CORS and start-up compose into one API."),
            file("backend/app/routers/pm.py", "A complete CRUD router: thin handlers, validation errors become HTTP codes."),
            file("backend/app/services/pm.py", "The logic behind that router, testable without HTTP."),
            file("backend/tests/conftest.py", "How each test gets its own database and a TestClient."),
            file("frontend/src/lib/api.ts", "One typed fetch layer with consistent error handling."),
            file("frontend/src/components/panels/PmPanel.tsx", "A full React feature: state, forms, charts, loading and error states."),
            page("Check configuration and backups", "/settings", "Environment, workspaces and recovery are part of the job."),
            page("Read the audit trail", "/activity", "Observability: what happened, when and did it work."),
        ],
        "projects": [
            "Scaffold a table, register the router, then add real validation and a test that fails when it should.",
            "Add a field end to end: column, API model, TypeScript type, form input and test.",
            "Find the slowest endpoint with the API tester, then fix it and show the before and after.",
            "Write a release checklist for this app and run it.",
        ],
        "files": ["docs/FULL_STACK_DEVELOPMENT.md", "backend/app/main.py", "backend/app/routers/pm.py", "backend/app/services/pm.py",
                  "backend/tests/conftest.py", "frontend/src/lib/api.ts", "frontend/src/components/panels/PmPanel.tsx"],
    },
    {
        "id": "security", "name": "Cybersecurity",
        "role": "Protect your own systems: find weaknesses, read the logs, respond to incidents. Defence and learning, on things you own.",
        "summary": "Security work is mostly habits: keep secrets out of git, check what you expose, read logs for patterns, "
                   "store passwords as hashes, and have a written plan for when something goes wrong. The tools here only look at "
                   "your own app and public sites; offensive tools (exploits, scanners against other people) are explained, not built.",
        "tools": [
            {"name": "Self-audit (built in)", "install": "Open the Cybersecurity dashboard, tab Self-audit. Checks .env, permissions, secrets in files, CORS and backups."},
            {"name": "Log analysis (built in)", "install": "Paste or upload a web or auth log in the Logs tab. Detections are leads to check, not verdicts."},
            {"name": "Web header and TLS checks (built in)", "install": "Public hosts only. Private addresses are refused on purpose."},
            {"name": "Hashing, password and 2FA labs (built in)", "install": "Crypto tab: SHA-256 and verify, password strength, a TOTP authenticator lab."},
            {"name": "pip-audit and Dependabot", "install": "pip install pip-audit, then pip-audit -r backend/requirements.txt. Turn on Dependabot alerts in GitHub."},
            {"name": "Wireshark, Nmap, Burp, Metasploit, Kali", "install": "Not embedded. Learn them in a lab you own (a VM, or a deliberately vulnerable app); never point them at systems you don't have written permission to test."},
        ],
        "path": [
            file("docs/CYBERSECURITY.md", "Vocabulary, the CIA triad, and the limits of these tools."),
            page("Investigate a log file", "/logs", "Load the practice log and read each detection with its evidence."),
            page("Read the activity log", "/activity", "What the app recorded: the raw material for investigations."),
            page("Check configuration and backups", "/settings", "A tested backup is your best ransomware defence."),
            file("backend/app/services/seclogs.py", "How log lines become detections: brute force, probing, injection patterns."),
            file("backend/app/services/security.py", "Hashing, password strength and TOTP in plain code."),
            file("backend/app/services/selfaudit.py", "The checks behind the self-audit, and what each one means."),
        ],
        "projects": [
            "Run the self-audit, fix every red item, and run it again.",
            "Paste the sample auth log, find the brute-force attempt, and write the incident report.",
            "Check the security headers of your own public site and list the three that matter most.",
            "Write an incident playbook for 'laptop lost' and run it as a tabletop exercise.",
        ],
        "files": ["docs/CYBERSECURITY.md", "backend/app/services/seclogs.py", "backend/app/services/security.py", "backend/app/services/selfaudit.py", "backend/tests/test_update13.py"],
    },
    {
        "id": "network", "name": "Network Engineer",
        "role": "Design, build and fix the paths data takes between machines.",
        "summary": "Network work is addressing, segmentation and disciplined fault-finding. Learn to subnet in your head, read a config for mistakes, "
                   "recognise what traffic looks like, and walk the layers from the cable up. The tools here run on text you paste and on public hosts; "
                   "they don't touch your network, and scanners are explained, not built.",
        "tools": [
            {"name": "Subnet and VLSM planner (built in)", "install": "Open the Network dashboard, tab Subnet and VLSM. Subnet, split, plan, check overlaps, summarise routes."},
            {"name": "Config review (built in)", "install": "Paste a router or switch config in the Config review tab. Pattern checks, not a CIS audit."},
            {"name": "Packet capture reader (built in)", "install": "Paste tcpdump -nn text in the Packet capture tab. It reads text; it never captures."},
            {"name": "DNS and TCP reachability (built in)", "install": "Public hosts only, one port at a time, 12 checks a minute."},
            {"name": "Wireshark and tcpdump", "install": "Wireshark is free (wireshark.org). Capture only on networks you own."},
            {"name": "Cisco Packet Tracer, GNS3, EVE-NG", "install": "Not embedded. Free virtual labs for routing, VLANs and trunking."},
            {"name": "iperf3, Nmap, Zabbix, Nagios, Ansible, pfSense", "install": "Not embedded. Run them in a lab you own; never scan networks you don't have written permission to test."},
        ],
        "path": [
            file("docs/NETWORK_ENGINEERING.md", "The five ideas, what is built in, and what isn't."),
            page("Watch your own app's traffic", "/ops", "Request counts and timings for this app: a first taste of monitoring."),
            file("backend/app/services/netlab.py", "Subnetting, config checks and capture parsing in plain Python."),
            page("Read the activity log", "/activity", "A timeline of what changed: the habit behind change management."),
            file("backend/app/routers/net.py", "The endpoints behind the Network tools, with the rate limit on outbound checks."),
        ],
        "projects": [
            "Plan a small office in one /22: 60 staff, 20 guest Wi-Fi, 10 servers and two point-to-point links. Check for overlaps.",
            "Paste the sample switch config, fix every high finding, and explain each in one sentence.",
            "Read the sample capture and decide: scan, monitoring or a broken client? List the next two things you'd check.",
            "Write a one-page troubleshooting runbook for 'the internet is down' that walks the layers.",
        ],
        "files": ["docs/NETWORK_ENGINEERING.md", "backend/app/services/netlab.py", "backend/app/routers/net.py", "backend/tests/test_network_it.py"],
    },
    {
        "id": "itsupport", "name": "IT Specialist",
        "role": "Keep people productive: fix the problem, protect the data, know what you own, write it down.",
        "summary": "IT support is method more than magic: ask what changed, check the cheap causes first, change one thing at a time and confirm the fix. "
                   "The trackers here are personal-scale versions of a helpdesk and an asset system, and the readers work on exports you paste.",
        "tools": [
            {"name": "Helpdesk tickets with SLA clocks (built in)", "install": "Open the IT dashboard, tab Helpdesk. Each category has a first-line checklist."},
            {"name": "Asset inventory (built in)", "install": "Inventory tab: owner, serial, warranty, status. Flags warranties ending within 90 days."},
            {"name": "Windows event log reader (built in)", "install": "Export from Event Viewer as CSV, or paste lines with Event IDs. Findings are leads."},
            {"name": "Checklists, capacity and RAID calculators (built in)", "install": "Onboarding, offboarding, new PC and outage checklists; disk-full forecast; availability; RAID."},
            {"name": "PowerShell, Bash, Active Directory, Group Policy", "install": "The cheat sheet tab lists safe starting commands. Practise Active Directory in a Windows Server evaluation VM."},
            {"name": "osTicket, GLPI, Snipe-IT, Zabbix", "install": "Not embedded. Free open-source helpdesk, asset and monitoring systems to try in a VM."},
            {"name": "Intune, Entra ID, Microsoft 365 admin", "install": "Not embedded: cloud services are out of scope here."},
        ],
        "path": [
            file("docs/IT_SPECIALIST.md", "The habits that matter, what is built in, and what isn't."),
            page("Check settings and backups", "/settings", "A tested backup is the best fix for most disasters."),
            file("backend/app/services/itlab.py", "Ticket SLA clocks, the event-ID table and the calculators in plain code."),
            page("Read the activity log", "/activity", "An audit trail: who changed what and when."),
            file("backend/app/routers/it.py", "The endpoints behind the IT tools."),
        ],
        "projects": [
            "Log five realistic tickets, work each checklist, resolve them, and read the mean time to resolve.",
            "Enter your own devices in the inventory and list the warranties that end this year.",
            "Paste the sample event log, rank the findings, and write what you'd do first.",
            "Write your own onboarding and offboarding checklist for a five-person business and run both once.",
        ],
        "files": ["docs/IT_SPECIALIST.md", "backend/app/services/itlab.py", "backend/app/routers/it.py", "backend/tests/test_network_it.py"],
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
