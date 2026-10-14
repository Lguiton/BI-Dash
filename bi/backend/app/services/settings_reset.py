"""Reset the app's own settings to their defaults, with a snapshot taken first so the reset can be undone.

Only settings are touched (AI access, blocked columns, backup options, alert and report options and similar). Your data,
backups, study progress, tickets and the activity log are left alone."""
from __future__ import annotations

import json

from app.services import state, workspaces

KEEP = 5
KEY = "settings_snapshots"


class ResetError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _load() -> list[dict]:
    raw = state.kv_get(KEY)
    return json.loads(raw) if raw else []


def _save(snaps: list[dict]) -> None:
    state.kv_set(KEY, json.dumps(snaps[:KEEP]))


def snapshot(label: str) -> dict:
    rows = state.rows("SELECT workspace, key, value FROM settings")
    snaps = _load()
    nid = (max((s["id"] for s in snaps), default=0)) + 1
    s = {"id": nid, "at": state.now(), "label": label, "rows": rows}
    _save([s] + snaps)
    return {"id": nid, "at": s["at"], "label": label, "count": len(rows)}


def snapshots() -> list[dict]:
    return [{"id": s["id"], "at": s["at"], "label": s["label"], "count": len(s["rows"])} for s in _load()]


def current() -> dict:
    out = {}
    for w in workspaces.NAMES:
        out[w] = workspaces.settings(w)
    return {"settings": out, "custom_rows": len(state.rows("SELECT 1 FROM settings"))}


def reset(scope: str) -> dict:
    if scope not in (*workspaces.NAMES, "all"):
        raise ResetError("Scope must be practice, real or all.")
    snap = snapshot(f"before reset ({scope})")
    if scope == "all":
        n = state.run("DELETE FROM settings").rowcount
    else:
        n = state.run("DELETE FROM settings WHERE workspace = ?", (scope,)).rowcount
    state.audit("settings_reset", f"scope={scope}, removed {n} saved setting(s); snapshot #{snap['id']}")
    return {"reset": scope, "removed": n, "snapshot": snap, "settings": current()["settings"]}


def restore(snap_id: int) -> dict:
    snaps = _load()
    target = next((s for s in snaps if s["id"] == snap_id), None)
    if not target:
        raise ResetError("That snapshot no longer exists.", 404)
    before = snapshot(f"before restoring #{snap_id}")
    state.run("DELETE FROM settings")
    for r in target["rows"]:
        state.run("INSERT INTO settings (workspace, key, value) VALUES (?, ?, ?)", (r["workspace"], r["key"], r["value"]))
    state.audit("settings_restore", f"restored snapshot #{snap_id}; the state before is #{before['id']}")
    return {"restored": snap_id, "snapshot_before": before, "settings": current()["settings"]}
