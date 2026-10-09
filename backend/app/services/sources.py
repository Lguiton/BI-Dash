"""Data sources: saved connections that pull data into the active workspace, on demand or on a schedule.

Kinds
  file  a CSV/Excel/JSON file in an allowed folder (the inbox by default; more via BI_SOURCE_DIRS)
  url   an https CSV/JSON link; an optional bearer token is read from an environment variable, never stored
  sql   a read-only SELECT against Postgres (password in an environment variable) or a SQLite file

Safety: loads are staged and swapped in one transaction; a replace that would shrink a table below 50% of its old row
count is refused; Real gets a backup first. Credentials never go into the state file.
"""
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import os

from app.config import MAX_TABLE_UPLOAD_BYTES, MAX_TABLE_ROWS, scheduler_enabled, source_dirs
from app.services import backups, datasets, state, workspaces

KINDS = ("file", "url", "sql")
ENV_RE = re.compile(r"^[A-Z_][A-Z0-9_]{0,63}$")
SQL_START = re.compile(r"^\s*(select|with)\b", re.I)
SQL_BAD = re.compile(r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|call|do|vacuum|attach)\b", re.I)
MIN_REFRESH_RATIO = 0.5
_run_lock = threading.Lock()


class SourceError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


# ------------------------------------------------------------------ config checks
def _allowed_file(path: str) -> Path:
    if not path or not path.strip():
        raise SourceError("Give a file name from the inbox or a full path inside an allowed folder.")
    roots = [r.resolve() for r in source_dirs()]
    p = Path(path).expanduser()
    candidates = [p] if p.is_absolute() else [r / p for r in roots]
    for c in candidates:
        rc = c.resolve()
        if any(rc == r or r in rc.parents for r in roots):
            if rc.is_file():
                return rc
    allowed = ", ".join(str(r) for r in roots)
    raise SourceError(f"'{path}' was not found in an allowed folder. Allowed: {allowed}. Add folders with BI_SOURCE_DIRS.", 404)


def validate_config(kind: str, cfg: dict) -> dict:
    if kind not in KINDS:
        raise SourceError(f"kind must be one of {', '.join(KINDS)}.")
    cfg = dict(cfg or {})
    if kind == "file":
        _allowed_file(str(cfg.get("path", "")))
        return {"path": str(cfg["path"]), "sheet": cfg.get("sheet") or None}
    if kind == "url":
        u = urlparse(str(cfg.get("url", "")))
        if u.scheme not in ("http", "https") or not u.netloc:
            raise SourceError("The URL must start with http:// or https://.")
        env = cfg.get("auth_env")
        if env and not ENV_RE.match(str(env)):
            raise SourceError("auth_env must be an environment variable name like MY_API_TOKEN (the token itself is never stored).")
        return {"url": str(cfg["url"]), "auth_env": env or None, "format": cfg.get("format") or None}
    driver = cfg.get("driver")
    query = str(cfg.get("query", ""))
    if driver not in ("postgres", "sqlite"):
        raise SourceError("driver must be postgres or sqlite.")
    if not SQL_START.match(query) or SQL_BAD.search(query) or ";" in query.strip().rstrip(";"):
        raise SourceError("The query must be a single SELECT (or WITH ... SELECT). Anything that writes is refused.")
    if driver == "postgres":
        env = str(cfg.get("dsn_env", ""))
        if not ENV_RE.match(env):
            raise SourceError("dsn_env must be the name of an environment variable holding the connection string, e.g. PG_URL.")
        return {"driver": driver, "dsn_env": env, "query": query.strip().rstrip(";")}
    _allowed_file(str(cfg.get("path", "")))
    return {"driver": driver, "path": str(cfg["path"]), "query": query.strip().rstrip(";")}


# ------------------------------------------------------------------ fetching
def _sql_cell(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat(sep=" ")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return format(v, "f")
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (bytes, memoryview)):
        return None
    return str(v)


