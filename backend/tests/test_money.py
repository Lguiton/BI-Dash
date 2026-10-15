"""Receivables, reminders, profit per job, books and tax set-aside, thank-you notes."""
from datetime import date, timedelta

import pytest

from app.services import money


def _mk(client, title="Slow database", hours=4, rate=100, status="sent", due_days=-10, quote=0):
    c = client.post("/api/clients", json={"name": "Acme Dental", "contact": "Dana Lee", "email": "dana@acme.test"}).json()
    j = client.post("/api/clients/jobs/add", json={"client_id": c["id"], "title": title, "rate": rate, "quote": quote, "status": "active"}).json()
    client.post("/api/clients/time/add", json={"job_id": j["id"], "hours": hours, "note": "work"})
    iss = (date.today() + timedelta(days=due_days - 14)).isoformat()
    inv = client.post("/api/clients/invoices/create", json={"client_id": c["id"], "job_id": j["id"], "issued": iss}).json()
    if status != "draft":
        client.put(f"/api/clients/invoices/{inv['id']}", json={"status": status})
    return c, j, inv


def test_receivables_buckets_and_drafts(client):
    _, _, inv = _mk(client, due_days=-10)
    r = client.get("/api/money/receivables").json()
    assert r["owed"] == 400 and r["late"] == 400
    row = r["rows"][0]
    assert row["days_late"] == 10 and row["bucket"] == "8-14"
    assert {b["id"]: b["count"] for b in r["buckets"]}["8-14"] == 1
    assert r["drafts"] == []
    _mk(client, title="Router swap", due_days=-1, status="draft")
    r = client.get("/api/money/receivables").json()
    assert len(r["drafts"]) == 1 and r["owed"] == 400          # a draft is not owed


@pytest.mark.parametrize("late,tone", [(-3, "heads-up"), (3, "friendly"), (15, "firm"), (45, "final")])
def test_reminder_tone_by_age(client, late, tone):
    _, _, inv = _mk(client, due_days=-late)
    r = client.get(f"/api/money/reminder/{inv['id']}").json()
    assert r["tone"] == tone and inv["number"] in r["body"] and "$400.00" in r["body"] and r["to"] == "dana@acme.test"
    assert "Hi Dana," in r["body"] and "Nothing was sent" in r["note"]
    assert "lawyer" not in r["body"].lower() and "collections" not in r["body"].lower()


def test_reminder_needs_sent_invoice(client):
    _, _, inv = _mk(client, status="draft")
    assert client.get(f"/api/money/reminder/{inv['id']}").status_code == 409
    client.put(f"/api/clients/invoices/{inv['id']}", json={"status": "paid"})
    assert client.get(f"/api/money/reminder/{inv['id']}").status_code == 409
    assert client.get("/api/money/reminder/999").status_code == 404


def test_mark_reminded_shows_on_list(client):
    _, _, inv = _mk(client)
    client.post(f"/api/money/reminder/{inv['id']}/sent")
    assert client.get("/api/money/receivables").json()["rows"][0]["last_reminded"] == date.today().isoformat()


def test_profit_per_job_with_parts_and_flag(client):
    c, j, inv = _mk(client, hours=4, rate=100)
    client.put(f"/api/clients/invoices/{inv['id']}", json={"status": "paid"})
    client.post("/api/money/expenses", json={"amount": 250, "category": "parts", "job_id": j["id"], "note": "SSD"})
    p = client.get("/api/money/profit").json()
    row = p["jobs"][0]
    assert row["charged"] == 400 and row["paid"] == 400 and row["parts"] == 250 and row["net"] == 150
    assert row["per_hour"] == 37.5 and "under 75%" in row["flag"]            # default rate is $75, so 75% of it is $56.25
    assert p["totals"]["net"] == 150


def test_profit_not_flagged_when_rate_is_fine(client):
    _, j, inv = _mk(client, hours=2, rate=120)
    p = client.get("/api/money/profit").json()
    assert p["jobs"][0]["per_hour"] == 120 and p["jobs"][0]["flag"] == ""
    assert p["jobs"][0]["owed"] == 240


def test_profit_fixed_price_line_is_attributed(client):
    c = client.post("/api/clients", json={"name": "Fixed Co"}).json()
    j = client.post("/api/clients/jobs/add", json={"client_id": c["id"], "title": "Wi-Fi setup", "quote": 300, "status": "active"}).json()
    client.post("/api/clients/time/add", json={"job_id": j["id"], "hours": 3})
    client.post(f"/api/jobs/{j['id']}/close", json={"bill": "quote"})
    p = client.get("/api/money/profit").json()
    row = next(r for r in p["jobs"] if r["title"] == "Wi-Fi setup")
    assert row["charged"] == 300 and row["per_hour"] == 100


