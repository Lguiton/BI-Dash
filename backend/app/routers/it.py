"""IT Specialist track endpoints."""
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.services import it_software, itlab, virt_lab

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


@router.post("/events/upload")
async def events_upload(file: UploadFile = File(...)):
    raw = await file.read(itlab.MAX_EVENT_BYTES + 1)
    if len(raw) > itlab.MAX_EVENT_BYTES:
        raise HTTPException(413, f"That file is over {itlab.MAX_EVENT_BYTES // (1024 * 1024)} MB. Export a smaller slice.")
    text = itlab.decode_export(raw)
    return _g(itlab.read_events, text, itlab.MAX_EVENT_BYTES * 2)


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


@router.get("/repair")
def repair():
    from app.services import it_repair
    return it_repair.sheet()


@router.get("/shortcuts")
def shortcuts():
    from app.services import it_shortcuts
    return it_shortcuts.sheet()


@router.get("/cheats")
def cheats():
    return itlab.cheats()


# ---------------------------------------------------------------- software guide
def _sw(fn, *a, **k):
    try:
        return fn(*a, **k)
    except it_software.SoftError as e:
        raise HTTPException(e.status, e.message) from e


class ShortlistIn(BaseModel):
    category: str = Field(max_length=20)
    weights: dict[str, float] | None = None
    exclude: list[str] = Field(default_factory=list, max_length=40)


class StackIn(BaseModel):
    items: list[dict] = Field(max_length=20)


@router.get("/software")
def software_catalog():
    return it_software.catalog()


@router.post("/software/shortlist")
def software_shortlist(body: ShortlistIn):
    return _sw(it_software.shortlist, body.category, body.weights, body.exclude)


@router.get("/software/stack")
def software_stack():
    return it_software.stack()


@router.put("/software/stack")
def software_stack_save(body: StackIn):
    return _sw(it_software.save_stack, body.items)


# ---------------------------------------------------------------- virtualization planner
def _vt(fn, *a, **k):
    try:
        return fn(*a, **k)
    except virt_lab.VirtError as e:
        raise HTTPException(400, str(e)) from e


class VirtCap(BaseModel):
    vms: float
    vcpu_per_vm: float
    ram_per_vm_gb: float
    disk_per_vm_gb: float
    host_cores: float
    host_ram_gb: float
    vcpu_ratio: float = 4
    headroom_pct: float = 20
    ha_spares: float = 1
    thin_ratio: float = 1.0
    storage_overhead_pct: float = 25
    ram_overcommit: float = 1.0


class VirtRows(BaseModel):
    rows: list[dict] = Field(max_length=40)


@router.get("/virt")
def virt_catalog():
    return virt_lab.catalog()


@router.post("/virt/capacity")
def virt_capacity(b: VirtCap):
    return _vt(virt_lab.capacity, **b.model_dump())


@router.post("/virt/network")
def virt_network(b: VirtRows):
    return _vt(virt_lab.check_network, b.rows)


@router.post("/virt/cluster")
def virt_cluster(b: VirtRows):
    return _vt(virt_lab.check_cluster, b.rows)


@router.get("/repair/search")
def repair_search(q: str = "", limit: int = 8):
    from app.services import repair_search
    return repair_search.search(q[:200], max(1, min(limit, 20)))
