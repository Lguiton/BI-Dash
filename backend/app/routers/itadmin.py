"""IT admin lab: email authentication checker, onboarding runbooks, script reviewer, ITIL helpers, stop codes."""
from fastapi import APIRouter, Body, HTTPException

from app.services import it_admin as ia

router = APIRouter(prefix="/api/itadmin", tags=["itadmin"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except ia.AdminError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/reference")
def reference():
    return ia.reference()


@router.post("/email-auth")
def email_auth(b: dict = Body(...)):
    return _g(ia.email_auth, str(b.get("domain") or ""), str(b.get("spf") or ""), str(b.get("dmarc") or ""), str(b.get("dkim") or ""))


@router.post("/lifecycle")
def lifecycle(b: dict = Body(...)):
    return _g(ia.lifecycle, str(b.get("kind") or ""), str(b.get("name") or ""), str(b.get("role") or ""), str(b.get("platform") or "m365"), str(b.get("extras") or ""))


@router.post("/script-review")
def script_review(b: dict = Body(...)):
    return _g(ia.review_script, str(b.get("text") or ""))


@router.post("/priority")
def priority(b: dict = Body(...)):
    return _g(ia.priority, str(b.get("impact") or ""), str(b.get("urgency") or ""))


@router.post("/sla")
def sla(b: dict = Body(...)):
    return _g(ia.sla, b.get("available_pct"), b.get("window_days", 30))


@router.post("/stop-code")
def stop_code(b: dict = Body(...)):
    return _g(ia.stop_code, str(b.get("code") or ""))
