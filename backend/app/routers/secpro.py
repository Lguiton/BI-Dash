"""Advanced security lab: CVSS, risk, scope template, forensic timeline, rule explainer, checklists."""
from fastapi import APIRouter, Body, HTTPException

from app.services import sec_pro as sp

router = APIRouter(prefix="/api/secpro", tags=["secpro"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except sp.SecError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/reference")
def reference():
    return sp.reference()


@router.post("/cvss")
def cvss(b: dict = Body(...)):
    return _g(sp.cvss, str(b.get("vector") or ""), **{k: b[k] for k in ("AV", "AC", "PR", "UI", "S", "C", "I", "A") if k in b})


@router.post("/ale")
def ale(b: dict = Body(...)):
    return _g(sp.ale, b.get("asset_value"), b.get("exposure_pct"), b.get("incidents_per_year"), b.get("control_cost_per_year", 0), b.get("risk_reduction_pct", 0))


@router.post("/risk")
def risk(b: dict = Body(...)):
    return _g(sp.risk_matrix, str(b.get("likelihood") or ""), str(b.get("impact") or ""))


@router.post("/scope")
def scope(b: dict = Body(default={})):
    return _g(sp.scope, str(b.get("client") or ""), str(b.get("systems") or ""), str(b.get("start") or ""), str(b.get("end") or ""), str(b.get("testing") or ""), str(b.get("exclusions") or ""))


@router.post("/timeline")
def timeline(b: dict = Body(...)):
    try:
        yr = int(b.get("year") or 2026)
    except (TypeError, ValueError):
        raise HTTPException(400, "Year must be a number.") from None
    return _g(sp.timeline, str(b.get("text") or ""), yr)


@router.post("/rule")
def rule(b: dict = Body(...)):
    return _g(sp.explain_rule, str(b.get("rule") or ""))


@router.get("/checklist/{kind}")
def checklist(kind: str):
    return _g(sp.checklist, kind)