def fetch(kind: str, cfg: dict) -> tuple[list[str], list[list], str]:
    """Return (header, rows, description). Rows are strings or None."""
    if kind == "file":
        p = _allowed_file(cfg["path"])
        if p.stat().st_size > MAX_TABLE_UPLOAD_BYTES:
            raise SourceError("That file is over the size limit.")
        h, r, _ = datasets.read_table(p.read_bytes(), p.name, cfg.get("sheet"))
        return h, r, p.name
    if kind == "url":
        req = urllib.request.Request(cfg["url"], headers={"User-Agent": "bi-dashboard/2", "Accept": "text/csv, application/json, */*"})
        if cfg.get("auth_env"):
            tok = os.environ.get(cfg["auth_env"])
            if not tok:
                raise SourceError(f"The environment variable {cfg['auth_env']} is not set.")
            req.add_header("Authorization", f"Bearer {tok}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read(MAX_TABLE_UPLOAD_BYTES + 1)
                ctype = resp.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            raise SourceError(f"The server answered {e.code} {e.reason}.", 502) from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise SourceError(f"Could not reach the URL: {getattr(e, 'reason', e)}", 502) from e
        if len(raw) > MAX_TABLE_UPLOAD_BYTES:
            raise SourceError("The download is over the size limit.")
        path = urlparse(cfg["url"]).path.lower()
        fmt = cfg.get("format") or ("json" if "json" in ctype or path.endswith(".json") else "xlsx" if path.endswith((".xlsx", ".xlsm")) else "csv")
        h, r, _ = datasets.read_table(raw, f"download.{fmt}")
        return h, r, urlparse(cfg["url"]).netloc
    return _fetch_sql(cfg)


def _fetch_sql(cfg: dict):
    if cfg["driver"] == "sqlite":
        p = _allowed_file(cfg["path"])
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=10)
        try:
            con.execute("PRAGMA query_only = ON")
            cur = con.execute(cfg["query"])
            header = [d[0] for d in cur.description]
            rows = cur.fetchmany(MAX_TABLE_ROWS + 1)
        except sqlite3.Error as e:
            raise SourceError(f"SQLite error: {e}") from e
        finally:
            con.close()
        desc = p.name
    else:
        dsn = os.environ.get(cfg["dsn_env"])
        if not dsn:
            raise SourceError(f"The environment variable {cfg['dsn_env']} is not set.")
        try:
            import psycopg
        except ImportError as e:
            raise SourceError("Postgres support needs psycopg (pip install 'psycopg[binary]').") from e
        try:
            with psycopg.connect(dsn, connect_timeout=10) as con:
                con.read_only = True                       # the server refuses writes, whatever the query says
                with con.cursor() as cur:
                    cur.execute("SET statement_timeout = '60s'")
                    cur.execute(cfg["query"])
                    header = [d.name for d in cur.description]
                    rows = cur.fetchmany(MAX_TABLE_ROWS + 1)
        except psycopg.Error as e:
            raise SourceError(f"Postgres error: {str(e).splitlines()[0]}", 502) from e
        desc = "postgres"
    if len(rows) > MAX_TABLE_ROWS:
        raise SourceError(f"The query returned over {MAX_TABLE_ROWS:,} rows. Add a WHERE or aggregate it.")
    if not rows:
        raise SourceError("The query returned no rows.")
    out = [[None if (c := _sql_cell(v)) is None or c.strip().lower() in datasets.NULL_TOKENS else c.strip() for v in r] for r in rows]
    return list(header), out, desc


def preview(kind: str, cfg: dict, limit: int = 8) -> dict:
    cfg = validate_config(kind, cfg)
    header, rows, desc = fetch(kind, cfg)
    names = datasets.sanitize_columns(header)
    cols = datasets.infer_types(names, rows)
    return {"from": desc, "rows": len(rows), "columns": [{"name": c["name"], "type": c["type"]} for c in cols],
            "preview": [dict(zip(names, r)) for r in rows[:limit]]}


