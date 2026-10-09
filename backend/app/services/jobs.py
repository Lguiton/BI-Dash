"""Housekeeping the scheduler does for the ACTIVE workspace: a weekly plan snapshot, a weekly restore drill and the alert check.
Each job is wrapped so one failure never stops the others or the scheduler."""
from __future__ import annotations

import time

from app.services import alerts, company, drill, state, workspaces

_last_alert_pass: dict[str, float] = {}
ALERT_EVERY_SECONDS = 900


def tick() -> list[str]:
    ran: list[str] = []
    ws = workspaces.active()
    try:
        if company.weekly_due():
            s = company.snapshot("weekly")
            ran.append("snapshot")
            cfg = alerts.config()
            if cfg["email"] and alerts.mailer.configured():
                try:
                    alerts.mailer.send("Weekly engagement brief", s["brief"])
                except alerts.mailer.MailError:
                    pass
    except Exception:  # noqa: BLE001
        pass
    try:
        if drill.due():
            drill.run()
            ran.append("drill")
    except Exception:  # noqa: BLE001
        pass
    try:
        if alerts.config()["enabled"] and time.time() - _last_alert_pass.get(ws, 0) >= ALERT_EVERY_SECONDS:
            _last_alert_pass[ws] = time.time()
            alerts.check(send=True)
            ran.append("alerts")
    except Exception:  # noqa: BLE001
        pass
    return ran
