"""Saved dashboard views: a name, the filters, and which sections of the main dashboard are shown and in what order.
Stored per workspace. The server only checks shape and size; the dashboard decides what the section ids mean."""
from __future__ import annotations

import json
import re
import uuid

from app.services import state, workspaces

MAX_VIEWS = 30
FILTER_KEYS = ("date_from", "date_to", "entity_id", "category", "status")
ID_RE = re.compile(r"^[a-z0-9_-]{1,40}$")


class ViewError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _key() -> str:
    return f"views:{workspaces.active()}"


def _load() -> list[dict]:
    try:
        v = json.loads(state.kv_get(_key(), "[]") or "[]")
        return v if isinstance(v, list) else []
    except ValueError:
        return []


def list_views() -> list[dict]:
    return _load()


def _ids(v, what: str) -> list[str]:
    if v is None:
        return []
    if not isinstance(v, list) or len(v) > 40 or any(not isinstance(i, str) or not ID_RE.match(i) for i in v):
        raise ViewError(f"{what} must be a short list of section ids.")
    return list(dict.fromkeys(v))


def save(name: str, filters: dict | None, hidden=None, order=None, vid: str | None = None) -> dict:
    name = (name or "").strip()
    if not name or len(name) > 40:
        raise ViewError("Give the view a name of 1 to 40 characters.")
    filters = filters or {}
    if not isinstance(filters, dict):
        raise ViewError("filters must be an object.")
    clean = {}
    for k, v in filters.items():
        if k not in FILTER_KEYS:
            raise ViewError(f"Unknown filter '{k}'.")
        if v not in (None, ""):
            if not isinstance(v, str) or len(v) > 60:
                raise ViewError(f"Filter '{k}' must be short text.")
            clean[k] = v
    views = _load()
    item = {"id": vid or uuid.uuid4().hex[:8], "name": name, "filters": clean, "hidden": _ids(hidden, "hidden"), "order": _ids(order, "order")}
    if vid:
        if not any(v["id"] == vid for v in views):
            raise ViewError("No such view.", 404)
        views = [item if v["id"] == vid else v for v in views]
    else:
        if len(views) >= MAX_VIEWS:
            raise ViewError(f"Limit of {MAX_VIEWS} views reached. Delete one first.")
        if any(v["name"].lower() == name.lower() for v in views):
            raise ViewError("A view with that name already exists.", 409)
        views.append(item)
    state.kv_set(_key(), json.dumps(views))
    state.audit("view_save", name)
    return item


def delete(vid: str) -> None:
    views = _load()
    if not any(v["id"] == vid for v in views):
        raise ViewError("No such view.", 404)
    state.kv_set(_key(), json.dumps([v for v in views if v["id"] != vid]))
    state.audit("view_delete", vid)
