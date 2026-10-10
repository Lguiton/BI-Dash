"""Safe actions the command palette (Ctrl+K) can run. Each one is something the app already does elsewhere, none deletes or
overwrites data, and each needs an explicit confirm from the caller. Every run is written to the audit log."""
from __future__ import annotations

from app.services import alerts, backups, expectations, sources, state, workspaces


class ActionError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _quality() -> str:
    tables = sorted({r["table"] for r in expectations.list_rules()})
    if not tables:
        raise ActionError("There are no quality rules yet. Add some on the Data quality page first.", 409)
    bad = 0
    for t in tables:
        bad += expectations.run(t, trigger="palette")["failed"]
    return f"Ran rules on {len(tables)} table(s); {bad} rule(s) failed." if bad else f"Ran rules on {len(tables)} table(s); all passed."


def _backup() -> str:
    b = backups.create("palette")
    return f"Backup saved: {b.get('name', 'ok')}"


def _refresh() -> str:
    items = [s for s in sources.list_sources() if s["enabled"]]
    if not items:
        raise ActionError("There are no enabled sources to refresh.", 409)
    ok = failed = 0
    for s in items:
        try:
            sources.run_source(s["id"])
            ok += 1
        except Exception:  # noqa: BLE001
            failed += 1
    return f"Refreshed {ok} source(s)" + (f"; {failed} failed (see Sources)." if failed else ".")


def _alerts() -> str:
    r = alerts.check(send=False)
    n = len(r["alerts"]) if isinstance(r, dict) and "alerts" in r else len(r)
    return f"{n} alert(s) right now." if n else "No alerts right now."


ACTIONS = {
    "run_quality": ("Run all data-quality rules", "Runs every saved rule and records the result. Changes no data.", _quality),
    "backup": ("Take a backup now", "Copies the current database into the backups folder.", _backup),
    "refresh_sources": ("Refresh all data sources", "Re-pulls every enabled source using its saved settings (a replace still refuses to shrink a table badly).", _refresh),
    "check_alerts": ("Check alerts now", "Looks at your data and lists anything needing attention. Sends nothing.", _alerts),
}


def catalog() -> list[dict]:
    return [{"id": k, "label": v[0], "detail": v[1]} for k, v in ACTIONS.items()]


def run(aid: str, confirm: bool) -> dict:
    if aid not in ACTIONS:
        raise ActionError("Unknown action.", 404)
    if not confirm:
        raise ActionError("Confirm first: this action needs confirm=true.", 400)
    try:
        msg = ACTIONS[aid][2]()
    except ActionError as e:
        state.audit("palette_action", f"{aid}: {e.message}", ok=False)
        raise
    except Exception as e:  # noqa: BLE001
        state.audit("palette_action", f"{aid}: {type(e).__name__}", ok=False)
        raise ActionError(f"That didn't work: {getattr(e, 'message', None) or type(e).__name__}.", 422) from None
    state.audit("palette_action", f"{aid} ({workspaces.active()}): {msg}")
    return {"ok": True, "message": msg}
