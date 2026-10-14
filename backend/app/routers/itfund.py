"""IT fundamentals endpoints (IT Specialist track)."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import it_fund as f

router = APIRouter(prefix="/api/itfund", tags=["itfund"])


def _w(fn, *a, **k):
    try:
        return fn(*a, **k)
    except f.FundError as e:
        raise HTTPException(e.status, e.message) from e


class ConvIn(BaseModel):
    value: str = Field(max_length=80)
    base: str = Field(default="decimal", max_length=10)


class TextIn(BaseModel):
    text: str = Field(max_length=300)


class StorageIn(BaseModel):
    value: float
    unit: str = Field(default="GB", max_length=3)


class ChmodIn(BaseModel):
    mode: str = Field(max_length=12)
    kind: str = Field(default="file", max_length=4)
    umask: str = Field(default="", max_length=5)


class Ip6In(BaseModel):
    address: str = Field(max_length=60)


@router.get("")
def reference(topic: str = Query("", max_length=20)):
    return _w(f.reference, topic)


@router.post("/convert")
def convert(b: ConvIn):
    return _w(f.convert, b.value, b.base)


@router.post("/encode")
def encode(b: TextIn):
    return _w(f.encode_text, b.text)


@router.get("/gate")
def gate(name: str = Query(max_length=6)):
    return _w(f.gate_table, name)


@router.post("/circuit")
def circuit(b: TextIn):
    return _w(f.circuit, b.text)


@router.post("/storage")
def storage(b: StorageIn):
    return _w(f.storage, b.value, b.unit)


@router.post("/chmod")
def chmod(b: ChmodIn):
    return _w(f.chmod, b.mode, b.kind, b.umask)


@router.post("/ipv6")
def ipv6(b: Ip6In):
    return _w(f.ipv6, b.address)


@router.get("/commands")
def commands(q: str = Query("", max_length=60)):
    return f.commands(q)
