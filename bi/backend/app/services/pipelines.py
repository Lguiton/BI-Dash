"""Pipeline runner: our own small take on an orchestrator like Airflow or Prefect.

A pipeline is a set of tasks with dependencies (task B waits for task A). Task types: run a saved workflow into a table, run a table's
data quality rules, refresh a data source, take a backup. Tasks run in dependency order; if one fails (after its retries) everything
that depends on it is skipped, and the run is recorded. A pipeline can run on demand or every N minutes while the backend is running.

Honest limits: it runs inside this app's process, one task at a time, so it is for a personal dashboard, not a replacement for Airflow
(see apache_practice/airflow for the real thing). If the backend is off, nothing runs; a missed schedule runs once when it is back.
"""
from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime, timedelta, timezone

from app.services import backups, expectations, sources, state, workflows

KINDS = {"workflow": "Run a saved workflow into a table", "dq": "Check a table's quality rules",
         "source": "Refresh a data source", "backup": "Take a backup"}
MAX_TASKS = 15
MAX_RETRIES = 3
_running: set[int] = set()
_lock = threading.Lock()


class PipelineError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _ws() -> str:
    from app.services import workspaces
    return workspaces.active()


def validate(tasks: list[dict]) -> list[dict]:
    if not isinstance(tasks, list) or not tasks:
        raise PipelineError("Add at least one task.")
    if len(tasks) > MAX_TASKS:
        raise PipelineError(f"Use at most {MAX_TASKS} tasks.")
    out, ids = [], set()
    for t in tasks:
        tid = re.sub(r"[^a-z0-9_]+", "_", str(t.get("id", "")).strip().lower()).strip("_")[:30]
        if not tid:
            raise PipelineError("Every task needs a short id (letters, numbers, underscores).")
        if tid in ids:
            raise PipelineError(f"Two tasks are called '{tid}'.")
        ids.add(tid)
        kind = t.get("kind")
        if kind not in KINDS:
            raise PipelineError(f"Task '{tid}': unknown type. Use one of {', '.join(KINDS)}.")
        item = {"id": tid, "kind": kind, "depends_on": [], "retries": 0, "ref": t.get("ref")}
        try:
            item["retries"] = int(t.get("retries", 0))
        except (TypeError, ValueError):
            raise PipelineError(f"Task '{tid}': retries must be a number.") from None
        if not 0 <= item["retries"] <= MAX_RETRIES:
            raise PipelineError(f"Task '{tid}': retries must be 0 to {MAX_RETRIES}.")
        if kind == "workflow":
            wid = t.get("ref")
            if not isinstance(wid, int) or not any(w["id"] == wid for w in workflows.list_saved()):
                raise PipelineError(f"Task '{tid}': pick one of your saved workflows.")
            name = str(t.get("table") or "").strip()
            if not name:
                raise PipelineError(f"Task '{tid}': name the table the workflow should fill.")
            item["table"] = name[:60]
        elif kind == "dq":
            tbl = str(t.get("ref") or "")
            if not expectations.list_rules(tbl):
                raise PipelineError(f"Task '{tid}': '{tbl}' has no quality rules yet.")
            item["fail_on_rule_failure"] = bool(t.get("fail_on_rule_failure", True))
        elif kind == "source":
            sid = t.get("ref")
            try:
                s = sources.get(int(sid))
            except Exception:  # noqa: BLE001
                raise PipelineError(f"Task '{tid}': pick one of your data sources.") from None
            if s["workspace"] != _ws():
                raise PipelineError(f"Task '{tid}': that source belongs to the other workspace.")
            item["ref"] = int(sid)
        else:
            item["ref"] = None
        out.append(item)
    for t, raw in zip(out, tasks):
        deps = raw.get("depends_on") or []
        if not isinstance(deps, list) or any(d not in ids for d in deps) or t["id"] in deps:
            raise PipelineError(f"Task '{t['id']}': depends_on must name other tasks in this pipeline.")
        t["depends_on"] = list(dict.fromkeys(deps))
    order(out)                                            # raises on a cycle
    return out


def order(tasks: list[dict]) -> list[dict]:
    """Dependency order (Kahn). Raises if the tasks wait on each other in a circle."""
    done, left, out = set(), list(tasks), []
    while left:
        ready = [t for t in left if all(d in done for d in t["depends_on"])]
        if not ready:
            raise PipelineError("These tasks wait on each other in a circle: " + ", ".join(t["id"] for t in left) + ". Remove one dependency.")
        for t in ready:
            out.append(t)
            done.add(t["id"])
            left.remove(t)
    return out


def _do(task: dict) -> str:
    k = task["kind"]
    if k == "workflow":
        w = next((w for w in workflows.list_saved() if w["id"] == task["ref"]), None)
        if not w:
            raise PipelineError("The saved workflow no longer exists.")
        r = workflows.save_as_table(w["steps"], task["table"], replace=True)
        return f"{r['rows']:,} rows written to {r['table']}"
    if k == "dq":
        r = expectations.run(task["ref"], trigger="pipeline")
        if r["failed"] and task.get("fail_on_rule_failure", True):
            raise PipelineError(f"{r['failed']} of {r['rules']} rule(s) failed on {task['ref']}.")
        return f"{r['passed']} of {r['rules']} rule(s) passed" + (f" ({r['failed']} failed, continuing)" if r["failed"] else "")
    if k == "source":
        return sources.run_source(task["ref"])["message"]
    b = backups.create("pipeline")
    return f"backup {b.get('name', 'saved')}"