def test_same_title_jobs_do_not_double_count(client):
    c = client.post("/api/clients", json={"name": "Twin Co"}).json()
    ids = [client.post("/api/clients/jobs/add", json={"client_id": c["id"], "title": "Tune-up", "rate": 50, "status": "active"}).json()["id"] for _ in range(2)]
    client.post("/api/clients/time/add", json={"job_id": ids[0], "hours": 2})
    client.post("/api/clients/invoices/create", json={"client_id": c["id"], "job_id": ids[0]})
    rows = client.get("/api/money/profit").json()["jobs"]
    assert sum(r["charged"] for r in rows) == 100


def test_expense_and_mileage_validation(client):
    assert client.post("/api/money/expenses", json={"amount": 0, "category": "parts"}).status_code == 400
    assert client.post("/api/money/expenses", json={"amount": 5, "category": "yachts"}).status_code == 400
    assert client.post("/api/money/expenses", json={"amount": 5, "category": "parts", "job_id": 999}).status_code == 404
    assert client.post("/api/money/mileage", json={"miles": 0}).status_code == 400
    e = client.post("/api/money/expenses", json={"amount": 12.5, "category": "software"}).json()
    assert client.delete(f"/api/money/expenses/{e['id']}").json() == {"deleted": e["id"]}
    assert client.delete(f"/api/money/expenses/{e['id']}").status_code == 404


def test_books_and_tax_set_aside(client):
    _, j, inv = _mk(client, hours=10, rate=100)
    client.put(f"/api/clients/invoices/{inv['id']}", json={"status": "paid"})
    client.post("/api/money/expenses", json={"amount": 200, "category": "tools"})
    client.post("/api/money/mileage", json={"miles": 100, "purpose": "client visits"})
    client.put("/api/money/settings", json={"tax_pct": 20, "mileage_rate": 0.5})
    b = client.get("/api/money/books").json()
    assert b["income"] == 1000 and b["expenses_total"] == 200 and b["mileage_deduction"] == 50
    assert b["net"] == 750 and b["set_aside"] == 150
    assert sum(q["income"] for q in b["quarters"]) == 1000 and sum(q["set_aside"] for q in b["quarters"]) == pytest.approx(150, abs=0.02)
    assert b["paid"][0]["set_aside"] == 200
    assert "not tax advice" in b["note"]


def test_set_aside_never_negative(client):
    client.post("/api/money/expenses", json={"amount": 500, "category": "tools"})
    b = client.get("/api/money/books").json()
    assert b["net"] == -500 and b["set_aside"] == 0


def test_settings_limits(client):
    assert client.put("/api/money/settings", json={"tax_pct": 90}).status_code == 400
    assert client.put("/api/money/settings", json={"review_url": "javascript:alert(1)"}).status_code == 400
    assert client.put("/api/money/settings", json={"review_url": "https://g.page/r/abc"}).json()["review_url"].startswith("https://")


def test_next_due_date():
    assert money._due_dates(2026)[-1] == "2027-01-15"
    b = money.books(2026, date(2026, 10, 15))
    assert b["next_due"] == "2027-01-15"


def test_csv_blocks_formula_injection(client):
    client.post("/api/money/expenses", json={"amount": 9, "category": "other", "vendor": "=HYPERLINK(\"http://x\")", "note": ""})
    r = client.get("/api/money/books.csv")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert "'=HYPERLINK" in r.text and ",=HYPERLINK" not in r.text and "\n=HYPERLINK" not in r.text


def test_thank_you_needs_paid_and_uses_review_link(client):
    _, _, inv = _mk(client)
    assert client.get(f"/api/money/thank-you/{inv['id']}").status_code == 409
    client.put(f"/api/clients/invoices/{inv['id']}", json={"status": "paid"})
    client.put("/api/money/settings", json={"review_url": "https://g.page/r/abc"})
    r = client.get(f"/api/money/thank-you/{inv['id']}").json()
    assert "https://g.page/r/abc" in r["body"] and r["review_url_set"]
    assert len(client.get("/api/money/receivables").json()["thank_you"]) == 1
    client.post(f"/api/money/thank-you/{inv['id']}/sent")
    assert client.get("/api/money/receivables").json()["thank_you"] == []
