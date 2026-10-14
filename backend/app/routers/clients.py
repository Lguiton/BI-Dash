from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import HTMLResponse, Response

from app.services import clients as cl

router = APIRouter(prefix="/api/clients", tags=["clients"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except cl.ClientError as e:
        raise HTTPException(e.status, e.message) from None
    except (TypeError, ValueError):
        raise HTTPException(400, "Check the numbers and ids you sent.") from None


@router.get("/overview")
def overview():
    return cl.overview()


@router.get("/settings")
def get_settings():
    return cl.settings()


@router.put("/settings")
def put_settings(body: dict = Body(...)):
    return _g(cl.settings, body)


@router.get("")
def clients():
    return {"clients": cl.list_clients(), "sample": cl.sample()}


@router.post("")
def add(body: dict = Body(...)):
    return _g(cl.add_client, body)


@router.get("/{cid}")
def view(cid: int):
    return _g(cl.client_view, cid)


@router.put("/{cid}")
def update(cid: int, body: dict = Body(...)):
    return _g(cl.update_client, cid, body)


@router.delete("/{cid}")
def delete(cid: int):
    return _g(cl.delete_client, cid)


@router.post("/jobs/add")
def add_job(body: dict = Body(...)):
    return _g(cl.add_job, body)


@router.put("/jobs/{jid}")
def update_job(jid: int, body: dict = Body(...)):
    return _g(cl.update_job, jid, body)


@router.delete("/jobs/{jid}")
def delete_job(jid: int):
    return _g(cl.delete_job, jid)


@router.post("/time/add")
def add_time(body: dict = Body(...)):
    return _g(cl.add_time, body)


@router.delete("/time/{tid}")
def delete_time(tid: int):
    return _g(cl.delete_time, tid)


@router.post("/followups/add")
def add_followup(body: dict = Body(...)):
    return _g(cl.add_followup, body)


@router.put("/followups/{fid}")
def update_followup(fid: int, body: dict = Body(...)):
    return _g(cl.update_followup, fid, body)


@router.delete("/followups/{fid}")
def delete_followup(fid: int):
    return _g(cl.delete_followup, fid)


@router.post("/invoices/create")
def create_invoice(body: dict = Body(...)):
    return _g(cl.create_invoice, body)


@router.put("/invoices/{iid}")
def set_invoice(iid: int, body: dict = Body(...)):
    return _g(cl.set_invoice, iid, body.get("status"), body.get("paid_date"))


@router.get("/invoices/{iid}/view")
def invoice_view(iid: int):
    return HTMLResponse(_g(cl.invoice_html, iid), headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})


@router.post("/{cid}/pack")
def pack(cid: int, body: dict = Body(default={})):
    raw, rec = _g(cl.handoff_pack, cid, body.get("notes") or {}, body.get("pack_id"), int(body.get("days") or 30), body.get("model_ids"), body.get("include_invoices", True))
    return Response(raw, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="handoff_{cid}_{rec["made"]}.zip"'})
