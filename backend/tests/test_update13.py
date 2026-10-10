"""Update 13: model comparison, experiment tracker, dataset hub, workflow builder, notebooks service."""
import pathlib

import pytest

from app.services import workflows

pytest.importorskip("sklearn")
pytest.importorskip("pandas")
ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture()
def big(client):
    csv = ROOT / "data_samples" / "operations_clean.csv"
    if not csv.exists():
        import subprocess, sys
        subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_sample_data.py")], check=True)
    assert client.post("/api/ingest/csv?mode=replace", files={"file": ("d.csv", csv.read_bytes(), "text/csv")}).status_code == 200
    return client


FEATS = ["category", "weekday", "units_processed", "duration_minutes"]


# ------------------------------------------------------------ comparison + tracker
def test_compare_ranks_every_model_and_logs_each_run(big):
    r = big.post("/api/ml/compare", json={"task": "revenue", "features": FEATS})
    assert r.status_code == 200
    j = r.json()
    assert {m["model"] for m in j["models"]} == {"linear", "ridge", "random_forest", "gradient_boosting", "neural_net", "hist_gradient_boosting"}
    scores = [m["score"] for m in j["models"]]
    assert scores == sorted(scores, reverse=True) and [m["rank"] for m in j["models"]] == [1, 2, 3, 4, 5, 6]
    assert all(m["run_id"] for m in j["models"])
    assert len(big.get("/api/ml/runs").json()["runs"]) == 6


def test_compare_flags_a_tie_instead_of_declaring_a_winner(big):
    j = big.post("/api/ml/compare", json={"task": "revenue", "features": FEATS}).json()
    top, second = j["models"][0]["score"], j["models"][1]["score"]
    assert (j["note"] is not None) == (abs(top - second) < 0.02)


def test_compare_validates(big):
    assert big.post("/api/ml/compare", json={"task": "revenue", "features": ["nope"]}).status_code == 400
    assert big.post("/api/ml/compare", json={"task": "bogus", "features": FEATS}).status_code == 422


def test_compare_with_too_little_data_says_so(client):
    r = client.post("/api/ml/compare", json={"task": "revenue", "features": FEATS})
    assert r.status_code == 400 and "rows" in r.json()["detail"]


def test_neural_net_trains_alone_and_warns_about_class_balance(big):
    r = big.post("/api/ml/train", json={"task": "not_completed", "model": "neural_net", "features": FEATS, "balance_classes": True})
    assert r.status_code == 200
    assert any("class-weight" in w for w in r.json()["warnings"])


def test_runs_note_star_delete_and_filters(big):
    big.post("/api/ml/compare", json={"task": "revenue", "features": FEATS})
    runs = big.get("/api/ml/runs").json()["runs"]
    rid = runs[0]["id"]
    r = big.patch(f"/api/ml/runs/{rid}", json={"note": "  baseline  ", "starred": True})
    assert r.status_code == 200 and r.json()["note"] == "baseline" and r.json()["starred"] is True
    assert [x["id"] for x in big.get("/api/ml/runs?starred=true").json()["runs"]] == [rid]
    assert big.get("/api/ml/runs?task=profit").json()["runs"] == []
    assert big.delete(f"/api/ml/runs/{rid}").status_code == 200
    assert big.patch(f"/api/ml/runs/{rid}", json={"note": "x"}).status_code == 404


def test_run_compare_explains_what_changed(big):
    big.post("/api/ml/train", json={"task": "revenue", "model": "ridge", "features": FEATS})
    big.post("/api/ml/train", json={"task": "revenue", "model": "random_forest", "features": FEATS})
    big.post("/api/ml/train", json={"task": "revenue", "model": "random_forest", "features": FEATS[:2]})
    ids = [r["id"] for r in big.get("/api/ml/runs").json()["runs"]]
    one = big.post("/api/ml/runs/compare", json={"ids": ids[1:]}).json()           # ridge vs forest: only the model differs
    assert one["changed"] == ["model"] and "attributable" in one["hint"]
    many = big.post("/api/ml/runs/compare", json={"ids": ids}).json()
    assert {"model", "features"} <= set(many["changed"]) and "Several things" in many["hint"]
    assert many["best_id"] in ids


def test_run_compare_refuses_different_tasks_and_bad_counts(big):
    big.post("/api/ml/train", json={"task": "revenue", "model": "ridge", "features": FEATS})
    big.post("/api/ml/train", json={"task": "profit", "model": "ridge", "features": FEATS})
    ids = [r["id"] for r in big.get("/api/ml/runs").json()["runs"]]
    assert big.post("/api/ml/runs/compare", json={"ids": ids}).status_code == 400
    assert big.post("/api/ml/runs/compare", json={"ids": ids[:1]}).status_code == 422
    assert big.post("/api/ml/runs/compare", json={"ids": [999, 998]}).status_code == 404


