from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import HTMLResponse

from app.services import sec_report, sec_tracker as st

router = APIRouter(prefix="/api/sectrack", tags=["sectrack"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except (st.TrackError, sec_report.ReportError) as e:
        raise HTTPException(e.status, e.message) from None


@router.post("/reports/save")
def save_report(body: dict = Body(...)):
    """Build a checkup report from the same inputs as /api/security/report and keep a snapshot for this client (no network checks are run unless hosts are given)."""
    try:
        rep = sec_report.build(body.get("client", ""), body.get("prepared_by", ""), body.get("scope", ""), body.get("endpoints") or [], [h for h in (body.get("hosts") or []) if str(h).strip()][:5], str(body.get("logs") or "")[:5_000_000], body.get("checklist") or {})
    except sec_report.ReportError as e:
        raise HTTPException(e.status, e.message) from None
    return _g(st.save_report, body.get("client_id"), rep)


@router.get("/{cid}/reports")
def history(cid: int):
    return {"reports": st.history(cid)}


@router.get("/{cid}/compare")
def compare(cid: int, a: int | None = None, b: int | None = None):
    return _g(st.compare, cid, a, b)


@router.get("/{cid}/backups/status")
def backup_status(cid: int):
    return st.backup_status(cid)


@router.get("/{cid}/accounts/review")
def account_review(cid: int):
    return st.account_review(cid)


@router.get("/{cid}/devices/status")
def device_status(cid: int):
    return st.device_status(cid)


@router.get("/{cid}/timeline/html")
def timeline_html(cid: int, incident: str = ""):
    return HTMLResponse(_g(st.timeline_html, cid, incident), headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})


@router.get("/{kind}/list/{cid}")
def list_rows(kind: str, cid: int):
    if kind not in st.COLL:
        raise HTTPException(404, "Unknown list.")
    return {"rows": st.rows(kind, cid)}


@router.post("/{kind}")
def add(kind: str, body: dict = Body(...)):
    if kind not in st.COLL:
        raise HTTPException(404, "Unknown list.")
    return _g(st.add, kind, body)


@router.put("/{kind}/{rid}")
def update(kind: str, rid: int, body: dict = Body(...)):
    if kind not in st.COLL:
        raise HTTPException(404, "Unknown list.")
    return _g(st.update, kind, rid, body)


@router.delete("/{kind}/{rid}")
def remove(kind: str, rid: int):
    if kind not in st.COLL:
        raise HTTPException(404, "Unknown list.")
    return _g(st.remove, kind, rid)
