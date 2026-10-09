"""Study state kept in the same DuckDB file as the data: learning progress, ML experiment log, AI question log.

Keeping it in the database (not the browser) means it survives clearing site data, works across browsers, and the
dashboard widgets can read it. It never touches the fact/dimension tables, so importing new data can't erase it.
"""
import json

from app.services.db import fetch_all, get_cursor


def ensure_tables() -> None:
    with get_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS study_progress (item_id VARCHAR PRIMARY KEY, done_at TIMESTAMP DEFAULT now());
            CREATE TABLE IF NOT EXISTS ml_runs (
                id VARCHAR PRIMARY KEY DEFAULT uuid()::VARCHAR, created_at TIMESTAMP DEFAULT now(), task VARCHAR, model VARCHAR,
                features VARCHAR, metric VARCHAR, model_score DOUBLE, baseline_score DOUBLE, test_rows INTEGER);
            CREATE TABLE IF NOT EXISTS ai_log (
                id VARCHAR PRIMARY KEY DEFAULT uuid()::VARCHAR, created_at TIMESTAMP DEFAULT now(), question VARCHAR, provider VARCHAR,
                model VARCHAR, kind VARCHAR, input_tokens INTEGER, output_tokens INTEGER, ok BOOLEAN, charted BOOLEAN)""")


# ---- progress ----
def done_items() -> dict[str, str]:
    with get_cursor() as cur:
        return {r["item_id"]: str(r["done_at"]) for r in fetch_all(cur, "SELECT item_id, done_at FROM study_progress")}


def set_done(item_id: str, done: bool) -> None:
    with get_cursor() as cur:
        if done:
            cur.execute("INSERT INTO study_progress (item_id) VALUES (?) ON CONFLICT DO NOTHING", [item_id])
        else:
            cur.execute("DELETE FROM study_progress WHERE item_id = ?", [item_id])


# ---- ML experiment log ----
def log_ml_run(res: dict) -> None:
    pm = res["primary_metric"]
    with get_cursor() as cur:
        cur.execute("INSERT INTO ml_runs (task, model, features, metric, model_score, baseline_score, test_rows) VALUES (?,?,?,?,?,?,?)",
                    [res["task"], res["model"], json.dumps(res["features"]), pm["name"], pm["model"], pm["baseline"], res["split"]["test_rows"]])
        cur.execute("DELETE FROM ml_runs WHERE id NOT IN (SELECT id FROM ml_runs ORDER BY created_at DESC LIMIT 500)")


def ml_runs(limit: int = 12) -> list[dict]:
    with get_cursor() as cur:
        rows = fetch_all(cur, "SELECT created_at, task, model, features, metric, model_score, baseline_score, test_rows "
                              "FROM ml_runs ORDER BY created_at DESC LIMIT ?", [limit])
    for r in rows:
        r["created_at"] = str(r["created_at"])[:19]
        r["features"] = json.loads(r["features"] or "[]")
    return rows


# ---- AI question log ----
def log_ai(question: str, provider: str, model: str, kind: str, tin: int, tout: int, ok: bool, charted: bool) -> None:
    with get_cursor() as cur:
        cur.execute("INSERT INTO ai_log (question, provider, model, kind, input_tokens, output_tokens, ok, charted) VALUES (?,?,?,?,?,?,?,?)",
                    [question[:500], provider, model, kind, tin, tout, ok, charted])
        cur.execute("DELETE FROM ai_log WHERE id NOT IN (SELECT id FROM ai_log ORDER BY created_at DESC LIMIT 500)")


def ai_summary() -> dict:
    with get_cursor() as cur:
        tot = fetch_all(cur, "SELECT COUNT(*) AS questions, COALESCE(SUM(input_tokens),0) AS tin, COALESCE(SUM(output_tokens),0) AS tout, "
                             "COALESCE(SUM(CASE WHEN charted THEN 1 ELSE 0 END),0) AS charts FROM ai_log")[0]
        by = fetch_all(cur, "SELECT provider, COUNT(*) AS questions FROM ai_log GROUP BY 1 ORDER BY 2 DESC")
        recent = fetch_all(cur, "SELECT created_at, question, provider, kind, ok FROM ai_log ORDER BY created_at DESC LIMIT 8")
    for r in recent:
        r["created_at"] = str(r["created_at"])[:19]
    return {"totals": {k: int(v) for k, v in tot.items()}, "by_provider": by, "recent": recent}
