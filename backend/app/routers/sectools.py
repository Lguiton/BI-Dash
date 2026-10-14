"""Security study tools: token and certificate inspectors, CVSS, STRIDE, code scanner, rule matcher, playbook simulator."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import sec_tools as st
from app.services.security import SecError

router = APIRouter(prefix="/api/sectools", tags=["sectools"])


def _w(fn, *a, **k):
    try:
        return fn(*a, **k)
    except SecError as e:
        raise HTTPException(e.status, str(e)) from e


class Jwt(BaseModel):
    token: str = Field(max_length=20000)
    secret: str | None = Field(default=None, max_length=500)


class Pem(BaseModel):
    pem: str = Field(max_length=20000)


class Vec(BaseModel):
    vector: str = Field(max_length=200)


class Txt(BaseModel):
    text: str = Field(max_length=st.MAXT)


class Sig(BaseModel):
    rule: str = Field(max_length=20000)
    events: str = Field(max_length=st.MAXT)


class Pb(BaseModel):
    rules: str = Field(max_length=8000)
    alert: str = Field(max_length=8000)


@router.get("/reference")
def reference():
    return st.reference()


@router.post("/jwt")
def jwt(b: Jwt):
    return _w(st.jwt_inspect, b.token, b.secret)


@router.post("/cert")
def cert(b: Pem):
    return _w(st.cert_inspect, b.pem)


@router.post("/cvss")
def cvss(b: Vec):
    return _w(st.cvss31, b.vector)


@router.post("/stride")
def stride(b: Txt):
    return _w(st.stride, b.text)


@router.post("/code-scan")
def code(b: Txt):
    return _w(st.code_scan, b.text)


@router.post("/sigma")
def sigma(b: Sig):
    return _w(st.sigma, b.rule, b.events)


@router.post("/playbook")
def playbook(b: Pb):
    return _w(st.playbook, b.rules, b.alert)