def test_runs_csv_export(big):
    big.post("/api/ml/train", json={"task": "revenue", "model": "ridge", "features": FEATS})
    r = big.get("/api/ml/runs/export.csv")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("id,created_at,task,model") and len(lines) == 2 and "ridge" in lines[1]


def test_mlflow_copy_is_optional_and_works_when_installed(big, monkeypatch):
    big.post("/api/ml/train", json={"task": "revenue", "model": "ridge", "features": FEATS})
    try:
        import mlflow  # noqa: F401
    except ImportError:
        assert big.post("/api/ml/runs/mlflow").status_code == 501
        return
    monkeypatch.setenv("MLFLOW_DISABLE_AGENT_HINT", "1")
    r = big.post("/api/ml/runs/mlflow")
    assert r.status_code == 200 and r.json()["copied"] == 1 and "mlflow ui" in r.json()["view_with"]


def test_mlflow_missing_gives_a_clear_install_hint(big, monkeypatch):
    import builtins
    real = builtins.__import__

    def fake(name, *a, **k):
        if name == "mlflow":
            raise ImportError("no mlflow")
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", fake)
    big.post("/api/ml/train", json={"task": "revenue", "model": "ridge", "features": FEATS})
    r = big.post("/api/ml/runs/mlflow")
    assert r.status_code == 501 and "pip install mlflow" in r.json()["detail"]


def test_old_state_files_get_the_new_run_columns(tmp_path):
    import sqlite3
    from app.services import state
    c = sqlite3.connect(tmp_path / "old.sqlite")
    c.execute("CREATE TABLE ml_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, task TEXT, model TEXT, features TEXT, metric TEXT, model_score REAL, baseline_score REAL, test_rows INTEGER, workspace TEXT)")
    c.execute("CREATE TABLE ai_log (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, question TEXT, provider TEXT, model TEXT, kind TEXT, input_tokens INTEGER, output_tokens INTEGER, ok INTEGER, charted INTEGER, workspace TEXT)")
    state._migrate(c)
    cols = {r[1] for r in c.execute("PRAGMA table_info(ml_runs)")}
    assert {"note", "starred", "params", "metrics", "cv_mean", "seconds", "batch"} <= cols


# ------------------------------------------------------------ dataset hub
CSV = "d,city,amt,id\n" + "\n".join(f"2026-01-{i % 28 + 1:02d},{'AB'[i % 2]},{i * 3},id{i}" for i in range(40)) + "\n2026-01-05,A,,idx\n2026-01-05,A,,idx\n2026-01-06,B,,idy\n2026-01-07,B,,idz\n2026-01-08,A,,idw\n"


def _imp(client, name="hubt", text=CSV):
    r = client.post(f"/api/data/import?table={name}", files={"file": (name + ".csv", text.encode(), "text/csv")})
    assert r.status_code == 200, r.text


def test_hub_health_check_finds_real_problems(client):
    _imp(client)
    j = client.get("/api/hub/hubt").json()
    titles = " | ".join(c["title"] for c in j["checks"])
    assert "duplicate rows" in titles and "'amt'" in titles and "ID or free text" in titles
    assert j["grade"] == "needs attention" and j["ideas"]


def test_hub_clean_table_and_missing_table(client):
    _imp(client, "clean", "a,b\n" + "\n".join(f"{i % 5},{i}" for i in range(60)) + "\n")
    j = client.get("/api/hub/clean").json()
    assert j["rows"] == 61 or j["rows"] == 60
    assert client.get("/api/hub/nope").status_code == 404


def test_hub_notes_and_tags_are_cleaned_and_scoped(client):
    _imp(client)
    r = client.put("/api/hub/hubt/notes", json={"note": " from finance ", "tags": ["Sales!", "q1", "sales", "  "]})
    assert r.status_code == 200 and r.json()["note"] == "from finance" and r.json()["tags"] == ["sales", "q1"]
    row = next(t for t in client.get("/api/hub").json()["tables"] if t["table"] == "hubt")
    assert row["has_note"] and row["tags"] == ["sales", "q1"]
    assert client.put("/api/hub/nope/notes", json={"note": "x", "tags": []}).status_code == 404
    assert client.put("/api/hub/hubt/notes", json={"note": "x", "tags": [f"t{i}" for i in range(9)]}).status_code == 400


