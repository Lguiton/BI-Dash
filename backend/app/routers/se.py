"""Software engineering lab endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import se_lab as se

router = APIRouter(prefix="/api/se", tags=["software-engineering"])


def _w(fn, *a, **k):
    try:
        return fn(*a, **k)
    except se.SeError as e:
        raise HTTPException(400, str(e)) from e


class VerIn(BaseModel):
    a: str = Field(max_length=60)
    b: str = Field(max_length=60)


class BumpIn(BaseModel):
    version: str = Field(max_length=60)
    level: str = Field(max_length=10)


class SatIn(BaseModel):
    version: str = Field(max_length=60)
    spec: str = Field(max_length=80)


class StoryIn(BaseModel):
    text: str = Field(max_length=600)


class TraceIn(BaseModel):
    requirements: list[dict] = Field(max_length=60)
    tests: list[dict] = Field(max_length=60)


class MethodIn(BaseModel):
    req_change: str
    customer_access: str
    regulated: bool = False
    fixed_contract: bool = False
    cadence: str
    team_size: str


class RegIn(BaseModel):
    cases: list[dict] = Field(max_length=60)


class ArchIn(BaseModel):
    users: str
    team: str
    realtime_events: bool = False
    decentralized: bool = False
    independent_deploy: bool = False
    strong_consistency: bool = False


class TopoIn(BaseModel):
    web_servers: int = Field(2, ge=0, le=50)
    app_servers: int = Field(2, ge=0, le=50)
    db_replicas: int = Field(1, ge=0, le=50)
    load_balancer: bool = True
    firewall: bool = True
    proxy: bool = False
    part_availability_pct: float = Field(99.5, gt=0, le=100)


class StatesIn(BaseModel):
    states: list[str] = Field(max_length=30)
    transitions: list[dict] = Field(max_length=80)
    start: str
    finals: list[str] = Field(default_factory=list, max_length=30)


class ClassesIn(BaseModel):
    classes: list[dict] = Field(max_length=25)


class FlowIn(BaseModel):
    src: str = Field(max_length=6000)


@router.get("")
def reference():
    return se.reference()


@router.post("/version/compare")
def v_compare(b: VerIn):
    return _w(se.compare, b.a, b.b)


@router.post("/version/bump")
def v_bump(b: BumpIn):
    return _w(se.bump, b.version, b.level)


@router.post("/version/satisfies")
def v_sat(b: SatIn):
    return _w(se.satisfies, b.version, b.spec)


@router.post("/story")
def story(b: StoryIn):
    return _w(se.check_story, b.text)


@router.post("/traceability")
def trace(b: TraceIn):
    return _w(se.traceability, b.requirements, b.tests)


@router.post("/method")
def method(b: MethodIn):
    return _w(se.choose_method, b.req_change, b.customer_access, b.regulated, b.fixed_contract, b.cadence, b.team_size)


@router.post("/regression")
def regression(b: RegIn):
    return _w(se.prioritize_regression, b.cases)


@router.post("/architecture")
def architecture(b: ArchIn):
    return _w(se.recommend_architecture, b.users, b.team, b.realtime_events, b.decentralized, b.independent_deploy, b.strong_consistency)


@router.post("/topology")
def topology(b: TopoIn):
    return _w(se.topology, **b.model_dump())


@router.post("/states")
def states(b: StatesIn):
    return _w(se.check_states, b.states, b.transitions, b.start, b.finals)


@router.post("/classes")
def classes(b: ClassesIn):
    return _w(se.class_diagram, b.classes)


@router.post("/flow")
def flow(b: FlowIn):
    return _w(se.pseudocode_to_flow, b.src)
