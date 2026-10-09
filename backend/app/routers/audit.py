"""Read-only activity log."""
from fastapi import APIRouter, Query

from app.services import state

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
def recent(limit: int = Query(100, ge=1, le=500), workspace: str | None = None, action: str | None = None):
    where, params = [], []
    if workspace in ("practice", "real"):
        where.append("workspace = ?"); params.append(workspace)
    if action:
        where.append("action = ?"); params.append(action)
    sql = "SELECT id, at, workspace, action, detail, ok FROM audit" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY id DESC LIMIT ?"
    rows = state.rows(sql, (*params, limit))
    actions = [r["action"] for r in state.rows("SELECT DISTINCT action FROM audit ORDER BY action")]
    return {"entries": [{**r, "ok": bool(r["ok"])} for r in rows], "actions": actions}