# ------------------------------------------------------------ workflow builder
SRC = {"kind": "source", "table": "v_operations_flat"}
CHAIN = [SRC,
         {"kind": "filter", "column": "revenue", "op": ">", "value": 100},
         {"kind": "derive", "name": "net", "a": "revenue", "op": "-", "b_column": "operational_cost"},
         {"kind": "aggregate", "group_by": ["category"], "measures": [{"column": "net", "agg": "sum"}, {"column": "*", "agg": "count"}]},
         {"kind": "sort", "column": "sum_net", "desc": True},
         {"kind": "limit", "n": 3}]


def test_workflow_runs_and_reports_rows_per_step(big):
    j = big.post("/api/workflows/run", json={"steps": CHAIN}).json()
    assert j["names"] == ["category", "sum_net", "rows"] and len(j["rows"]) == 3
    assert j["row_counts"][0] >= j["row_counts"][1] > 0 and j["row_counts"][-1] == 3
    assert j["rows"][0][1] >= j["rows"][1][1]
    assert "WITH s0 AS" in j["sql"] and "groupby" in j["pandas"] and len(j["notes"]) == len(CHAIN)


def test_workflow_pandas_matches_the_sql(big):
    """The teaching code must give the same answer as the query we run."""
    import duckdb, pandas as pd
    from app.services.db import get_cursor
    j = big.post("/api/workflows/run", json={"steps": CHAIN}).json()
    with get_cursor() as cur:
        class Con:
            def sql(self, s):
                return cur.execute(s)
        ns = {"duckdb": duckdb, "pd": pd, "con": Con()}
        exec("\n".join(j["pandas"].split("\n")[2:]), ns)
    df = ns["df"]
    assert list(df["category"]) == [r[0] for r in j["rows"]]
    assert [round(x, 2) for x in df["sum_net"]] == [round(r[1], 2) for r in j["rows"]]
    assert list(df["rows"]) == [r[2] for r in j["rows"]]


def test_workflow_validation_names_the_step_and_options(big):
    bad = [SRC, {"kind": "filter", "column": "nope", "op": "=", "value": 1}]
    r = big.post("/api/workflows/run", json={"steps": bad})
    assert r.status_code == 400 and r.json()["detail"].startswith("Step 1 (filter)") and "Available:" in r.json()["detail"]
    for steps, frag in [
        ([{"kind": "filter", "column": "revenue", "op": ">", "value": 1}], "first step must be the source"),
        ([{"kind": "source", "table": "user_tables"}], "isn't a table"),
        ([SRC, {"kind": "filter", "column": "revenue", "op": ">", "value": "abc"}], "number"),
        ([SRC, {"kind": "filter", "column": "revenue", "op": "~", "value": 1}], "Pick a comparison"),
        ([SRC, {"kind": "derive", "name": "x", "a": "category", "op": "+", "b_value": 1}], "needs number"),
        ([SRC, {"kind": "derive", "name": "x", "a": "revenue", "op": "/", "b_value": 0}], "divide by zero"),
        ([SRC, {"kind": "derive", "name": "revenue", "a": "units_processed", "op": "+", "b_value": 1}], "already exists"),
        ([SRC, {"kind": "aggregate", "group_by": [], "measures": []}], "at least one measure"),
        ([SRC, {"kind": "aggregate", "group_by": [], "measures": [{"column": "category", "agg": "sum"}]}], "needs number"),
        ([SRC, {"kind": "limit", "n": 0}], "between 1"),
        ([SRC, {"kind": "mystery"}], "unknown step"),
    ]:
        r = big.post("/api/workflows/run", json={"steps": steps})
        assert r.status_code in (400, 404) and frag in r.json()["detail"], (steps, r.text)


def test_workflow_values_cannot_inject_sql(big):
    evil = "x'; DROP TABLE fact_operations; --"
    r = big.post("/api/workflows/run", json={"steps": [SRC, {"kind": "filter", "column": "category", "op": "=", "value": evil}]})
    assert r.status_code == 200 and r.json()["total_rows"] == 0
    r = big.post("/api/workflows/run", json={"steps": [SRC, {"kind": "filter", "column": "category", "op": "contains", "value": "%'; DROP TABLE x;--"}]})
    assert r.status_code == 200
    assert big.get("/api/analytics/summary").status_code == 200       # the data is still there
    r = big.post("/api/workflows/run", json={"steps": [SRC, {"kind": "filter", "column": 'revenue" > 0 OR "1', "op": ">", "value": 1}]})
    assert r.status_code == 400
    r = big.post("/api/workflows/run", json={"steps": [SRC, {"kind": "derive", "name": 'a"; DROP TABLE x;--', "a": "revenue", "op": "+", "b_value": 1}]})
    assert r.status_code == 200 and all(n.replace("_", "").isalnum() for n in r.json()["names"])


