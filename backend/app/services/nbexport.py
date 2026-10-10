"""Send what you built to a notebook: writes a ready-to-run .ipynb (nbformat 4, built by hand, no extra package).
The notebook opens the warehouse read-only with DuckDB. Set BI_DB to the .duckdb path if it isn't beside the notebook."""
from __future__ import annotations

import json
import re

from app.services import ml_lab, workflows, workspaces


class NbError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _src(text: str) -> list[str]:
    lines = text.split("\n")
    return [l + "\n" for l in lines[:-1]] + [lines[-1]]


def _md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": _src(text)}


def _code(text: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": _src(text)}


def _wrap(cells: list[dict]) -> dict:
    return {"cells": cells, "nbformat": 4, "nbformat_minor": 5,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                         "language_info": {"name": "python"}}}


def _connect() -> str:
    db = workspaces.path_of(workspaces.active()).name
    return ('import os\nimport duckdb\nimport pandas as pd\n\n'
            f'DB = os.environ.get("BI_DB", "{db}")   # path to the warehouse file\n'
            'con = duckdb.connect(DB, read_only=True)')


def _slug(s: str) -> str:
    return (re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower() or "notebook")[:40]


def sql_notebook(sql: str, title: str = "SQL Lab query") -> dict:
    sql = (sql or "").strip().rstrip(";")
    if not sql:
        raise NbError("Write a query first.")
    from app.services import sql_lab
    try:
        sql_lab.validate_readonly(sql)
    except sql_lab.SqlLabError as e:
        raise NbError(str(e)) from e
    return {"filename": f"{_slug(title)}.ipynb", "notebook": _wrap([
        _md(f"# {title}\n\nExported from the BI dashboard SQL Lab. Run the cells top to bottom."),
        _code(_connect()),
        _code(f'query = """\n{sql}\n"""\ndf = con.execute(query).df()\ndf.head(20)'),
        _md("## Next\nTry `df.describe()`, a plot with `df.plot()`, or change the query and run it again."),
        _code("df.describe(include='all')"),
    ])}


def workflow_notebook(steps: list[dict], title: str = "Workflow") -> dict:
    try:
        ex = workflows.explain(steps)
    except workflows.WorkflowError as e:
        raise NbError(str(e), e.status) from e
    return {"filename": f"{_slug(title)}.ipynb", "notebook": _wrap([
        _md(f"# {title}\n\nThe workflow you built, as SQL and as pandas. Both give the same table."),
        _code(_connect()),
        _md("## As SQL"),
        _code(f'query = """\n{ex["sql"]}\n"""\nsql_df = con.execute(query).df()\nsql_df.head(20)'),
        _md("## The same thing in pandas (generated from your steps)"),
        _code("\n".join(l for l in ex["pandas"].split("\n") if not l.startswith(("import duckdb", "con = duckdb"))) + "\ndf.head(20)"),
        _md("Compare `sql_df` with `df` (the pandas result). Writing both is the fastest way to learn either."),
    ])}


def ml_notebook(cfg: dict) -> dict:
    task, feats = cfg.get("task"), list(cfg.get("features") or [])
    if task not in ml_lab.TASKS:
        raise NbError("Pick a task first.")
    bad = [f for f in feats if f not in ml_lab.FEATURES]
    if bad or not feats:
        raise NbError("Pick at least one valid feature first.")
    kind = ml_lab.TASKS[task][1]
    sel = ", ".join(f"{ml_lab.FEATURES[i].sql} AS {i}" for i in feats)
    sql = (f"SELECT f.record_date AS record_date, {ml_lab.TASKS[task][2]} AS target, {sel}\n"
           "FROM fact_operations f LEFT JOIN dim_entities e ON f.entity_id = e.entity_id\n"
           "WHERE f.revenue IS NOT NULL AND f.operational_cost IS NOT NULL\nORDER BY f.record_date")
    num = [f for f in feats if ml_lab.FEATURES[f].kind == "num"]
    cat = [f for f in feats if ml_lab.FEATURES[f].kind == "cat"]
    frac = float(cfg.get("testFraction") or 0.2)
    frac = min(0.5, max(0.1, frac))
    if kind == "regression":
        model, base, metric = "GradientBoostingRegressor(random_state=0)", "DummyRegressor(strategy='mean')", "mean_absolute_error"
        imp = "from sklearn.ensemble import GradientBoostingRegressor\nfrom sklearn.dummy import DummyRegressor\nfrom sklearn.metrics import mean_absolute_error"
        score = "mean_absolute_error(y_test, p)"
        label = "Mean absolute error (lower is better)"
    else:
        model, base, metric = "RandomForestClassifier(random_state=0, class_weight='balanced')", "DummyClassifier(strategy='most_frequent')", "f1"
        imp = "from sklearn.ensemble import RandomForestClassifier\nfrom sklearn.dummy import DummyClassifier\nfrom sklearn.metrics import f1_score"
        score = "f1_score(y_test, p, zero_division=0)"
        label = "F1 on the problem class (higher is better; accuracy alone misleads on rare outcomes)"
    train = f'''{imp}
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer

NUM, CAT = {num!r}, {cat!r}
# time-ordered split: train on the past, test on the most recent rows (a random split would leak the future)
cut = int(len(df) * (1 - {frac}))
train, test = df.iloc[:cut], df.iloc[cut:]
X_train, y_train, X_test, y_test = train[NUM + CAT], train["target"], test[NUM + CAT], test["target"]

pre = ColumnTransformer([
    ("num", SimpleImputer(strategy="median"), NUM),
    ("cat", Pipeline([("fill", SimpleImputer(strategy="constant", fill_value="Unknown")),
                      ("onehot", OneHotEncoder(handle_unknown="ignore"))]), CAT),
])
for name, est in [("baseline", {base}), ("model", {model})]:
    pipe = Pipeline([("pre", pre), ("est", est)]).fit(X_train, y_train)
    p = pipe.predict(X_test)
    print(name, round({score}, 4))'''
    return {"filename": f"ml_{_slug(task)}.ipynb", "notebook": _wrap([
        _md(f"# {ml_lab.TASKS[task][0]}\n\nExported from the ML Lab with your settings. Metric: {label}.\n\n"
            "The baseline is a model that ignores the features; a real model has to beat it."),
        _code(_connect()),
        _code(f'query = """\n{sql}\n"""\ndf = con.execute(query).df()\nprint(len(df), "rows")\ndf.head()'),
        _code(train),
        _md("## Ideas\n- Drop a feature and see what changes.\n- Check feature importance with `permutation_importance`.\n- Remember: a good test score means good on data like this, not a promise about the future."),
    ])}


def build(kind: str, body: dict) -> dict:
    if kind == "sql":
        out = sql_notebook(body.get("sql", ""), body.get("title") or "SQL Lab query")
    elif kind == "workflow":
        out = workflow_notebook(body.get("steps") or [], body.get("title") or "Workflow")
    elif kind == "ml":
        out = ml_notebook(body.get("config") or {})
    else:
        raise NbError("kind must be sql, workflow or ml.")
    json.dumps(out["notebook"])
    return out
