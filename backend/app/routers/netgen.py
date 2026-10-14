"""Network config generators and checkers."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import net_gen as g

router = APIRouter(prefix="/api/netgen", tags=["netgen"])


def _w(fn, *a, **k):
    try:
        return fn(*a, **k)
    except g.GenError as e:
        raise HTTPException(e.status, e.message) from e


class VlanIn(BaseModel):
    id: int | str
    name: str = Field(max_length=40)
    subnet: str = Field(max_length=50)
    gateway: str | None = Field(None, max_length=45)
    ports: list[str] = Field(default_factory=list, max_length=48)


class PlanIn(BaseModel):
    vlans: list[VlanIn] = Field(max_length=20)
    trunk_port: str = Field("g0/1", max_length=20)
    router_port: str = Field("g0/0", max_length=20)
    native: int = 1
    allowed: list[int] | None = Field(None, max_length=200)
    style: str = Field("roas", max_length=6)
    encapsulation_line: bool = False
    loopback: str | None = Field(None, max_length=45)
    router_name: str = Field("R1", pattern=r"^[A-Za-z0-9_-]{1,20}$")
    switch_name: str = Field("S1", pattern=r"^[A-Za-z0-9_-]{1,20}$")


@router.post("/plan")
def plan(b: PlanIn):
    d = b.model_dump()
    return _w(g.vlan_plan, d.pop("vlans"), **d)


class TrunkIn(BaseModel):
    a: str = Field(max_length=200_000)
    b: str = Field(max_length=200_000)
    iface_a: str = Field("", max_length=30)
    iface_b: str = Field("", max_length=30)


@router.post("/trunk")
def trunk(b: TrunkIn):
    return _w(g.trunk_check, b.a, b.b, b.iface_a, b.iface_b)


class RouteIn(BaseModel):
    routes: list[dict] = Field(max_length=40)
    destination: str = Field(max_length=45)


@router.post("/route")
def route(b: RouteIn):
    return _w(g.route_select, b.routes, b.destination)


class CableIn(BaseModel):
    speed_gbps: float
    distance_m: float
    emi: bool = False


@router.post("/cable")
def cable(b: CableIn):
    return _w(g.cable_pick, b.speed_gbps, b.distance_m, b.emi)


@router.get("/reference")
def reference():
    return g.reference()
