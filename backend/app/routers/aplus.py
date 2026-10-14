"""CompTIA A+ study area endpoints (inside the IT Specialist track)."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import aplus_lab as a

router = APIRouter(prefix="/api/aplus", tags=["aplus"])


def _w(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except a.AplusError as e:
        raise HTTPException(e.status, e.message) from e


class LevelIn(BaseModel):
    objective: str = Field(max_length=12)
    level: int


class GradeIn(BaseModel):
    answers: dict[str, int] = Field(max_length=100)


class IpIn(BaseModel):
    address: str = Field(max_length=60)
    mask: str = Field(default="", max_length=20)
    gateway: str = Field(default="", max_length=60)


class DhcpIn(BaseModel):
    network: str = Field(max_length=30)
    start: str = Field(max_length=20)
    end: str = Field(max_length=20)
    exclusions: list[str] = Field(default_factory=list, max_length=20)
    reservations: int = 0
    devices: int = 0
    lease_hours: float = 24


class TextIn(BaseModel):
    text: str = Field(max_length=200000)
    filename: str = Field(default="", max_length=80)


class DisplayIn(BaseModel):
    width_px: float
    height_px: float
    diagonal_in: float
    refresh_hz: float = 60


class PsuIn(BaseModel):
    cpu_w: float = 65
    gpu_w: float = 0
    drives: int = 1
    fans: int = 3
    ram_sticks: int = 2
    other_w: float = 20
    headroom_pct: float = 30


class BackupIn(BaseModel):
    full_gb: float
    daily_change_gb: float
    days: int = 28
    full_every_days: int = 7
    copies: int = 3
    media_types: int = 2
    offsite: int = 1


@router.get("")
def objectives():
    return a.objectives()


@router.post("/level")
def level(b: LevelIn):
    return _w(a.set_level, b.objective, b.level)


@router.get("/quiz")
def quiz(exam: str = Query("", max_length=1), domain: str = Query("", max_length=20), n: int = Query(10, ge=1, le=60), seed: int = 0):
    return _w(a.quiz, exam, domain, n, seed)


@router.post("/quiz/grade")
def grade(b: GradeIn):
    return _w(a.grade, b.answers)


@router.delete("/quiz/results")
def reset():
    return a.reset_results()


@router.get("/cards")
def cards(kind: str = Query("acronyms", max_length=10), n: int = Query(20, ge=1, le=100), exam: str = Query("", max_length=1), seed: int = 0):
    return _w(a.cards, kind, n, exam, seed)


@router.get("/symptoms")
def symptoms(q: str = Query("", max_length=80), exam: str = Query("", max_length=1)):
    return a.symptoms(q, exam)


@router.get("/reference")
def reference(topic: str = Query("", max_length=20)):
    return _w(a.reference, topic)


@router.post("/ip")
def ip(b: IpIn):
    return _w(a.ip_check, b.address, b.mask, b.gateway)


@router.post("/dhcp")
def dhcp(b: DhcpIn):
    return _w(a.dhcp_scope, b.network, b.start, b.end, b.exclusions, b.reservations, b.devices, b.lease_hours)


@router.post("/mail")
def mail(b: TextIn):
    return _w(a.mail_records, b.text)


@router.post("/display")
def display(b: DisplayIn):
    return _w(a.display_calc, b.width_px, b.height_px, b.diagonal_in, b.refresh_hz)


@router.post("/psu")
def psu(b: PsuIn):
    return _w(a.psu_size, b.cpu_w, b.gpu_w, b.drives, b.fans, b.ram_sticks, b.other_w, b.headroom_pct)


@router.post("/backup")
def backup(b: BackupIn):
    return _w(a.backup_plan, b.full_gb, b.daily_change_gb, b.days, b.full_every_days, b.copies, b.media_types, b.offsite)


@router.post("/script")
def script(b: TextIn):
    return _w(a.script_review, b.text, b.filename)