def test_workflow_date_and_text_filters(big):
    r = big.post("/api/workflows/run", json={"steps": [SRC, {"kind": "filter", "column": "record_date", "op": ">=", "value": "2099-01-01"}]})
    assert r.status_code == 200 and r.json()["total_rows"] == 0
    r = big.post("/api/workflows/run", json={"steps": [SRC, {"kind": "filter", "column": "category", "op": "contains", "value": "fle"}]})
    assert r.json()["total_rows"] > 0
    r = big.post("/api/workflows/run", json={"steps": [SRC, {"kind": "filter", "column": "revenue", "op": "not_null"}]})
    assert r.json()["total_rows"] > 0


def test_workflow_aggregate_over_all_rows_and_pandas(big):
    steps = [SRC, {"kind": "aggregate", "group_by": [], "measures": [{"column": "revenue", "agg": "sum"}, {"column": "*", "agg": "count"}, {"column": "category", "agg": "distinct"}]}]
    j = big.post("/api/workflows/run", json={"steps": steps}).json()
    assert j["names"] == ["sum_revenue", "rows", "distinct_category"] and j["rows"][0][1] == j["row_counts"][0]


def test_workflow_save_as_table_makes_a_new_imported_table(big):
    r = big.post("/api/workflows/save-table", json={"name": "top_categories", "steps": CHAIN})
    assert r.status_code == 200 and r.json()["rows"] == 3
    assert "top_categories" in [t["table_name"] for t in big.get("/api/data/tables").json()["tables"]]
    assert big.post("/api/workflows/save-table", json={"name": "top_categories", "steps": CHAIN}).status_code == 400       # never overwrites
    before = big.get("/api/analytics/summary").json()
    r = big.post("/api/workflows/save-table", json={"name": "fact_operations", "steps": CHAIN})
    assert r.status_code == 200 and r.json()["table"] == "my_fact_operations"          # renamed: a built-in table is never touched
    assert big.get("/api/analytics/summary").json() == before
    empty = [SRC, {"kind": "filter", "column": "revenue", "op": ">", "value": 1e12}]
    assert big.post("/api/workflows/save-table", json={"name": "nothing", "steps": empty}).status_code == 400
    # an imported table can be a source for the next workflow
    r = big.post("/api/workflows/run", json={"steps": [{"kind": "source", "table": "top_categories"}]})
    assert r.status_code == 200 and r.json()["total_rows"] == 3


def test_workflow_save_list_update_delete(big):
    assert big.post("/api/workflows", json={"name": "", "steps": CHAIN}).status_code == 400
    assert big.post("/api/workflows", json={"name": "bad", "steps": [SRC, {"kind": "limit", "n": 0}]}).status_code == 400
    wid = big.post("/api/workflows", json={"name": "Top 3", "steps": CHAIN}).json()["id"]
    assert big.post("/api/workflows", json={"name": "Top three", "steps": CHAIN, "id": wid}).json()["id"] == wid
    saved = big.get("/api/workflows").json()["workflows"]
    assert len(saved) == 1 and saved[0]["name"] == "Top three" and len(saved[0]["steps"]) == len(CHAIN)
    assert big.post("/api/workflows", json={"name": "x", "steps": CHAIN, "id": 999}).status_code == 404
    assert big.delete(f"/api/workflows/{wid}").status_code == 200 and big.get("/api/workflows").json()["workflows"] == []
    assert big.delete(f"/api/workflows/{wid}").status_code == 404


def test_workflow_sources_list_columns(big):
    names = {s["table"] for s in big.get("/api/workflows/sources").json()["sources"]}
    assert {"fact_operations", "dim_entities", "v_operations_flat"} <= names


def test_workflow_is_capped(big):
    steps = [SRC] + [{"kind": "limit", "n": 5}] * (workflows.MAX_STEPS + 1)
    assert big.post("/api/workflows/run", json={"steps": steps}).status_code == 422


# ------------------------------------------------------------ notebooks service (static)
def test_notebooks_service_is_opt_in_local_and_read_only():
    yaml = pytest.importorskip("yaml")
    c = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]["notebooks"]
    assert c["profiles"] == ["notebooks"]
    assert all(str(p).startswith("127.0.0.1:") for p in c["ports"])
    assert any(str(v).endswith(":ro") and "warehouse" in str(v) for v in c["volumes"])
    assert "JUPYTER_TOKEN" in str(c["environment"])
    assert (ROOT / "python_practice" / "Dockerfile.jupyter").is_file()
