"""Computer engineering and vehicle electronics endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import auto_elec as ae
from app.services import cpe_lab as cl

router = APIRouter(prefix="/api/cpe", tags=["cpe"])


def _w(fn, *a, **k):
    try:
        return fn(*a, **k)
    except cl.CpeError as e:
        raise HTTPException(e.status, e.message) from e


class Conv(BaseModel):
    text: str = Field(max_length=80)
    base: int = 10
    bits: int = 8


class Add(BaseModel):
    a: int
    b: int
    bits: int = 8
    subtract: bool = False


class Flt(BaseModel):
    value: float
    double: bool = False


class Expr(BaseModel):
    text: str = Field(max_length=300)


class Pair(BaseModel):
    a: str = Field(max_length=300)
    b: str = Field(max_length=300)


class OhmIn(BaseModel):
    v: float | None = None
    i: float | None = None
    r: float | None = None
    p: float | None = None


class Res(BaseModel):
    kind: str
    values: list[float]


class Div(BaseModel):
    vin: float
    r1: float
    r2: float
    load: float | None = None


class Led(BaseModel):
    supply: float
    forward: float
    current_ma: float


class RC(BaseModel):
    r: float
    c_uf: float
    v: float = 12


class Color(BaseModel):
    b1: str
    b2: str
    mult: str
    tol: str = "gold"


class Amat(BaseModel):
    hit_time: float
    miss_rate_pct: float
    miss_penalty: float


class Cache(BaseModel):
    address_bits: int
    cache_bytes: int
    block_bytes: int
    ways: int = 1


class Cpu(BaseModel):
    instructions: float
    cpi: float
    clock_ghz: float


class Amd(BaseModel):
    parallel_pct: float
    speedup_part: float


class Pipe(BaseModel):
    stages: int
    instructions: int
    stall_cycles: float = 0


class Raid(BaseModel):
    level: int
    disks: int
    size_tb: float


class Wire(BaseModel):
    load_a: float
    length_m: float
    volts: float = 12
    max_drop_pct: float = 3
    round_trip: bool = True
    continuous: bool = True


class Text(BaseModel):
    text: str = Field(max_length=20_000)


class Can(BaseModel):
    bitrate_kbps: float
    frames: list[dict]


class Term(BaseModel):
    measured_ohm: float


class Charge(BaseModel):
    capacity_kwh: float
    start_pct: float
    target_pct: float
    source: str
    volts: float = 230
    amps: float = 32
    phases: int = 1
    station_kw: float = 50
    vehicle_max_kw: float = 100
    onboard_kw: float = 11
    taper_after_pct: float = 80
    taper_factor: float = 0.4


class Pack(BaseModel):
    series: int
    parallel: int
    cell_v: float = 3.7
    cell_ah: float = 5.0
    cell_kg: float | None = None


class Pre(BaseModel):
    bus_v: float
    cap_uf: float
    resistor_ohm: float


class Iso(BaseModel):
    bus_v: float
    measured_kohm: float


@router.get("/reference")
def reference():
    return {"lab": cl.reference(), "auto": ae.reference()}


@router.post("/convert")
def convert(b: Conv):
    return _w(cl.convert, b.text, b.base, b.bits)


@router.post("/signed-add")
def signed_add(b: Add):
    return _w(cl.signed_add, b.a, b.b, b.bits, b.subtract)


@router.post("/float")
def flt(b: Flt):
    return _w(cl.ieee754, b.value, b.double)


@router.post("/logic")
def logic(b: Expr):
    return _w(cl.logic, b.text)


@router.post("/equivalent")
def equivalent(b: Pair):
    return _w(cl.equivalent, b.a, b.b)


@router.post("/ohm")
def ohm(b: OhmIn):
    return _w(cl.ohm, b.v, b.i, b.r, b.p)


@router.post("/resistors")
def resistors(b: Res):
    return _w(cl.resistors, b.kind, b.values)


@router.post("/divider")
def divider(b: Div):
    return _w(cl.divider, b.vin, b.r1, b.r2, b.load)


@router.post("/led")
def led(b: Led):
    return _w(cl.led_resistor, b.supply, b.forward, b.current_ma)


@router.post("/rc")
def rc(b: RC):
    return _w(cl.rc_time, b.r, b.c_uf, b.v)


@router.post("/color-code")
def color(b: Color):
    return _w(cl.color_code, b.b1, b.b2, b.mult, b.tol)


@router.post("/amat")
def amat(b: Amat):
    return _w(cl.amat, b.hit_time, b.miss_rate_pct, b.miss_penalty)


@router.post("/cache")
def cache(b: Cache):
    return _w(cl.cache_split, b.address_bits, b.cache_bytes, b.block_bytes, b.ways)


@router.post("/cpu-time")
def cpu(b: Cpu):
    return _w(cl.cpu_time, b.instructions, b.cpi, b.clock_ghz)


@router.post("/amdahl")
def amdahl(b: Amd):
    return _w(cl.amdahl, b.parallel_pct, b.speedup_part)


@router.post("/pipeline")
def pipeline(b: Pipe):
    return _w(cl.pipeline, b.stages, b.instructions, b.stall_cycles)


@router.post("/raid")
def raid(b: Raid):
    return _w(cl.raid, b.level, b.disks, b.size_tb)


@router.post("/wire")
def wire(b: Wire):
    return _w(ae.wire, b.load_a, b.length_m, b.volts, b.max_drop_pct, b.round_trip, b.continuous)


@router.post("/harness")
def harness(b: Text):
    return _w(ae.harness_check, b.text)


@router.post("/can-load")
def can_load(b: Can):
    return _w(ae.can_load, b.bitrate_kbps, b.frames)


@router.post("/can-termination")
def can_term(b: Term):
    return _w(ae.can_termination, b.measured_ohm)


@router.post("/ev-charge")
def ev_charge(b: Charge):
    return _w(ae.charge, **b.model_dump())


@router.post("/ev-pack")
def ev_pack(b: Pack):
    return _w(ae.pack, b.series, b.parallel, b.cell_v, b.cell_ah, b.cell_kg)


@router.post("/precharge")
def pre(b: Pre):
    return _w(ae.precharge, b.bus_v, b.cap_uf, b.resistor_ohm)


@router.post("/isolation")
def iso(b: Iso):
    return _w(ae.isolation, b.bus_v, b.measured_kohm)
