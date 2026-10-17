"""PC build lab: compatibility, power supply sizing, build checklist, no-POST diagnostic."""
from fastapi import APIRouter, Body, HTTPException

from app.services import pc_build as pb

router = APIRouter(prefix="/api/pcbuild", tags=["pcbuild"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except pb.PcError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/options")
def options():
    return pb.options()


@router.post("/check")
def check(b: dict = Body(...)):
    return _g(pb.check, b)


@router.post("/psu")
def psu(b: dict = Body(...)):
    def go():
        return pb.recommend_psu(b.get("cpu_w"), b.get("gpu_w"), int(b.get("ssd") or 0), int(b.get("hdd") or 0), int(b.get("fans") or 0), int(b.get("sticks") or 2))
    return _g(go)


@router.get("/checklist")
def checklist():
    return pb.checklist()


@router.post("/diagnose")
def diagnose(b: dict = Body(...)):
    return _g(pb.diagnose, str(b.get("symptom") or ""))
