"""Computer engineering simulators and vehicle message decoders."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import cpe_sim as sim
from app.services import veh_decode as vd
from app.services.cpe_lab import CpeError

router = APIRouter(prefix="/api/cpesim", tags=["cpesim"])


def _w(fn, *a, **k):
    try:
        return fn(*a, **k)
    except CpeError as e:
        raise HTTPException(e.status, e.message) from e


class Logic(BaseModel):
    netlist: str = Field(max_length=4000)
    stimulus: str = Field(default="", max_length=2000)
    cycles: int = Field(default=8, ge=1, le=64)


class Cpu(BaseModel):
    source: str = Field(max_length=4000)
    max_steps: int = Field(default=500, ge=1, le=5000)


class Net(BaseModel):
    net: str = Field(max_length=4000)


class Tran(Net):
    t_end: float
    steps: int = Field(default=200, ge=2, le=1000)


class CacheT(BaseModel):
    trace: str = Field(max_length=6000)
    cache_bytes: int = 256
    block_bytes: int = 16
    ways: int = 2
    policy: str = "LRU"


class Can(BaseModel):
    data: str = Field(max_length=200)
    signals: str = Field(max_length=3000)


class J(BaseModel):
    can_id: str = Field(max_length=16)
    data: str = Field(default="", max_length=200)


class Code(BaseModel):
    code: str = Field(max_length=10)


class Pid(BaseModel):
    pid: str = Field(max_length=4)
    data: str = Field(max_length=60)


class Frames(BaseModel):
    frames: str = Field(max_length=4000)


class Num(BaseModel):
    value: float


@router.get("/reference")
def reference():
    return {"sim": sim.reference(), "vehicle": vd.reference(), "logic_samples": {k: {"netlist": v[0], "stimulus": v[1]} for k, v in sim.LOGIC_SAMPLES.items()},
            "cpu_samples": sim.CPU_SAMPLES, "net_samples": sim.NET_SAMPLES, "cache_sample": sim.CACHE_SAMPLE}


@router.post("/logic")
def logic(b: Logic):
    return _w(sim.logic_circuit, b.netlist, b.stimulus, b.cycles)


@router.post("/cpu")
def cpu(b: Cpu):
    return _w(sim.cpu_run, b.source, b.max_steps)


@router.post("/circuit-dc")
def dc(b: Net):
    return _w(sim.circuit_dc, b.net)


@router.post("/circuit-transient")
def tran(b: Tran):
    return _w(sim.circuit_transient, b.net, b.t_end, b.steps)


@router.post("/cache-trace")
def cache(b: CacheT):
    return _w(sim.cache_trace, b.trace, b.cache_bytes, b.block_bytes, b.ways, b.policy)


@router.post("/can-signals")
def can(b: Can):
    return _w(vd.can_signals, b.data, b.signals)


@router.post("/j1939")
def j1939(b: J):
    return _w(vd.j1939, b.can_id, b.data)


@router.post("/dtc")
def dtc(b: Code):
    return _w(vd.dtc, b.code)


@router.post("/obd-pid")
def pid(b: Pid):
    return _w(vd.obd_pid, b.pid, b.data)


@router.post("/isotp")
def isotp(b: Frames):
    return _w(vd.isotp, b.frames)


@router.post("/cp-duty")
def cpd(b: Num):
    return _w(vd.cp_duty, b.value)


@router.post("/cp-state")
def cps(b: Num):
    return _w(vd.cp_state, b.value)


@router.post("/pp-resistor")
def ppr(b: Num):
    return _w(vd.pp_resistor, b.value)
