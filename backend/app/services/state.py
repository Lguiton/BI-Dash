"""App state in a small SQLite file next to the databases.

Everything here must survive switching between the Practice and Real workspaces, so it can't live in either DuckDB file:
study progress, the ML experiment log, the AI question log, per-workspace settings, saved data sources and the audit log.
"""
import json
import sqlite3
import threading
from datetime import datetime, timezone

from app.config import state_path

_lock = threading.RLock()
_conns: dict[str, sqlite3.Connection] = {}

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS study_progress (item_id TEXT PRIMARY KEY, done_at TEXT);
CREATE TABLE IF NOT EXISTS ml_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, task TEXT, model TEXT, features TEXT,
    metric TEXT, model_score REAL, baseline_score REAL, test_rows INTEGER, workspace TEXT);
CREATE TABLE IF NOT EXISTS ai_log (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, question TEXT, provider TEXT, model TEXT,
    kind TEXT, input_tokens INTEGER, output_tokens INTEGER, ok INTEGER, charted INTEGER, workspace TEXT);
CREATE TABLE IF NOT EXISTS settings (workspace TEXT, key TEXT, value TEXT, PRIMARY KEY (workspace, key));
CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, workspace TEXT, action TEXT, detail TEXT, ok INTEGER);
CREATE TABLE IF NOT EXISTS sources (id INTEGER PRIMARY KEY AUTOINCREMENT, workspace TEXT, name TEXT, kind TEXT, config TEXT, target TEXT,
    interval_minutes INTEGER DEFAULT 0, enabled INTEGER DEFAULT 1, created_at TEXT, last_run_at TEXT, last_status TEXT, last_message TEXT);
CREATE TABLE IF NOT EXISTS source_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER, at TEXT, ok INTEGER, rows INTEGER, message TEXT, seconds REAL);
"""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def conn() -> sqlite3.Connection:
    """One connection per state file (tests use a fresh file each time)."""
    p = state_path()
    key = str(p)
    with _lock:
        c = _conns.get(key)
        if c is None:
            p.parent.mkdir(parents=True, exist_ok=True)
            c = sqlite3.connect(key, check_same_thread=False, isolation_level=None)
            c.row_factory = sqlite3.Row
            c.executescript(SCHEMA)
            _conns[key] = c
        return c


def close_all() -> None:
    with _lock:
        for c in _conns.values():
            c.close()
        _conns.clear()


def run(sql: str, params: tuple | list = ()) -> sqlite3.Cursor:
    with _lock:
        return conn().execute(sql, params)


def rows(sql: str, params: tuple | list = ()) -> list[dict]:
    with _lock:
        return [dict(r) for r in conn().execute(sql, params).fetchall()]


def one(sql: str, params: tuple | list = ()) -> dict | None:
    r = rows(sql, params)
    return r[0] if r else None


# ---- key/value (active workspace, migration flags) ----
def kv_get(key: str, default: str | None = None) -> str | None:
    r = one("SELECT value FROM kv WHERE key = ?", (key,))
    return r["value"] if r else default


def kv_set(key: str, value: str) -> None:
    run("INSERT INTO kv (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))


# ---- per-workspace settings (JSON values) ----
def setting_get(workspace: str, key: str, default=None):
    r = one("SELECT value FROM settings WHERE workspace = ? AND key = ?", (workspace, key))
    return json.loads(r["value"]) if r else default


def setting_set(workspace: str, key: str, value) -> None:
    run("INSERT INTO settings (workspace, key, value) VALUES (?, ?, ?) ON CONFLICT(workspace, key) DO UPDATE SET value = excluded.value",
        (workspace, key, json.dumps(value)))


# ---- audit ----
def audit(action: str, detail: str = "", ok: bool = True, workspace: str | None = None) -> None:
    """Record something that changed or left the app. Never raises: a logging problem must not break the action itself."""
    try:
        if workspace is None:
            from app.services import workspaces
            workspace = workspaces.active()
        run("INSERT INTO audit (at, workspace, action, detail, ok) VALUES (?,?,?,?,?)", (now(), workspace, action, detail[:500], 1 if ok else 0))
        run("DELETE FROM audit WHERE id NOT IN (SELECT id FROM audit ORDER BY id DESC LIMIT 5000)")
    except Exception:  # noqa: BLE001
        pass
