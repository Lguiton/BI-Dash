"""IT Specialist track endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import itlab

router = APIRouter(prefix="/api/it", tags=["it"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except itlab.ItError as e:
        raise HTTPException(e.status, e.message) from e


class TicketIn(BaseModel):
    title: str = Field(max_length=140)
    category: str = Field(max_length=20)
    priority: str = Field("medium", max_length=10)
    requester: str = Field("", max_length=80)
    note: str = Field("", max_length=300)


class TicketPatch(BaseModel):
    status: str | None = Field(None, max_length=20)
    priority: str | None = Field(None, max_length=10)
    note: str | None = Field(None, max_length=500)
    tick: dict | None = None


class AssetIn(BaseModel):
    hostname: str = Field(max_length=80)
    kind: str = Field(max_length=20)
    os: str = Field("", max_length=60)
    owner: str = Field("", max_length=60)
    serial: str = Field("", max_length=60)
    purchased: str = Field("", max_length=10)
    warranty_end: str = Field("", max_length=10)
    status: str = Field("in_use", max_length=20)
    notes: str = Field("", max_length=300)


class AssetPatch(BaseModel):
    os: str | None = Field(None, max_length=60)
    owner: str | None = Field(None, max_length=60)
    serial: str | None = Field(None, max_length=60)
    purchased: str | None = Field(None, max_length=10)
    warranty_end: str | None = Field(None, max_length=10)
    status: str | None = Field(None, max_length=20)
    notes: str | None = Field(None, max_length=300)


class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=400_000)


class TickIn(BaseModel):
    index: int | None = None
    done: bool = True
    reset: bool = False


class CapacityIn(BaseModel):
    used_gb: float
    total_gb: float
    growth_gb_per_month: float
    warn_pct: float = 80.0


class AvailIn(BaseModel):
    pct: float


class RaidIn(BaseModel):
    level: str = Field(max_length=6)
    disks: int
    size_tb: float


@router.get("/tickets")
def tickets():
    return itlab.tickets()


@router.post("/tickets")
def ticket_open(b: TicketIn):
    return _g(itlab.open_ticket, b.title, b.category, b.priority, b.requester, b.note)


@router.patch("/tickets/{tid}")
def ticket_update(tid: int, b: TicketPatch):
    return _g(itlab.update_ticket, tid, b.status, b.note, b.tick, b.priority)


@router.delete("/tickets/{tid}")
def ticket_delete(tid: int):
    _g(itlab.delete_ticket, tid)
    return {"deleted": tid}


@router.get("/assets")
def assets():
    return itlab.assets()


@router.post("/assets")
def asset_add(b: AssetIn):
    return _g(itlab.add_asset, b.hostname, b.kind, b.os, b.owner, b.serial, b.purchased, b.warranty_end, b.status, b.notes)


@router.patch("/assets/{aid}")
def asset_update(aid: int, b: AssetPatch):
    return _g(itlab.update_asset, aid, b.model_dump(exclude_none=True))


@router.delete("/assets/{aid}")
def asset_delete(aid: int):
    _g(itlab.delete_asset, aid)
    return {"deleted": aid}


@router.get("/events/sample")
def events_sample():
    return {"text": itlab.SAMPLE_EVENTS, "note": "Made-up Windows event rows using documentation-range addresses."}


@router.post("/events/read")
def events_read(b: TextIn):
    return _g(itlab.read_events, b.text)


@router.get("/checklists")
def checklists():
    return itlab.checklists()


@router.post("/checklists/{lid}")
def checklist_tick(lid: str, b: TickIn):
    return _g(itlab.tick_checklist, lid, b.index, b.done, b.reset)


@router.post("/capacity")
def capacity(b: CapacityIn):
    return _g(itlab.capacity, b.used_gb, b.total_gb, b.growth_gb_per_month, b.warn_pct)


@router.post("/availability")
def availability(b: AvailIn):
    return _g(itlab.availability, b.pct)


@router.post("/raid")
def raid(b: RaidIn):
    return _g(itlab.raid, b.level, b.disks, b.size_tb)


@router.get("/cheats")
def cheats():
    return itlab.cheats()