# ------------------------------------------------------------------ CRUD
def _row(r: dict) -> dict:
    import json
    r = dict(r)
    r["config"] = json.loads(r["config"] or "{}")
    r["enabled"] = bool(r["enabled"])
    for k in ("auth_env",):   # not secret (it is a variable name) but keep output tidy
        pass
    return r


def list_sources(ws: str | None = None) -> list[dict]:
    ws = ws or workspaces.active()
    return [_row(r) for r in state.rows("SELECT * FROM sources WHERE workspace = ? ORDER BY id", (ws,))]


def get(sid: int) -> dict:
    r = state.one("SELECT * FROM sources WHERE id = ?", (sid,))
    if not r:
        raise SourceError("No such source.", 404)
    return _row(r)


def create(name: str, kind: str, cfg: dict, target: str, load: str = "table", mode: str = "replace", interval_minutes: int = 0) -> dict:
    import json
    name = (name or "").strip()
    if not name:
        raise SourceError("Give the source a name.")
    if load not in ("table", "operations"):
        raise SourceError("load must be table or operations.")
    if mode not in ("replace", "append"):
        raise SourceError("mode must be replace or append.")
    if load == "table" and not (target or "").strip():
        raise SourceError("Give the table a name.")
    cfg = validate_config(kind, cfg)
    cfg.update({"load": load, "mode": mode})
    interval = max(0, min(int(interval_minutes or 0), 60 * 24 * 30))
    if interval and interval < 5:
        raise SourceError("The shortest schedule is every 5 minutes.")
    cur = state.run("INSERT INTO sources (workspace, name, kind, config, target, interval_minutes, enabled, created_at) VALUES (?,?,?,?,?,?,1,?)",
                    (workspaces.active(), name[:80], kind, json.dumps(cfg), datasets.table_name_for(target) if load == "table" else "fact_operations", interval, state.now()))
    state.audit("source_create", f"{name} ({kind})")
    return get(cur.lastrowid)


def update(sid: int, changes: dict) -> dict:
    s = get(sid)
    sets, vals = [], []
    if "name" in changes and changes["name"]:
        sets.append("name = ?"); vals.append(str(changes["name"])[:80])
    if "enabled" in changes and changes["enabled"] is not None:
        sets.append("enabled = ?"); vals.append(1 if changes["enabled"] else 0)
    if "interval_minutes" in changes and changes["interval_minutes"] is not None:
        iv = max(0, min(int(changes["interval_minutes"]), 60 * 24 * 30))
        if iv and iv < 5:
            raise SourceError("The shortest schedule is every 5 minutes.")
        sets.append("interval_minutes = ?"); vals.append(iv)
    if sets:
        state.run(f"UPDATE sources SET {', '.join(sets)} WHERE id = ?", (*vals, sid))
        state.audit("source_update", f"{s['name']}: {', '.join(changes)}")
    return get(sid)


def delete(sid: int) -> None:
    s = get(sid)
    state.run("DELETE FROM source_runs WHERE source_id = ?", (sid,))
    state.run("DELETE FROM sources WHERE id = ?", (sid,))
    state.audit("source_delete", s["name"])


def runs(sid: int, limit: int = 20) -> list[dict]:
    get(sid)
    return state.rows("SELECT at, ok, rows, message, seconds FROM source_runs WHERE source_id = ? ORDER BY id DESC LIMIT ?", (sid, limit))


