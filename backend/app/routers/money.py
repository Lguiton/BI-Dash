"""Who owes you, profit per job, expenses and mileage, tax set-aside, thank-you notes."""
from datetime import date

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import Response

from app.services import clients as cl
from app.services import money

router = APIRouter(prefix="/api/money", tags=["money"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except cl.ClientError as e:
        raise HTTPException(e.status, e.message) from None
    except (TypeError, ValueError):
        raise HTTPException(400, "Check the numbers and ids you sent.") from None


@router.get("/receivables")
def receivables():
    return money.receivables()


@router.get("/reminder/{iid}")
def reminder(iid: int):
    return _g(money.reminder, iid)


@router.post("/reminder/{iid}/sent")
def reminded(iid: int):
    return _g(money.mark_reminded, iid)


@router.get("/thank-you/{iid}")
def thank_you(iid: int):
    return _g(money.thank_you, iid)


@router.post("/thank-you/{iid}/sent")
def thanked(iid: int):
    return _g(money.mark_thanked, iid)


@router.get("/profit")
def profit():
    return money.profit()


@router.get("/settings")
def get_settings():
    return money.settings()


@router.put("/settings")
def put_settings(body: dict = Body(...)):
    return _g(money.settings, body)


@router.get("/books")
def books(year: int | None = Query(None)):
    return _g(money.books, year)


@router.get("/books.csv")
def books_csv(year: int | None = Query(None)):
    text, name = _g(money.books_csv, year)
    return Response(text, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/expenses")
def add_expense(body: dict = Body(...)):
    return _g(money.add_expense, body)


@router.delete("/expenses/{eid}")
def del_expense(eid: int):
    return _g(money.delete_expense, eid)


@router.post("/mileage")
def add_mileage(body: dict = Body(...)):
    return _g(money.add_mileage, body)


@router.delete("/mileage/{mid}")
def del_mileage(mid: int):
    return _g(money.delete_mileage, mid)


@router.get("/categories")
def categories():
    return {"categories": list(money.CATEGORIES), "today": date.today().isoformat()}