def _run_task(task: dict) -> dict:
    t0, err = time.perf_counter(), ""
    for attempt in range(1, task["retries"] + 2):
        try:
            msg = _do(task)
            return {"id": task["id"], "status": "ok", "attempts": attempt, "seconds": round(time.perf_counter() - t0, 2), "message": msg}
        except (PipelineError, workflows.WorkflowError, expectations.DqError, sources.SourceError, backups.BackupError) as e:
            err = str(e)
        except Exception as e:  # noqa: BLE001  one bad task must not take the scheduler down
            err = f"{type(e).__name__}: {str(e)[:160]}"
        if attempt <= task["retries"]:
            time.sleep(min(2 * attempt, 5))
    return {"id": task["id"], "status": "failed", "attempts": task["retries"] + 1, "seconds": round(time.perf_counter() - t0, 2), "message": err[:300]}


def run(pid: int, trigger: str = "manual") -> dict:
    p = get(pid)
    with _lock:
        if pid in _running:
            raise PipelineError("This pipeline is already running.", 409)
        _running.add(pid)
    t0, results, status = time.perf_counter(), [], {}
    try:
        for t in order(p["tasks"]):
            if any(status.get(d) != "ok" for d in t["depends_on"]):
                bad = [d for d in t["depends_on"] if status.get(d) != "ok"]
                r = {"id": t["id"], "status": "skipped", "attempts": 0, "seconds": 0, "message": f"Skipped because {', '.join(bad)} did not succeed."}
            else:
                r = _run_task(t)
            status[t["id"]] = r["status"]
            results.append(r)
    finally:
        with _lock:
            _running.discard(pid)
    ok = all(r["status"] == "ok" for r in results)
    secs = round(time.perf_counter() - t0, 2)
    state.run("INSERT INTO pipeline_runs (pipeline_id, workspace, at, ok, seconds, trigger, detail) VALUES (?,?,?,?,?,?,?)",
              (pid, _ws(), state.now(), 1 if ok else 0, secs, trigger, json.dumps(results)))
    state.run("UPDATE pipelines SET last_run_at = ?, last_ok = ? WHERE id = ?", (state.now(), 1 if ok else 0, pid))
    state.run("DELETE FROM pipeline_runs WHERE pipeline_id = ? AND id NOT IN (SELECT id FROM pipeline_runs WHERE pipeline_id = ? ORDER BY id DESC LIMIT 50)", (pid, pid))
    state.audit("pipeline_run", f"{p['name']}: {'ok' if ok else 'failed'} ({trigger})", ok=ok)
    return {"id": pid, "name": p["name"], "ok": ok, "seconds": secs, "results": results}


def _shape(r: dict) -> dict:
    r["tasks"] = json.loads(r["tasks"])
    r["enabled"] = bool(r["enabled"])
    r["last_ok"] = None if r["last_ok"] is None else bool(r["last_ok"])
    return r


def list_pipelines() -> list[dict]:
    return [_shape(r) for r in state.rows("SELECT id, name, tasks, every_minutes, enabled, last_run_at, last_ok FROM pipelines WHERE workspace = ? ORDER BY id", (_ws(),))]


def get(pid: int) -> dict:
    r = state.one("SELECT id, name, tasks, every_minutes, enabled, last_run_at, last_ok FROM pipelines WHERE id = ? AND workspace = ?", (pid, _ws()))
    if not r:
        raise PipelineError("No such pipeline in this workspace.", 404)
    return _shape(r)


def save(name: str, tasks: list[dict], every_minutes: int = 0, enabled: bool = True, pid: int | None = None) -> dict:
    name = (name or "").strip()[:80]
    if not name:
        raise PipelineError("Give the pipeline a name.")
    if every_minutes and not 5 <= every_minutes <= 10080:
        raise PipelineError("A schedule must be between every 5 minutes and every 7 days (10080), or 0 for manual only.")
    clean = validate(tasks)
    if pid:
        get(pid)
        state.run("UPDATE pipelines SET name = ?, tasks = ?, every_minutes = ?, enabled = ? WHERE id = ?", (name, json.dumps(clean), every_minutes, 1 if enabled else 0, pid))
        return get(pid)
    if len(list_pipelines()) >= 30:
        raise PipelineError("You have 30 pipelines. Delete some first.")
    cur = state.run("INSERT INTO pipelines (workspace, name, tasks, every_minutes, enabled, created_at) VALUES (?,?,?,?,?,?)",
                    (_ws(), name, json.dumps(clean), every_minutes, 1 if enabled else 0, state.now()))
    return get(int(cur.lastrowid))


def delete(pid: int) -> None:
    get(pid)
    state.run("DELETE FROM pipeline_runs WHERE pipeline_id = ?", (pid,))
    state.run("DELETE FROM pipelines WHERE id = ?", (pid,))


def history(pid: int, limit: int = 20) -> list[dict]:
    get(pid)
    rows = state.rows("SELECT id, at, ok, seconds, trigger, detail FROM pipeline_runs WHERE pipeline_id = ? ORDER BY id DESC LIMIT ?", (pid, limit))
    for r in rows:
        r["detail"], r["ok"] = json.loads(r["detail"]), bool(r["ok"])
    return rows


def due() -> list[int]:
    out = []
    now = datetime.now(timezone.utc)
    for p in list_pipelines():
        if not p["enabled"] or not p["every_minutes"] or p["id"] in _running:
            continue
        if not p["last_run_at"]:
            out.append(p["id"])
            continue
        try:
            last = datetime.fromisoformat(p["last_run_at"].replace("Z", "+00:00"))
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
        except ValueError:
            out.append(p["id"])
            continue
        if now - last >= timedelta(minutes=p["every_minutes"]):
            out.append(p["id"])
    return out


def tick() -> list[str]:
    ran = []
    for pid in due():
        try:
            run(pid, trigger="schedule")
            ran.append(f"pipeline:{pid}")
        except Exception:  # noqa: BLE001
            pass
    return ran
