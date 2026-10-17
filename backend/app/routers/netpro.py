"""Advanced networking lab: OSPF cost, spanning tree, IPv6 plan, EUI-64, PoE, fiber, Wi-Fi link budget, TCP limit, firewall review."""
from fastapi import APIRouter, Body, HTTPException

from app.services import net_pro as n

router = APIRouter(prefix="/api/netpro", tags=["netpro"])


@router.get("/reference")
def reference():
    return n.reference()


@router.post("/calc/{kind}")
def calc(kind: str, b: dict = Body(default={})):
    try:
        return n.calc(kind, b)
    except n.NetError as e:
        raise HTTPException(e.status, e.message) from None


@router.post("/firewall")
def firewall(b: dict = Body(...)):
    try:
        return n.firewall_review(str(b.get("text") or ""))
    except n.NetError as e:
        raise HTTPException(e.status, e.message) from None
