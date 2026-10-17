"""Cybersecurity track endpoints. Defensive tools only (see services/security.py)."""
import threading
import time
from collections import deque
from typing import Literal

from fastapi import APIRouter, Body, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.services import breach, endpoint_unix, phish, sec_fixes, sec_report, seclogs, security, selfaudit, state

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
    from app.services import datasets
    return _g(seclogs.analyze, datasets.decode(raw), year)


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


# ============================================================ security checkup report
def _report(body: dict):
    hosts = [h for h in (body.get("hosts") or []) if str(h).strip()][:5]
    for _ in hosts:
        _limit_network()
        _limit_network()
    try:
        return sec_report.build(body.get("client", ""), body.get("prepared_by", ""), body.get("scope", ""), body.get("endpoints") or [], hosts, str(body.get("logs") or "")[:5_000_000], body.get("checklist") or {})
    except sec_report.ReportError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/report/checklist")
def report_checklist():
    return {"items": [{"id": c[0], "title": c[1], "severity": c[2]} for c in sec_report.CHECKLIST], "answers": list(sec_report.ANS)}


@router.post("/report")
def report(body: dict = Body(...)):
    return _report(body)


@router.post("/report/html")
def report_html(body: dict = Body(...)):
    return HTMLResponse(sec_report.to_html(_report(body)), headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'", "Content-Disposition": 'inline; filename="security_checkup.html"'})


# ============================================================ how-to-fix guides, phishing practice, breach checks, macOS/Linux audit
@router.get("/fixes")
def fixes_index():
    return {"areas": sec_fixes.areas(), "count": len(sec_fixes.FIXES)}


@router.get("/fixes/search")
def fixes_search(q: str = Query("", max_length=200)):
    return {"query": q, "results": sec_fixes.search(q, 8)}


@router.get("/fixes/{gid}")
def fixes_get(gid: str):
    g = sec_fixes.get(gid)
    if not g:
        raise HTTPException(404, "No guide with that id.")
    return g


@router.get("/phish/deck")
def phish_deck(seed: int = 1, n: int = 8):
    return phish.deck(seed, n)


@router.post("/phish/grade")
def phish_grade(body: dict = Body(...)):
    try:
        return phish.grade(body.get("answers") or {})
    except phish.PhishError as e:
        raise HTTPException(e.status, e.message) from None


@router.post("/breach/password")
def breach_password(body: dict = Body(...)):
    _limit_network()
    try:
        return breach.password_exposure(str(body.get("password") or ""))
    except breach.BreachError as e:
        raise HTTPException(e.status, e.message) from None


@router.post("/breach/email")
def breach_email(body: dict = Body(...)):
    _limit_network()
    try:
        return breach.email_exposure(str(body.get("email") or ""), str(body.get("api_key") or ""))
    except breach.BreachError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/unix/script")
def unix_script(os: str = Query("linux")):
    try:
        return {"script": endpoint_unix.script(os)}
    except endpoint_unix.UnixError as e:
        raise HTTPException(e.status, e.message) from None


@router.post("/unix/grade")
def unix_grade(body: dict = Body(...)):
    try:
        return endpoint_unix.grade(str(body.get("text") or ""), str(body.get("os") or ""))
    except endpoint_unix.UnixError as e:
        raise HTTPException(e.status, e.message) from None
