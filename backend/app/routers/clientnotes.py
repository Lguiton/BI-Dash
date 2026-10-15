"""Per-client site notes and the printable site sheet."""
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import Response

from app.services import clientnotes as cn
from app.services import clients as cl
from app.services import pdfdocs

router = APIRouter(prefix="/api/client-notes", tags=["client-notes"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except cl.ClientError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/{cid}")
def get(cid: int):
    return _g(cn.get, cid)


@router.put("/{cid}")
def save(cid: int, body: dict = Body(...)):
    return _g(cn.save, cid, body)


@router.get("/{cid}/sheet.pdf")
def sheet(cid: int):
    data, name = _g(pdfdocs.site_sheet, cid)
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})
