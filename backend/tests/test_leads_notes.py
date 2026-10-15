"""Lead tracker, client site notes, quote to job."""
from datetime import date, timedelta


def _lead(client, **k):
    return client.post("/api/leads", json={"name": "Bob's Bakery", "source": "nextdoor", "what": "Wi-Fi dead zones", "value": 400, **k}).json()


def test_lead_lifecycle_and_win_creates_client_and_job(client):
    l = _lead(client, contact="bob@bakery.test")
    assert l["status"] == "new"
    client.put(f"/api/leads/{l['id']}", json={"status": "quoted"})
    r = client.post(f"/api/leads/{l['id']}/win", json={}).json()
    assert r["client_id"] and r["job_id"]
    v = client.get(f"/api/clients/{r['client_id']}").json()
    assert v["client"]["email"] == "bob@bakery.test" and v["jobs"][0]["quote"] == 400 and v["jobs"][0]["status"] == "active"
    again = client.post(f"/api/leads/{l['id']}/win", json={})
    assert again.status_code == 409


def test_cannot_mark_won_without_win(client):
    l = _lead(client)
    assert client.put(f"/api/leads/{l['id']}", json={"status": "won"}).status_code == 400
    assert client.put(f"/api/leads/{l['id']}", json={"status": "bogus"}).status_code == 400
    assert client.post("/api/leads", json={"name": ""}).status_code == 400


def test_win_can_use_an_existing_client(client):
    c = client.post("/api/clients", json={"name": "Old Friend"}).json()
    l = _lead(client)
    r = client.post(f"/api/leads/{l['id']}/win", json={"client_id": c["id"], "title": "Rack tidy", "value": 250}).json()
    assert r["client_id"] == c["id"]
    assert client.get(f"/api/clients/{c['id']}").json()["jobs"][0]["title"] == "Rack tidy"
    assert client.post(f"/api/leads/{_lead(client)['id']}/win", json={"client_id": 999}).status_code == 404


def test_stats_say_when_there_is_too_little_data(client):
    _lead(client)
    s = client.get("/api/leads/stats").json()
    assert "Not enough finished leads" in s["message"]
    assert s["sources"][0]["source"] == "nextdoor" and s["sources"][0]["win_rate"] is None


def test_stats_name_a_best_source_only_after_enough_leads(client):
    for i in range(3):
        l = _lead(client, source="referral", value=500)
        client.post(f"/api/leads/{l['id']}/win", json={})
    for i in range(2):
        l = _lead(client, source="google", value=100)
        client.put(f"/api/leads/{l['id']}", json={"status": "lost"})
    s = client.get("/api/leads/stats").json()
    assert "referral" in s["message"] and "5 finished leads" in s["message"]
    ref = next(x for x in s["sources"] if x["source"] == "referral")
    assert ref["won"] == 3 and ref["win_rate"] == 100 and ref["won_value"] == 1500
    goog = next(x for x in s["sources"] if x["source"] == "google")
    assert goog["win_rate"] == 0 and goog["lost"] == 2


def test_due_next_steps_listed(client):
    past = (date.today() - timedelta(days=1)).isoformat()
    l = _lead(client, next_date=past, next_step="call back")
    rows = client.get("/api/leads").json()["leads"]
    assert rows[0]["due"] is True
    client.put(f"/api/leads/{l['id']}", json={"status": "lost"})
    assert client.get("/api/leads").json()["leads"][0]["due"] is False
    assert client.delete(f"/api/leads/{l['id']}").json() == {"deleted": l["id"]}


def test_client_notes_blank_secrets_and_cascade(client):
    c = client.post("/api/clients", json={"name": "Site Co"}).json()
    body = {"network": "Router in closet. admin password: hunter22secret", "issues": "Wi-Fi drops at 3pm", "devices": [{"name": "Front desk PC", "kind": "computer", "address": "192.168.1.20"}, {"name": "", "kind": "x"}, {"name": "Odd", "kind": "toaster"}]}
    r = client.put(f"/api/client-notes/{c['id']}", json=body).json()
    assert "hunter22secret" not in r["network"] and r["masked"] >= 1
    assert [d["name"] for d in r["devices"]] == ["Front desk PC", "Odd"] and r["devices"][1]["kind"] == "other"
    assert client.get(f"/api/client-notes/{c['id']}").json()["issues"] == "Wi-Fi drops at 3pm"
    pdf = client.get(f"/api/client-notes/{c['id']}/sheet.pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    client.delete(f"/api/clients/{c['id']}")
    assert client.get(f"/api/client-notes/{c['id']}").status_code == 404
    from app.services import clientnotes
    assert clientnotes._all() == {}


def test_client_notes_unknown_client(client):
    assert client.get("/api/client-notes/999").status_code == 404
    assert client.put("/api/client-notes/999", json={}).status_code == 404


def test_quote_to_job_then_accept_then_close(client):
    c = client.post("/api/clients", json={"name": "Quote Co"}).json()
    from app.services import service_catalog
    sid = service_catalog.SERVICES[0]["id"]
    lines = [{"id": sid, "qty": 1}]
    q = client.post("/api/service-list/quote", json={"lines": lines, "client": "Quote Co", "discount_pct": 0}).json()
    r = client.post("/api/clients/jobs/from-quote", json={"client_id": c["id"], "lines": lines, "pick": "high"}).json()
    assert r["job"]["status"] == "quoted" and r["price"] == q["total"][1] and r["job"]["notes"].startswith("Quoted:")
    acc = client.post(f"/api/clients/jobs/{r['job']['id']}/accept").json()
    assert acc["status"] == "active" and acc["accepted"] == date.today().isoformat()
    assert client.post(f"/api/clients/jobs/{r['job']['id']}/accept").status_code == 409
    done = client.post(f"/api/jobs/{r['job']['id']}/close", json={"bill": "quote"}).json()
    assert done["invoice"]["lines"][0]["rate"] == r["price"]


def test_quote_to_job_new_client_and_errors(client):
    from app.services import service_catalog
    lines = [{"id": service_catalog.SERVICES[0]["id"], "qty": 2}]
    r = client.post("/api/clients/jobs/from-quote", json={"client_name": "Brand New", "lines": lines}).json()
    assert client.get(f"/api/clients/{r['client_id']}").json()["client"]["name"] == "Brand New"
    assert client.post("/api/clients/jobs/from-quote", json={"lines": lines}).status_code == 400
    assert client.post("/api/clients/jobs/from-quote", json={"client_id": r["client_id"], "lines": []}).status_code == 400
    assert client.post("/api/clients/jobs/from-quote", json={"client_id": r["client_id"], "lines": [{"id": "nope"}]}).status_code == 400
    assert client.post("/api/clients/jobs/from-quote", json={"client_id": r["client_id"], "lines": lines, "pick": "huge"}).status_code == 400


def test_fix_checklist_pdf(client):
    f = client.post("/api/fixlog", json={"area": "it", "title": "Printer offline", "symptoms": "Won't print", "steps": ["Restart spooler", "Re-add printer"], "prevention": "Set a static IP", "result": "fixed"})
    assert f.status_code == 200, f.text
    r = client.get(f"/api/fixlog/{f.json()['id']}/checklist.pdf")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    from app.services import fileformats
    text = fileformats.pdf_text(r.content)
    assert "Restart spooler" in text and "static IP" in text
    assert client.get("/api/fixlog/999/checklist.pdf").status_code == 404
