from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.services import job_intake as intake

TODAY = date(2026, 10, 15)  # a Thursday
MSG = """From: Dana Lopez <dana@example.com>
Subject: Wi-Fi keeps dropping at the shop

Hi, our router and wifi keep dropping. Can you set up a better access point by Monday?"""


def test_reads_client_title_field_due_quote():
    r = intake.read(MSG, TODAY)
    assert r["client"] == "Dana Lopez"
    assert r["title"] == "Wi-Fi keeps dropping at the shop"
    assert r["field"]["key"] == "network"
    assert r["due"] == "2026-10-19"
    assert r["quote"] and r["quote"]["low"] <= r["quote"]["suggested"] <= r["quote"]["high"]


def test_dates_and_plain_text():
    assert intake._due("need it tomorrow", TODAY) == "2026-10-16"
    assert intake._due("due 11/3", TODAY) == "2026-11-03"
    assert intake._due("nothing here", TODAY) is None
    r = intake.read("Hello, this is Sam Cole. My laptop screen is cracked and the battery is bad.", TODAY)
    assert r["client"] == "Sam Cole" and r["field"]["key"] == "itsupport"


def test_empty_paste_refused_and_endpoint_makes_nothing():
    c = TestClient(app)
    assert c.post("/api/jobs/intake", json={"text": " "}).status_code == 400
    before = c.get("/api/clients/open-jobs").json()["jobs"]
    r = c.post("/api/jobs/intake", json={"text": MSG})
    assert r.status_code == 200 and r.json()["client"] == "Dana Lopez"
    assert c.get("/api/clients/open-jobs").json()["jobs"] == before


def test_quick_start_takes_due_and_quote():
    c = TestClient(app)
    r = c.post("/api/jobs/quick-start", json={"title": "Router setup", "client": "Intake Test Co", "due": "2026-12-01", "quote": 300}).json()
    assert r["job"]["due"] == "2026-12-01" and r["job"]["quote"] == 300
