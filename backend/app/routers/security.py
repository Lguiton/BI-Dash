"""Cybersecurity track endpoints. Defensive tools only (see services/security.py)."""
import threading
import time
from collections import deque
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field

from app.services import seclogs, security, selfaudit, state

router = APIRouter(prefix="/api/security", tags=["security"])
_hits: deque[float] = deque()
_lock = threading.Lock()


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except security.SecError as e:
        raise HTTPException(e.status, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


def _limit_network():
    """Network checks talk to other computers, so cap them: 12 per minute."""
    now = time.time()
    with _lock:
        while _hits and now - _hits[0] > 60:
            _hits.popleft()
        if len(_hits) >= 12:
            raise HTTPException(429, "That's a lot of network checks in a minute. Wait a little and try again.")
        _hits.append(now)


# ---- self-audit
@router.get("/audit")
def audit(request: Request):
    return selfaudit.run(request.client.host if request.client else None)


# ---- logs
class LogIn(BaseModel):
    text: str = Field(min_length=1, max_length=seclogs.MAX_BYTES)
    year: int | None = Field(None, ge=2000, le=2100)


class LogSearchIn(LogIn):
    query: str = Field("", max_length=200)
    level: str = Field("", max_length=10)
    ip: str = Field("", max_length=64)
    limit: int = Field(100, ge=1, le=500)


@router.get("/logs/sample")
def logs_sample():
    return {"text": seclogs.sample_log(), "note": "Made-up lines using documentation-range addresses. Safe to practise on."}


@router.post("/logs/analyze")
def logs(body: LogIn):
    return _g(seclogs.analyze, body.text, body.year)


@router.post("/logs/analyze-file")
async def logs_file(file: UploadFile = File(...), year: int | None = Form(None)):
    raw = await file.read(seclogs.MAX_BYTES + 1)
    if len(raw) > seclogs.MAX_BYTES:
        raise HTTPException(413, f"That log is over {seclogs.MAX_BYTES // (1024 * 1024)} MB. Upload a smaller slice.")
    return _g(seclogs.analyze, raw.decode("utf-8", "replace"), year)


@router.post("/logs/search")
def logs_search(body: LogSearchIn):
    return _g(seclogs.search, body.text, body.query, body.level, body.ip, body.limit, body.year)


# ---- website checks (public sites only)
class HostIn(BaseModel):
    host: str = Field(min_length=3, max_length=253)


@router.post("/headers")
def headers(body: HostIn):
    _limit_network()
    return _g(security.check_headers, body.host)


@router.post("/cert")
def cert(body: HostIn):
    _limit_network()
    return _g(security.check_cert, body.host)


@router.get("/ports")
def ports():
    _limit_network()
    return security.check_ports()


# ---- hashing
class HashIn(BaseModel):
    text: str = Field(max_length=1_000_000)
    algos: list[str] = Field(default_factory=lambda: ["sha256"], max_length=6)
    expected: str | None = Field(None, max_length=200)
    algo: str = "sha256"


@router.post("/hash")
def hash_text(body: HashIn):
    data = body.text.encode()
    out = _g(security.hash_bytes, data, body.algos)
    if body.expected:
        out["verify"] = _g(security.verify_hash, data, body.expected, body.algo)
    return out


@router.post("/hash-file")
async def hash_file(file: UploadFile = File(...), algos: str = Form("sha256"), expected: str = Form("")):
    raw = await file.read(security.MAX_HASH_BYTES + 1)
    out = _g(security.hash_bytes, raw, [a for a in algos.split(",") if a])
    out["filename"] = file.filename
    if expected.strip():
        out["verify"] = _g(security.verify_hash, raw, expected, (algos.split(",")[0] or "sha256"))
    return out


# ---- passwords and one-time codes
class PwIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)


@router.post("/password/check")
def password_check(body: PwIn):
    return _g(security.password_strength, body.password)


@router.get("/password/generate")
def password_generate(kind: Literal["passphrase", "password"] = "passphrase", length: int = Query(6, ge=4, le=64)):
    return _g(security.generate, kind, length)


class TotpIn(BaseModel):
    secret: str = Field(min_length=8, max_length=80)
    code: str | None = Field(None, max_length=12)


@router.get("/totp/new")
def totp_new():
    return security.new_secret()


@router.post("/totp")
def totp(body: TotpIn):
    return _g(security.totp_lab, body.secret, body.code)


# ---- incidents
class IncidentIn(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    category: str = Field(max_length=30)
    severity: str = Field(max_length=10)
    note: str = Field("", max_length=300)


class IncidentPatch(BaseModel):
    status: str | None = Field(None, max_length=15)
    severity: str | None = Field(None, max_length=10)
    note: str | None = Field(None, max_length=500)
    tick: dict | None = None


@router.get("/incidents")
def incidents():
    return security.incidents()


@router.post("/incidents")
def incident_open(body: IncidentIn):
    return _g(security.open_incident, body.title, body.category, body.severity, body.note)


@router.patch("/incidents/{iid}")
def incident_update(iid: int, body: IncidentPatch):
    return _g(security.update_incident, iid, body.status, body.note, body.tick, body.severity)


@router.delete("/incidents/{iid}")
def incident_delete(iid: int):
    _g(security.delete_incident, iid)
    return {"deleted": iid}
