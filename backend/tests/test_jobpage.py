import time

from app.services import state, worklog


def _setup(client, quote=300, rate=100):
    c = client.post("/api/clients", json={"name": "Silver State Plumbing"}).json()
    cid = c.get("id") or c["client"]["id"]
    j = client.post("/api/clients/jobs/add", json={"client_id": cid, "title": "Fix printer Wi-Fi", "status": "active", "quote": quote, "rate": rate}).json()
    return cid, j["id"]


def _age_timer(wid, seconds):
    """Pretend the timer started `seconds` ago (the app stores UTC timestamps)."""
    from datetime import datetime, timedelta, timezone
    t = (datetime.now(timezone.utc) - timedelta(seconds=seconds)).strftime("%Y-%m-%d %H:%M:%S")
    state.run("UPDATE work_items SET timer_start=? WHERE id=?", (t, wid))


def test_work_item_links_to_a_job_and_takes_its_client(client):
    cid, jid = _setup(client)
    it = client.post("/api/worklog", json={"title": "Reserve the IP", "job_id": jid}).json()
    assert it["job"]["title"] == "Fix printer Wi-Fi" and it["client"] == "Silver State Plumbing" and "for job" in it["log"][0]["text"]
    assert client.post("/api/worklog", json={"title": "x", "job_id": 9999}).status_code == 404
    up = client.put(f"/api/worklog/{it['id']}", json={"job_id": None}).json()
    assert up["job"] is None and "Unlinked" in up["log"][-1]["text"]


def test_timer_books_billable_time_to_the_job(client):
    cid, jid = _setup(client)
    it = client.post("/api/worklog", json={"title": "On site", "job_id": jid}).json()
    s = client.post(f"/api/worklog/{it['id']}/timer/start").json()
    assert s["running"] is True and s["status"] == "doing"
    other = client.post("/api/worklog", json={"title": "Second"}).json()
    assert client.post(f"/api/worklog/{other['id']}/timer/start").status_code == 409          # one timer at a time
    assert client.post(f"/api/worklog/{it['id']}/timer/start").status_code == 409
    _age_timer(it["id"], 5400)                                                                   # 1.5 hours
    r = client.post(f"/api/worklog/{it['id']}/timer/stop").json()
    assert r["running"] is False and r["added_hours"] == 1.5 and r["capped"] is False and r["seconds"] >= 5400
    jo = client.get(f"/api/jobs/{jid}").json()
    assert jo["hours"] == 1.5 and jo["unbilled_amount"] == 150.0 and jo["time"][0]["note"] == "Timer: On site" and jo["time"][0]["billable"] is True
    assert client.post(f"/api/worklog/{it['id']}/timer/stop").status_code == 409


def test_timer_without_a_job_is_kept_on_the_item_only_and_long_runs_are_capped(client):
    it = client.post("/api/worklog", json={"title": "Reading docs"}).json()
    client.post(f"/api/worklog/{it['id']}/timer/start")
    _age_timer(it["id"], 3600 * 30)
    r = client.post(f"/api/worklog/{it['id']}/timer/stop").json()
    assert r["capped"] is True and r["seconds"] == worklog.MAX_TIMER_HOURS * 3600 and r["added_hours"] == 0.0 and "Not linked to a job" in r["log"][-1]["text"]


def test_finishing_an_item_stops_its_timer(client):
    cid, jid = _setup(client)
    it = client.post("/api/worklog", json={"title": "Quick one", "job_id": jid}).json()
    client.post(f"/api/worklog/{it['id']}/timer/start")
    _age_timer(it["id"], 1800)
    done = client.put(f"/api/worklog/{it['id']}", json={"status": "done"}).json()
    assert done["status"] == "done" and done["running"] is False
    assert client.get(f"/api/jobs/{jid}").json()["hours"] == 0.5


def test_close_job_invoices_the_hours_and_finishes_the_items(client):
    cid, jid = _setup(client)
    a = client.post("/api/worklog", json={"title": "Item A", "job_id": jid}).json()
    client.post(f"/api/worklog/{a['id']}/log", json={"text": "Reserved the printer's IP in the router"})
    client.post(f"/api/worklog/{a['id']}/timer/start")
    _age_timer(a["id"], 7200)
    client.post("/api/clients/time/add", json={"job_id": jid, "hours": 1, "note": "Earlier"})
    r = client.post(f"/api/jobs/{jid}/close", json={"bill": "time"}).json()
    assert r["job"]["status"] == "done" and r["items_closed"] == 1 and r["timer_hours_added"] == 2.0
    assert r["invoice"]["total"] == 300.0                                                          # (2 + 1) h x $100
    jo = client.get(f"/api/jobs/{jid}").json()
    assert jo["unbilled_hours"] == 0 and jo["invoices"][0]["total"] == 300.0 and jo["work_items"][0]["status"] == "done"


def test_close_job_at_the_quoted_price_or_without_billing(client):
    cid, jid = _setup(client, quote=450)
    r = client.post(f"/api/jobs/{jid}/close", json={"bill": "quote"}).json()
    assert r["invoice"]["total"] == 450.0 and r["invoice"]["lines"][0]["desc"].endswith("(fixed price)")
    cid2, jid2 = _setup(client, quote=0)
    assert client.post(f"/api/jobs/{jid2}/close", json={"bill": "quote"}).status_code == 400
    r = client.post(f"/api/jobs/{jid2}/close", json={"bill": "time"}).json()
    assert r["invoice"] is None and "nothing was invoiced" in r["note"]
    assert client.post(f"/api/jobs/{jid2}/close", json={"bill": "bogus"}).status_code == 400
    assert client.get("/api/jobs/9999").status_code == 404


def test_client_summary_has_what_you_wrote_and_hides_internal_lines(client):
    cid, jid = _setup(client)
    it = client.post("/api/worklog", json={"title": "Fix the Wi-Fi drops", "job_id": jid}).json()
    client.post(f"/api/worklog/{it['id']}/log", json={"text": "Moved the access point to the hallway"})
    client.put(f"/api/worklog/{it['id']}", json={"note": "INTERNAL waiting on parts"})
    client.post("/api/fixlog", json={"area": "network", "title": "Back office Wi-Fi drops", "client": "Silver State Plumbing", "symptoms": "Drops past one wall", "steps": ["Moved the node"], "result": "fixed", "cause": "Weak signal"})
    html = client.get(f"/api/jobs/{jid}/summary").text
    assert "Moved the access point to the hallway" in html and "Back office Wi-Fi drops" in html and "Moved the node" in html
    assert "INTERNAL" not in html and "Marked" not in html and "Timer" not in html and "SAMPLE" in html
    assert [f["title"] for f in client.get(f"/api/jobs/{jid}").json()["fixes"]] == ["Back office Wi-Fi drops"]