# ------------------------------------------------------------------ running
def run_source(sid: int) -> dict:
    """Pull one source now. Always records the outcome; returns it (raises SourceError if it failed, after recording)."""
    s = get(sid)
    if s["workspace"] != workspaces.active():
        raise SourceError(f"'{s['name']}' belongs to the {s['workspace'].title()} workspace. Switch to it first.", 409)
    cfg = s["config"]
    t0 = time.time()
    try:
        with _run_lock:
            header, rows, _ = fetch(s["kind"], cfg)
            if s["workspace"] == "real":
                backups.safety_backup(f"before-refresh")
            if cfg.get("load") == "operations":
                res = _load_operations(header, rows, cfg.get("mode", "replace"))
                n = res["rows_loaded"]
            else:
                res = datasets.import_rows(header, rows, s["target"], cfg.get("mode", "replace"), source=f"source:{s['name']}", min_ratio=MIN_REFRESH_RATIO)
                n = res["added"]
        msg = f"{n:,} rows loaded"
        ok = True
    except datasets.DataError as e:
        ok, msg, n = False, e.message, 0
    except SourceError as e:
        ok, msg, n = False, e.message, 0
    except Exception as e:  # noqa: BLE001 - a bad source must never crash the scheduler
        ok, msg, n = False, f"{type(e).__name__}: {str(e)[:200]}", 0
    secs = round(time.time() - t0, 2)
    state.run("UPDATE sources SET last_run_at = ?, last_status = ?, last_message = ? WHERE id = ?", (state.now(), "ok" if ok else "error", msg, sid))
    state.run("INSERT INTO source_runs (source_id, at, ok, rows, message, seconds) VALUES (?,?,?,?,?,?)", (sid, state.now(), 1 if ok else 0, n, msg, secs))
    state.run("DELETE FROM source_runs WHERE source_id = ? AND id NOT IN (SELECT id FROM source_runs WHERE source_id = ? ORDER BY id DESC LIMIT 100)", (sid, sid))
    state.audit("source_run", f"{s['name']}: {msg}", ok=ok)
    if not ok:
        raise SourceError(msg, 422)
    return {"ok": True, "rows": n, "message": msg, "seconds": secs}


def _load_operations(header: list[str], rows: list[list], mode: str) -> dict:
    import csv
    import io

    from app.routers import ingest
    from app.services.db import get_cursor
    if mode == "replace":
        with get_cursor() as cur:
            old = cur.execute("SELECT COUNT(*) FROM fact_operations").fetchone()[0]
        if old and len(rows) < old * MIN_REFRESH_RATIO:
            raise SourceError(f"Refusing to replace: {len(rows):,} new rows vs {old:,} existing (under {int(MIN_REFRESH_RATIO * 100)}%).", 409)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow(["" if c is None else c for c in r])
    try:
        return ingest.load_operations_text(buf.getvalue(), mode)
    except ingest.IngestError as e:
        raise SourceError(f"{e.message} First problem: {e.errors[0] if e.errors else 'unknown'}") from e


def due(now_dt: datetime | None = None) -> list[dict]:
    now_dt = now_dt or datetime.now(timezone.utc)
    out = []
    for s in list_sources():
        if not s["enabled"] or not s["interval_minutes"]:
            continue
        if s["last_run_at"]:
            last = datetime.strptime(s["last_run_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if now_dt - last < timedelta(minutes=s["interval_minutes"]):
                continue
        out.append(s)
    return out


def tick() -> int:
    """One scheduler pass: automatic backup, then every source that is due. Returns how many sources ran."""
    try:
        backups.maybe_auto()
    except Exception:  # noqa: BLE001
        pass
    n = 0
    for s in due():
        try:
            run_source(s["id"])
        except SourceError:
            pass
        n += 1
    return n


class Scheduler:
    def __init__(self, every: float = 30.0):
        self.every, self._stop, self._t = every, threading.Event(), None

    def start(self):
        if self._t is None and scheduler_enabled():
            self._t = threading.Thread(target=self._loop, name="bi-scheduler", daemon=True)
            self._t.start()

    def _loop(self):
        while not self._stop.wait(self.every):
            try:
                tick()
            except Exception:  # noqa: BLE001
                pass

    def stop(self):
        self._stop.set()
        if self._t:
            self._t.join(timeout=5)
