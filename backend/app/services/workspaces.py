"""Practice and Real workspaces: two separate DuckDB files, one active at a time.

Practice is the original database (sample data, safe to break). Real starts empty and is never seeded with demo rows.
Switching closes one file and opens the other; study progress, settings, sources and the audit log live in state.py and
are unaffected. The active workspace is remembered across restarts.
"""
import threading

from app.config import seed_demo_enabled, workspace_paths
from app.services import db, state

NAMES = ("practice", "real")
LABELS = {"practice": "Practice", "real": "Real"}
DEFAULT_SETTINGS = {
    "practice": {"ai_mode": "full", "blocked_columns": [], "backup_keep": 14, "auto_backup": False},
    "real": {"ai_mode": "off", "blocked_columns": [], "backup_keep": 14, "auto_backup": True},
}
AI_MODES = ("off", "aggregate", "full")

_lock = threading.RLock()
_active: str | None = None


class WorkspaceError(Exception):
    pass


def active() -> str:
    global _active
    if _active is None:
        saved = state.kv_get("active_workspace", "practice")
        _active = saved if saved in NAMES else "practice"
    return _active


def path_of(name: str):
    if name not in NAMES:
        raise WorkspaceError(f"Unknown workspace '{name}'. Choose practice or real.")
    return workspace_paths()[name]


def _prepare(name: str) -> None:
    """Create/upgrade the tables in the workspace that is now open."""
    from app.routers import kpis, scd
    from app.services import datasets
    db.init_bi_schema(seed=None if name == "practice" else False)
    scd.ensure_tables()
    kpis.ensure_table()
    datasets.ensure_registry()
    if name == "practice":
        _migrate_study_state()


def startup() -> None:
    """Open the remembered workspace (called once when the API starts)."""
    global _active
    with _lock:
        state.conn()
        _active = None
        name = active()
        db.use_path(path_of(name))
        _prepare(name)


def activate(name: str) -> str:
    global _active
    with _lock:
        path_of(name)
        if name == _active:
            return name
        prev = _active
        db.use_path(path_of(name))
        _prepare(name)
        _active = name
        state.kv_set("active_workspace", name)
        state.audit("workspace_switch", f"{prev} -> {name}", workspace=name)
        return name


def settings(name: str | None = None) -> dict:
    name = name or active()
    out = dict(DEFAULT_SETTINGS[name])
    for k in out:
        v = state.setting_get(name, k, None)
        if v is not None:
            out[k] = v
    return out


def update_settings(name: str, changes: dict) -> dict:
    path_of(name)
    cur = settings(name)
    for k, v in changes.items():
        if k not in cur or v is None:
            continue
        if k == "ai_mode" and v not in AI_MODES:
            raise WorkspaceError(f"ai_mode must be one of {', '.join(AI_MODES)}.")
        if k == "blocked_columns":
            v = sorted({str(x).strip().lower() for x in v if str(x).strip()})[:200]
        if k == "backup_keep":
            v = max(1, min(int(v), 365))
        if k == "auto_backup":
            v = bool(v)
        state.setting_set(name, k, v)
        cur[k] = v
    state.audit("settings_change", ", ".join(f"{k}={cur[k]}" for k in changes if k in cur), workspace=name)
    return cur


def _migrate_study_state() -> None:
    """One-time: older versions kept study progress and logs inside the Practice database. Copy them to the state file."""
    if state.kv_get("study_migrated") == "1":
        return
    try:
        with db.get_cursor() as cur:
            have = {r[0] for r in cur.execute("SELECT table_name FROM information_schema.tables").fetchall()}
            if "study_progress" in have:
                for item_id, done_at in cur.execute("SELECT item_id, CAST(done_at AS VARCHAR) FROM study_progress").fetchall():
                    state.run("INSERT OR IGNORE INTO study_progress (item_id, done_at) VALUES (?, ?)", (item_id, str(done_at)[:19]))
            if "ml_runs" in have:
                for r in cur.execute("SELECT CAST(created_at AS VARCHAR), task, model, features, metric, model_score, baseline_score, test_rows FROM ml_runs ORDER BY created_at").fetchall():
                    state.run("INSERT INTO ml_runs (created_at, task, model, features, metric, model_score, baseline_score, test_rows, workspace) VALUES (?,?,?,?,?,?,?,?,'practice')",
                              (str(r[0])[:19], *r[1:]))
            if "ai_log" in have:
                for r in cur.execute("SELECT CAST(created_at AS VARCHAR), question, provider, model, kind, input_tokens, output_tokens, ok, charted FROM ai_log ORDER BY created_at").fetchall():
                    state.run("INSERT INTO ai_log (created_at, question, provider, model, kind, input_tokens, output_tokens, ok, charted, workspace) VALUES (?,?,?,?,?,?,?,?,?,'practice')",
                              (str(r[0])[:19], r[1], r[2], r[3], r[4], r[5], r[6], 1 if r[7] else 0, 1 if r[8] else 0))
    except Exception:  # noqa: BLE001 - migration is best effort; never block startup
        pass
    state.kv_set("study_migrated", "1")


def overview() -> list[dict]:
    """Per-workspace facts for the switcher and settings page (read from files, so the inactive one is not opened)."""
    out = []
    for n in NAMES:
        p = path_of(n)
        info = {"name": n, "label": LABELS[n], "active": n == active(), "exists": p.exists(),
                "size_bytes": p.stat().st_size if p.exists() else 0, "settings": settings(n)}
        if n == active():
            with db.get_cursor() as cur:
                info["records"] = cur.execute("SELECT COUNT(*) FROM fact_operations").fetchone()[0]
                info["tables"] = cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'main' AND table_type = 'BASE TABLE'").fetchone()[0]
        out.append(info)
    return out
