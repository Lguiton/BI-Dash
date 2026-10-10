"""Network Engineer track endpoints."""
import threading
import time
from collections import deque

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import netlab

router = APIRouter(prefix="/api/net", tags=["network"])
_hits: deque[float] = deque()
_lock = threading.Lock()


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except netlab.NetError as e:
        raise HTTPException(e.status, e.message) from e


def _limit():
    """DNS and reachability checks talk to other computers: 12 a minute."""
    now = time.time()
    with _lock:
        while _hits and now - _hits[0] > 60:
            _hits.popleft()
        if len(_hits) >= 12:
            raise HTTPException(429, "That's a lot of network checks in a minute. Wait a little and try again.")
        _hits.append(now)


class CidrIn(BaseModel):
    cidr: str = Field(max_length=60)


class SplitIn(CidrIn):
    new_prefix: int = Field(ge=1, le=128)


class VlsmIn(BaseModel):
    base: str = Field(max_length=60)
    needs: list[dict] = Field(min_length=1, max_length=50)


class ContainsIn(CidrIn):
    ip: str = Field(max_length=60)


class ListIn(BaseModel):
    cidrs: list[str] = Field(min_length=1, max_length=200)


class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=netlab.MAX_TEXT)


class HostIn(BaseModel):
    host: str = Field(max_length=253)


class TcpIn(HostIn):
    port: int = Field(ge=1, le=65535)


class TransferIn(BaseModel):
    size_gb: float
    mbps: float
    efficiency_pct: float = 85.0


class BdpIn(BaseModel):
    mbps: float
    rtt_ms: float
    window_kb: float = 64.0


@router.post("/subnet")
def subnet(b: CidrIn):
    return _g(netlab.subnet, b.cidr)


@router.post("/split")
def split(b: SplitIn):
    return _g(netlab.split, b.cidr, b.new_prefix)


@router.post("/vlsm")
def vlsm(b: VlsmIn):
    return _g(netlab.vlsm, b.base, b.needs)


@router.post("/contains")
def contains(b: ContainsIn):
    return _g(netlab.contains, b.cidr, b.ip)


@router.post("/overlaps")
def overlaps(b: ListIn):
    return _g(netlab.overlaps, b.cidrs)


@router.post("/summarize")
def summarize(b: ListIn):
    return _g(netlab.summarize, b.cidrs)


@router.get("/config/sample")
def config_sample():
    return {"text": netlab.SAMPLE_CONFIG, "note": "A made-up switch config with deliberate mistakes. Addresses are from the documentation ranges."}


@router.post("/config/audit")
def config_audit(b: TextIn):
    return _g(netlab.audit_config, b.text)


@router.get("/capture/sample")
def capture_sample():
    return {"text": netlab.SAMPLE_CAPTURE, "note": "Made-up tcpdump -nn lines using documentation-range addresses."}


@router.post("/capture/read")
def capture_read(b: TextIn):
    return _g(netlab.read_capture, b.text)


@router.post("/dns")
def dns(b: HostIn):
    _limit()
    return _g(netlab.dns_lookup, b.host)


@router.post("/tcp")
def tcp(b: TcpIn):
    _limit()
    return _g(netlab.tcp_check, b.host, b.port)


@router.post("/transfer")
def transfer(b: TransferIn):
    return _g(netlab.transfer_time, b.size_gb, b.mbps, b.efficiency_pct)


@router.post("/bdp")
def bdp(b: BdpIn):
    return _g(netlab.bdp, b.mbps, b.rtt_ms, b.window_kb)


@router.get("/reference")
def reference():
    return netlab.reference()
