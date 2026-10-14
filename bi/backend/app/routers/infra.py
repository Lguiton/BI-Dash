"""IT infrastructure labs: Group Policy, LDIF, RBAC, RAID risk, backup, DR, load balancing, HTTP triage."""
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import dnsmasq_gen as dg, it_infra as ii, it_ops as io, ticket_coach as tc

router = APIRouter(prefix="/api/infra", tags=["infra"])


def _w(fn, *a, **k):
    try:
        return fn(*a, **k)
    except (ii.InfraError, io.OpsError, dg.DnsmasqError, tc.CoachError) as e:
        raise HTTPException(400, str(e)) from e


class GpoIn(BaseModel):
    object: dict[str, Any]
    chain: list[dict[str, Any]]


class TextIn(BaseModel):
    text: str = Field(max_length=200_000)


class LdifBuildIn(BaseModel):
    kind: str
    fields: dict[str, Any]


class RbacIn(BaseModel):
    roles: dict[str, Any]
    users: dict[str, Any]
    conflicts: Optional[list[Any]] = None
    wide_limit: int = 12


class RaidIn(BaseModel):
    level: str
    disks: int
    size_tb: float
    ure_exponent: float = 14
    rebuild_mb_s: float = 100
    afr_pct: float = 2.0


class BackupIn(BaseModel):
    full_gb: float
    change_pct: float = 5
    days: int = 28
    full_every: int = 7
    restore_mb_s: float = 100
    rpo_h: float = 24
    rto_h: float = 8
    interval_h: float = 24


class DrIn(BaseModel):
    systems: list[dict[str, Any]]


class LbIn(BaseModel):
    servers: list[dict[str, Any]]
    requests: int = 2000
    seed: int = 5
    clients: int = 50
    mean_ms: float = 200
    fail: Optional[str] = None


class TriageIn(BaseModel):
    dns_resolves: Optional[bool] = None
    tcp_connects: Optional[bool] = None
    tls_ok: Optional[bool] = None
    http_status_code: Optional[int] = None
    from_elsewhere_works: Optional[bool] = None
    latency_slow: bool = False


@router.get("/gpo/sample")
def gpo_sample():
    return ii.GPO_SAMPLE


@router.post("/gpo")
def gpo(b: GpoIn):
    return _w(ii.gpo_resolve, b.object, b.chain)


@router.get("/ldif/sample")
def ldif_sample():
    return {"text": ii.LDIF_SAMPLE}


@router.post("/ldif/check")
def ldif_check(b: TextIn):
    return _w(ii.ldif_check, b.text)


@router.post("/ldif/build")
def ldif_build(b: LdifBuildIn):
    return _w(ii.ldif_build, b.kind, b.fields)


@router.get("/rbac/sample")
def rbac_sample():
    return ii.RBAC_SAMPLE


@router.post("/rbac")
def rbac(b: RbacIn):
    return _w(ii.rbac_check, b.roles, b.users, b.conflicts, b.wide_limit)


@router.post("/raid-risk")
def raid_risk(b: RaidIn):
    return _w(io.raid_risk, b.level, b.disks, b.size_tb, b.ure_exponent, b.rebuild_mb_s, b.afr_pct)


@router.post("/backup")
def backup(b: BackupIn):
    return _w(io.backup_plan, **b.model_dump())


@router.get("/dr/sample")
def dr_sample():
    return {"systems": io.DR_SAMPLE}


@router.post("/dr")
def dr(b: DrIn):
    return _w(io.dr_check, b.systems)


@router.post("/lb")
def lb(b: LbIn):
    return _w(io.lb_sim, **b.model_dump())


@router.get("/http")
def http_all():
    return {"codes": io.http_table()}


@router.get("/http/{code}")
def http_one(code: int):
    return _w(io.http_status, code)


@router.post("/triage")
def triage(b: TriageIn):
    return _w(io.site_triage, **b.model_dump())


@router.get("/log/sample")
def log_sample():
    return {"text": io.LOG_SAMPLE}


@router.post("/log")
def log(b: TextIn):
    return _w(io.access_log, b.text)


@router.get("/reference")
def reference():
    return io.reference()


class CodeIn(BaseModel):
    code: int


@router.post("/http-lookup")
def http_lookup(b: CodeIn):
    return _w(io.http_status, b.code)


# ------------------------------------------------------------ ticket coach
class ReportIn(BaseModel):
    title: str = Field("", max_length=400)
    body: str = Field("", max_length=9000)


class ResolutionIn(BaseModel):
    note: str = Field("", max_length=9000)


class PriorityIn(BaseModel):
    users_affected: int = 1
    workaround: bool = True
    deadline: bool = False
    security: bool = False
    business_critical: bool = False


@router.get("/ticket/sample")
def ticket_sample():
    return {"bad": tc.SAMPLE_REPORT, "good": tc.SAMPLE_GOOD, "resolution": tc.SAMPLE_RESOLUTION}


@router.post("/ticket/review")
def ticket_review(b: ReportIn):
    return _w(tc.review_report, b.title, b.body)


@router.post("/ticket/resolution")
def ticket_resolution(b: ResolutionIn):
    return _w(tc.review_resolution, b.note)


@router.post("/ticket/priority")
def ticket_priority(b: PriorityIn):
    return _w(tc.priority, **b.model_dump())


# ------------------------------------------------------------ dnsmasq
class ResIn(BaseModel):
    mac: str = Field(max_length=40)
    ip: str = Field(max_length=45)
    host: str = Field("", max_length=63)


class RecIn(BaseModel):
    name: str = Field(max_length=253)
    ip: str = Field(max_length=45)


class DnsmasqIn(BaseModel):
    interface: str = Field("", max_length=20)
    subnet: str = Field(max_length=50)
    gateway: str = Field("", max_length=45)
    server_ip: str = Field("", max_length=45)
    range_start: str = Field("", max_length=45)
    range_end: str = Field("", max_length=45)
    lease: str = Field("12h", max_length=12)
    domain: str = Field("", max_length=253)
    dns: list[str] = Field(default_factory=list, max_length=4)
    upstream: list[str] = Field(default_factory=list, max_length=4)
    reservations: list[ResIn] = Field(default_factory=list, max_length=100)
    records: list[RecIn] = Field(default_factory=list, max_length=100)
    authoritative: bool = True
    log_queries: bool = False
    no_resolv: bool = False
    cache_size: int = 150


@router.post("/dnsmasq/generate")
def dnsmasq_generate(b: DnsmasqIn):
    return _w(dg.generate, b.model_dump())


@router.post("/dnsmasq/check")
def dnsmasq_check(b: TextIn):
    return _w(dg.check, b.text)


@router.get("/dnsmasq/sample")
def dnsmasq_sample():
    return {"text": dg.SAMPLE_CHECK}
