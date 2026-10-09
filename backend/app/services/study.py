"""Study state: learning progress, ML experiment log, AI question log.

Stored in the app-state SQLite file (services/state.py), not in a workspace database, so progress is the same whether you
are looking at Practice or Real data and importing or restoring data can never erase it.
"""
import json

from app.services import state


def ensure_tables() -> None:
    state.conn()


def _ws() -> str:
    from app.services import workspaces
    return workspaces.active()


# ---- progress ----
def done_items() -> dict[str, str]:
    return {r["item_id"]: r["done_at"] for r in state.rows("SELECT item_id, done_at FROM study_progress")}


def set_done(item_id: str, done: bool) -> None:
    if done:
        state.run("INSERT OR IGNORE INTO study_progress (item_id, done_at) VALUES (?, ?)", (item_id, state.now()))
    else:
        state.run("DELETE FROM study_progress WHERE item_id = ?", (item_id,))


# ---- ML experiment log ----
def log_ml_run(res: dict) -> None:
    pm = res["primary_metric"]
    state.run("INSERT INTO ml_runs (created_at, task, model, features, metric, model_score, baseline_score, test_rows, workspace) VALUES (?,?,?,?,?,?,?,?,?)",
              (state.now(), res["task"], res["model"], json.dumps(res["features"]), pm["name"], pm["model"], pm["baseline"], res["split"]["test_rows"], _ws()))
    state.run("DELETE FROM ml_runs WHERE id NOT IN (SELECT id FROM ml_runs ORDER BY id DESC LIMIT 500)")


def ml_runs(limit: int = 12) -> list[dict]:
    rows = state.rows("SELECT created_at, task, model, features, metric, model_score, baseline_score, test_rows FROM ml_runs ORDER BY id DESC LIMIT ?", (limit,))
    for r in rows:
        try:
            r["features"] = json.loads(r["features"] or "[]")
        except ValueError:      # a hand-edited or very old row: show it as one item instead of failing the whole page
            r["features"] = [r["features"]]
    return rows


# ---- AI question log ----
def log_ai(question: str, provider: str, model: str, kind: str, tin: int, tout: int, ok: bool, charted: bool, tier: str = "", track: str = "") -> None:
    state.run("INSERT INTO ai_log (created_at, question, provider, model, kind, input_tokens, output_tokens, ok, charted, workspace, tier, track) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
              (state.now(), question[:500], provider, model, kind, tin, tout, 1 if ok else 0, 1 if charted else 0, _ws(), tier or None, track or None))
    state.run("DELETE FROM ai_log WHERE id NOT IN (SELECT id FROM ai_log ORDER BY id DESC LIMIT 2000)")


def ai_summary() -> dict:
    tot = state.one("SELECT COUNT(*) AS questions, COALESCE(SUM(input_tokens),0) AS tin, COALESCE(SUM(output_tokens),0) AS tout, "
                    "COALESCE(SUM(charted),0) AS charts FROM ai_log") or {}
    by = state.rows("SELECT provider, COUNT(*) AS questions FROM ai_log GROUP BY 1 ORDER BY 2 DESC")
    recent = state.rows("SELECT created_at, question, provider, kind, ok FROM ai_log ORDER BY id DESC LIMIT 8")
    for r in recent:
        r["ok"] = bool(r["ok"])
    return {"totals": {k: int(v) for k, v in tot.items()}, "by_provider": by, "recent": recent}
