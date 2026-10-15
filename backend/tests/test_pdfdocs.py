"""PDF downloads: invoice, job summary, quote, price list and checklists."""
import pytest

from app.services import fileformats


def text_of(pdf: bytes) -> str:
    assert pdf[:5] == b"%PDF-"
    return fileformats.pdf_text(pdf)


@pytest.fixture
def job(client):
    c = client.post("/api/clients", json={"name": "Acme <b>Co</b>", "contact": "sam@example.com"}).json()
    j = client.post("/api/clients/jobs/add", json={"client_id": c["id"], "title": "Fix the office Wi-Fi", "quote": 180}).json()
    return {"client": c, "job": j}


def test_invoice_pdf(client, job):
    client.post("/api/clients/time/add", json={"job_id": job["job"]["id"], "hours": 2, "note": "Router swap", "billable": True})
    inv = client.post("/api/clients/invoices/create", json={"client_id": job["client"]["id"], "extra": [{"desc": "Cable <i>kit</i>", "qty": 1, "rate": 25}]})
    assert inv.status_code == 200, inv.text
    iid = inv.json()["id"]
    r = client.get(f"/api/clients/invoices/{iid}/pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"] and ".pdf" in r.headers["content-disposition"]
    txt = text_of(r.content)
    assert "Invoice" in txt and "Acme" in txt and "Cable" in txt
    assert "Cable <i>kit</i>" in txt and "Acme <b>Co</b>" in txt   # typed text is shown as typed, never read as formatting
    assert client.get("/api/clients/invoices/9999/pdf").status_code in (404, 400)


def test_job_summary_pdf(client, job):
    jid = job["job"]["id"]
    r = client.get(f"/api/jobs/{jid}/summary.pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    txt = text_of(r.content)
    assert "Job summary" in txt and "Fix the office Wi-Fi" in txt and "Work completed as agreed" in txt
    assert client.get("/api/jobs/9999/summary.pdf").status_code in (404, 400)


def test_quote_pdf(client):
    r = client.post("/api/service-list/quote/pdf", json={"lines": [{"id": s["id"], "qty": 2} for s in client.get("/api/service-list").json()["services"][:2]], "client": "Sam <script>", "discount_pct": 10})
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    txt = text_of(r.content)
    assert "Quote for Sam" in txt and "after 10% off" in txt
    assert client.post("/api/service-list/quote/pdf", json={"lines": [{"id": "nope", "qty": 1}]}).status_code == 400


def test_price_list_pdf(client):
    r = client.get("/api/service-list/price-list/pdf")
    assert r.status_code == 200
    txt = text_of(r.content)
    assert "price list" in txt and "Remote tech support" in txt


def test_checklist_pdfs(client, job):
    jid = job["job"]["id"]
    blank = client.get("/api/checklists/slow-database/pdf")
    assert blank.status_code == 200 and "Slow database triage" in text_of(blank.content)
    assert client.get("/api/checklists/nope/pdf").status_code == 404
    assert client.get(f"/api/checklists/job/{jid}/slow-database/pdf").status_code == 404
    client.post(f"/api/checklists/job/{jid}/slow-database")
    client.put(f"/api/checklists/job/{jid}/slow-database", json={"checked": ["s1.1"], "notes": "Disk at 98 percent"})
    r = client.get(f"/api/checklists/job/{jid}/slow-database/pdf")
    txt = text_of(r.content)
    assert "Fix the office Wi-Fi" in txt and "Disk at 98 percent" in txt and "[x]" in txt
