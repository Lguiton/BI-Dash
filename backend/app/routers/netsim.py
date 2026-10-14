"""Network protocol simulators and the saved-capture reader."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import net_pcap, net_sim
from app.services.netlab import NetError

router = APIRouter(prefix="/api/netsim", tags=["netsim"])


def _w(fn, *a, **k):
    try:
        return fn(*a, **k)
    except NetError as e:
        raise HTTPException(e.status, e.message) from e


class Sw(BaseModel):
    ports: str = Field(max_length=4000)
    frames: str = Field(max_length=20000)


class Stp(BaseModel):
    bridges: str = Field(max_length=4000)
    links: str = Field(max_length=8000)


class Spf(BaseModel):
    links: str = Field(max_length=8000)
    source: str = Field(max_length=60)


class Bgp(BaseModel):
    routes: str = Field(max_length=8000)


class Acl(BaseModel):
    rules: str = Field(max_length=8000)
    packets: str = Field(max_length=20000)


class Nat(BaseModel):
    inside: str = Field(max_length=60)
    public_ip: str = Field(max_length=60)
    flows: str = Field(max_length=20000)


class Pcap(BaseModel):
    data: str = Field(max_length=9_000_000)


@router.get("/reference")
def reference():
    return {**net_sim.reference(), "pcap_not_built": net_pcap.NOT_BUILT, "pcap_slips": net_pcap.SLIPS}


@router.post("/switch")
def switch(b: Sw):
    return _w(net_sim.switch, b.ports, b.frames)


@router.post("/stp")
def stp(b: Stp):
    return _w(net_sim.stp, b.bridges, b.links)


@router.post("/spf")
def spf(b: Spf):
    return _w(net_sim.spf, b.links, b.source)


@router.post("/bgp")
def bgp(b: Bgp):
    return _w(net_sim.bgp, b.routes)


@router.post("/acl")
def acl(b: Acl):
    return _w(net_sim.acl, b.rules, b.packets)


@router.post("/nat")
def nat(b: Nat):
    return _w(net_sim.nat, b.inside, b.public_ip, b.flows)


@router.post("/pcap")
def pcap(b: Pcap):
    return _w(net_pcap.read, b.data)
