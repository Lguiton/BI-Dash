"""Data issue queue: anyone using the data (analyst, scientist, BI) can flag a problem; the data engineer works the queue.

Stored per workspace in the app's state file. It is a plain list with a status, not a ticketing system.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.services import state, workspaces

ROLES = ("analyst", "scientist", "bi", "engineer", "other")
SEVERITY = ("low", "medium", "high")
STATUS = ("open", "in_progress", "fixed", "wont_fix")
MAX_ITEMS = 300


class IssueError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _key() -> str:
    return f"data_issues:{workspaces.active()}"


def _load() -> list[dict]:
    try:
        return json.loads(state.kv_get(_key()) or "[]")
    except ValueError:
        return []


def _save(items: list[dict]) -> None:
    state.kv_set(_key(), json.dumps(items[-MAX_ITEMS:]))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def _clean(v, n: int) -> str:
    return " ".join(str(v or "").split())[:n]


def validate(data: dict) -> dict:
    """Check and clean a new issue without saving it."""
    summary = _clean(data.get("summary"), 300)
    if len(summary) < 5:
        raise IssueError("Describe the problem in a sentence (at least 5 characters).")
    role = data.get("role") or "other"
    sev = data.get("severity") or "medium"
    if role not in ROLES:
        raise IssueError(f"role must be one of {', '.join(ROLES)}.")
    if sev not in SEVERITY:
        raise IssueError(f"severity must be one of {', '.join(SEVERITY)}.")
    table = _clean(data.get("table"), 80)
    column = _clean(data.get("column"), 80)
    if table:
        from app.services import governance
        known = {a["name"]: a for a in governance.catalog()["assets"] if not a["system"]}
        if table not in known:
            raise IssueError(f"'{table}' isn't one of your tables.", 404)
        if column and column not in {c["name"] for c in known[table]["columns"]}:
            raise IssueError(f"'{column}' isn't a column of {table}.", 404)
    elif column:
        raise IssueError("Name the table the column belongs to.")
    return {"role": role, "severity": sev, "table": table, "column": column, "summary": summary, "expected": _clean(data.get("expected"), 300)}


def create(data: dict) -> dict:
    item = {"id": uuid.uuid4().hex[:10], **validate(data), "status": "open", "reply": "", "created": _now(), "updated": _now()}
    items = _load()
    items.append(item)
    _save(items)
    state.audit("data_issue", f"{item['role']}: {item['table'] or 'general'} {item['summary'][:80]}")
    return item


def update(iid: str, data: dict) -> dict:
    items = _load()
    it = next((i for i in items if i["id"] == iid), None)
    if not it:
        raise IssueError("No such issue.", 404)
    if "status" in data:
        if data["status"] not in STATUS:
            raise IssueError(f"status must be one of {', '.join(STATUS)}.")
        it["status"] = data["status"]
    if "reply" in data:
        it["reply"] = _clean(data["reply"], 500)
    if "severity" in data:
        if data["severity"] not in SEVERITY:
            raise IssueError(f"severity must be one of {', '.join(SEVERITY)}.")
        it["severity"] = data["severity"]
    it["updated"] = _now()
    _save(items)
    return it


def delete(iid: str) -> None:
    items = _load()
    if not any(i["id"] == iid for i in items):
        raise IssueError("No such issue.", 404)
    _save([i for i in items if i["id"] != iid])


def listing(status: str | None = None) -> dict:
    items = _load()
    rank = {"high": 0, "medium": 1, "low": 2}
    shown = [i for i in items if not status or i["status"] == status]
    shown.sort(key=lambda i: (i["status"] in ("fixed", "wont_fix"), rank[i["severity"]], i["created"]))
    return {"issues": shown, "open": sum(1 for i in items if i["status"] in ("open", "in_progress")), "total": len(items),
            "roles": ROLES, "severities": SEVERITY, "statuses": STATUS}
