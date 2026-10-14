from datetime import date, datetime, timedelta

import pytest

from app.services import biz_packs, briefing
from app.services.db import get_cursor


class FakeSMTP:
    sent = []

    def __init__(self, cfg):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


@pytest.fixture()
def mail(monkeypatch):
    for k, v in (("BI_SMTP_HOST", "smtp.example.com"), ("BI_SMTP_USER", "me@example.com"), ("BI_REPORT_TO", "me@example.com")):
        monkeypatch.setenv(k, v)
    FakeSMTP.sent = []
    return FakeSMTP


def test_build_collects_calendar_followups_and_moves(client):
    today = date.today()
    with get_cursor() as cur:
        cur.execute("CREATE TABLE my_cal (title VARCHAR, start VARCHAR, \"end\" VARCHAR, all_day VARCHAR, hours VARCHAR, location VARCHAR, status VARCHAR, repeats VARCHAR)")
        cur.execute("INSERT INTO my_cal VALUES (?,?,?,?,?,?,?,?)", ["Dentist", f"{today} 09:30", f"{today} 10:30", "no", "1", "Vegas", "Confirmed", "no"])
        cur.execute("INSERT INTO my_cal VALUES (?,?,?,?,?,?,?,?)", ["Car registration", f"{today + timedelta(days=1)}", f"{today + timedelta(days=2)}", "yes", "", "", "Confirmed", "no"])
        cur.execute("INSERT INTO my_cal VALUES (?,?,?,?,?,?,?,?)", ["Next week", f"{today + timedelta(days=7)} 09:00", f"{today + timedelta(days=7)} 10:00", "no", "1", "", "Confirmed", "no"])
    biz_packs.add_row("job-search", {"record_date": str(today - timedelta(days=9)), "company": "Acme", "role_type": "BI developer", "source": "LinkedIn", "stage": "Applied",
                                      "days_to_response": 0, "interviews": 0, "follow_up": str(today - timedelta(days=1))})
    biz_packs.add_row("job-search", {"record_date": str(today), "company": "Birch", "role_type": "BI developer", "source": "LinkedIn", "stage": "Rejected",
                                      "days_to_response": 3, "interviews": 0, "follow_up": str(today - timedelta(days=1))})
    b = briefing.build(datetime.now())
    text = b["body"]
    assert "09:30  Dentist (Vegas)" in text and "Tomorrow: all day  Car registration" in text and "Next week" not in text
    assert "Acme, BI developer (Applied)" in text and "Birch" not in text            # a rejected application needs no follow-up
    biz_packs.add_row("repair-jobs", {"record_date": str(today - timedelta(days=7)), "device_type": "Laptop", "fault": "Battery", "service": "Bench repair", "status": "Completed",
                                       "labor_hours": 1, "parts_cost": 40, "price": 140, "days_to_fix": 2, "follow_up": str(today)})
    assert "Customer check-in: Laptop (Battery)" in briefing.build(datetime.now())["body"]
    assert b["subject"].startswith("Morning briefing: ") and b["items"] >= 3


def test_all_clear_and_config_rules(client, mail, monkeypatch):
    monkeypatch.setattr(briefing.alerts, "current", lambda: [])
    monkeypatch.setattr("app.services.health_check.run", lambda *a, **k: {"needs_attention": []})
    assert "all clear" in briefing.build()["subject"] and "Nothing needs attention" in briefing.build()["body"]
    r = client.put("/api/briefing/config", json={"enabled": True, "hour": 7})
    assert r.status_code == 200 and r.json()["enabled"] and r.json()["hour"] == 7
    assert client.put("/api/briefing/config", json={"hour": 23}).status_code == 422
    assert "catch" not in r.json()["how"] and "isn't running" in r.json()["how"]


def test_not_configured_blocks_enable(client, monkeypatch):
    monkeypatch.delenv("BI_SMTP_HOST", raising=False)
    monkeypatch.delenv("BI_REPORT_TO", raising=False)
    assert client.put("/api/briefing/config", json={"enabled": True}).status_code == 503
    assert client.post("/api/briefing/send").status_code == 503


def test_tick_catches_up_once_per_day_and_retries(client, mail):
    briefing.update_config({"enabled": True, "hour": 7})
    day = datetime(2026, 10, 13, 6, 0)
    assert briefing.tick(day, mail, clock=lambda: 1000) == []                                   # before the send hour
    assert briefing.tick(day.replace(hour=22), mail, clock=lambda: 1000) == []                 # too late: that day's briefing is skipped
    late = day.replace(hour=13)                                                                  # app started at 1 pm: catches up once
    assert briefing.tick(late, mail, clock=lambda: 2000) == ["briefing"] and len(mail.sent) == 1
    assert briefing.tick(late, mail, clock=lambda: 9000) == [] and len(mail.sent) == 1          # not twice the same day
    assert briefing.tick(late + timedelta(days=1), mail, clock=lambda: 90000) == ["briefing"] and len(mail.sent) == 2
    assert briefing.config()["last_sent"] == "2026-10-14"


def test_failed_send_retries_after_30_minutes(client, mail, monkeypatch):
    briefing.update_config({"enabled": True, "hour": 7})
    def boom(cfg):
        raise OSError("down")
    now = datetime(2026, 10, 13, 8, 0)
    assert briefing.tick(now, boom, clock=lambda: 100) == [] and briefing.config()["last_sent"] == ""
    assert briefing.tick(now, mail, clock=lambda: 200) == [] and not mail.sent                  # too soon to retry
    assert briefing.tick(now, mail, clock=lambda: 100 + 1801) == ["briefing"] and len(mail.sent) == 1
