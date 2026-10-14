"""Alerts: what needs attention now, and whether to be emailed about it."""
from fastapi import APIRouter, Body, HTTPException

from app.services import alerts, mailer

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
def status():
    return alerts.status()


@router.put("/config")
def config(body: dict = Body(...)):
    try:
        alerts.save_config(body)
    except alerts.AlertError as e:
        raise HTTPException(e.status, e.message) from None
    return alerts.status()


@router.post("/check")
def check(body: dict = Body(default={})):
    return alerts.check(send=bool(body.get("send")))


@router.post("/test-email")
def test_email():
    try:
        to = mailer.send("BI dashboard: test email", "If you can read this, alert emails will reach you.")
    except mailer.MailError as e:
        raise HTTPException(e.status, e.message) from None
    return {"sent_to": to}
