"""Sample-work page for prospects. Builds one downloadable HTML file; nothing is published or sent."""
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import HTMLResponse

from app.services import samples

router = APIRouter(prefix="/api/samples", tags=["samples"])


def _w(fn, *a):
    try:
        return fn(*a)
    except samples.SampleError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("")
def get():
    return samples.get()


@router.put("/profile")
def profile(b: dict = Body(...)):
    return _w(samples.set_profile, b)


@router.post("/items")
def add(b: dict = Body(...)):
    return _w(samples.add_item, b)


@router.post("/starters/{n}")
def starter(n: int):
    return _w(samples.add_starter, n)


@router.put("/items/{iid}")
def update(iid: str, b: dict = Body(...)):
    return _w(samples.update_item, iid, b)


@router.delete("/items/{iid}")
def delete(iid: str):
    return _w(samples.delete_item, iid)


@router.post("/items/{iid}/move/{direction}")
def move(iid: str, direction: int):
    return _w(samples.move_item, iid, direction)


@router.get("/html", response_class=HTMLResponse)
def page(download: bool = False):
    h = {"Content-Disposition": 'attachment; filename="sample-work.html"'} if download else {}
    return HTMLResponse(samples.render_html(), headers=h)
