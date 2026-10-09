"""Database administration and data governance endpoints (Data Engineering tab)."""
from fastapi import APIRouter, Body, HTTPException

from app.services import backups, dba, governance

router = APIRouter(tags=["dba-governance"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except (governance.GovError,) as e:
        raise HTTPException(e.status, e.message) from e
    except backups.BackupError as e:
        raise HTTPException(e.status, str(e)) from e


@router.get("/api/dba/health")
def health():
    return dba.health()


@router.get("/api/dba/benchmarks")
def benchmarks():
    return dba.benchmarks()


@router.post("/api/dba/checkpoint")
def checkpoint():
    return dba.checkpoint()


@router.post("/api/dba/verify-backup")
def verify(body: dict = Body(default={})):
    return _g(dba.verify_backup, body.get("name"))


@router.get("/api/governance/catalog")
def catalog():
    return governance.catalog()


@router.put("/api/governance/assets/{name}")
def asset(name: str, body: dict = Body(...)):
    return _g(governance.save_asset, name, body)


@router.get("/api/governance/pii-scan")
def pii():
    return governance.pii_scan()


@router.post("/api/governance/protect")
def protect(body: dict = Body(...)):
    return _g(governance.protect, list(body.get("columns") or []))


@router.get("/api/governance/lineage")
def lineage():
    return governance.lineage()


@router.get("/api/governance/controls")
def controls():
    return governance.controls()


@router.get("/api/governance/access")
def access():
    return governance.access_summary()
