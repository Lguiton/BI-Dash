"""Work Room endpoints: begin from pasted text, run the agents on a job, show the two screens' data, tick the owner's checklist."""
from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile

from app.services import workroom as wr

router = APIRouter(prefix="/api/workroom", tags=["workroom"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except wr.RoomError as e:
        raise HTTPException(e.status, e.message) from None


@router.post("/begin")
def begin(body: dict = Body(...)):
    return _g(wr.begin, str(body.get("request") or ""), str(body.get("client") or ""), body.get("field") or None)


@router.get("/{jid}")
def view(jid: int):
    return _g(wr.view, jid)


@router.post("/{jid}/run")
async def run(jid: int, instructions: str = Form(""), file: UploadFile | None = File(None)):
    f = None
    if file is not None and file.filename:
        raw = await file.read(25 * 1024 * 1024 + 1)
        if len(raw) > 25 * 1024 * 1024:
            raise HTTPException(400, "That file is over 25 MB. Export a smaller slice.")
        f = (file.filename, raw)
    return _g(wr.run_job, jid, instructions, f)


@router.put("/{jid}/request")
def request_text(jid: int, body: dict = Body(...)):
    return _g(wr.save_request, jid, str(body.get("text") or ""))


@router.put("/{jid}/steps/{wid}")
def tick(jid: int, wid: int, body: dict = Body(...)):
    return _g(wr.tick, jid, wid, bool(body.get("done")))
