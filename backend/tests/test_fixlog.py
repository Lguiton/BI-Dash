def _fix(**k):
    base = {"area": "it", "title": "Laptop will not charge", "category": "Hardware", "device": "Dell Latitude 5420", "symptoms": "Plugged in but battery stays at 12 percent, charger light is off",
            "cause": "Failed charging port", "steps": ["Tried a known-good charger", "Reseated the DC jack", "Replaced the DC jack"], "result": "fixed", "minutes": 45, "tags": ["battery", "charger"]}
    base.update(k)
    return base


def test_add_get_list_update_delete(client):
    r = client.post("/api/fixlog", json=_fix())
    assert r.status_code == 200
    rec = r.json()
    assert rec["area_label"] == "IT repair" and rec["steps"][2] == "Replaced the DC jack" and rec["masked"] == 0
    assert client.get(f"/api/fixlog/{rec['id']}").json()["title"] == "Laptop will not charge"
    assert client.get("/api/fixlog").json()["stats"]["total"] == 1
    up = client.put(f"/api/fixlog/{rec['id']}", json={"result": "workaround", "minutes": 60}).json()
    assert up["result"] == "workaround" and up["minutes"] == 60 and up["title"] == "Laptop will not charge"
    assert client.delete(f"/api/fixlog/{rec['id']}").status_code == 200
    assert client.get(f"/api/fixlog/{rec['id']}").status_code == 404


def test_secrets_are_blanked_before_saving(client):
    key = "AKIA" + "ABCDEFGHIJKLMNOP"
    r = client.post("/api/fixlog", json=_fix(area="security", title="Leaked key in repo", symptoms=f"Found {key} in a commit", steps=["Rotated the key", "The admin password is Hunter22xx now"], cause="token: abcd1234efgh")).json()
    blob = " ".join([r["symptoms"], r["cause"]] + r["steps"])
    assert key not in blob and "Hunter22xx" not in blob and "abcd1234efgh" not in blob
    assert r["masked"] >= 3 and "[hidden]" in blob


def test_validation(client):
    assert client.post("/api/fixlog", json=_fix(title="  ")).status_code == 400
    assert client.post("/api/fixlog", json=_fix(area="plumbing")).status_code == 400
    assert client.post("/api/fixlog", json=_fix(result="maybe")).status_code == 400
    assert client.post("/api/fixlog", json=_fix(minutes="lots")).status_code == 400
    assert client.post("/api/fixlog", json=_fix(minutes=999999)).status_code == 400
    assert client.get("/api/fixlog?area=nope").status_code == 400


def test_search_finds_past_fix_and_prefers_fixed(client):
    a = client.post("/api/fixlog", json=_fix()).json()
    client.post("/api/fixlog", json=_fix(title="Printer offline", symptoms="Printer shows offline after router change", category="Printer", device="HP", cause="", steps=["Set a fixed IP"], tags=["printer"]))
    client.post("/api/fixlog", json=_fix(area="security", title="Phishing email clicked", symptoms="User entered password on a fake login page", steps=["Reset password", "Revoked sessions"], tags=["phish"]))
    r = client.get("/api/fixlog/search", params={"q": "laptop wont charge"}).json()
    assert r["fixes"] and r["fixes"][0]["id"] == a["id"]
    r2 = client.get("/api/fixlog/search", params={"q": "fake login page", "area": "security"}).json()
    assert r2["fixes"][0]["title"] == "Phishing email clicked"
    assert all(f["area"] == "security" for f in r2["fixes"])
    assert client.get("/api/fixlog/search", params={"q": "zzzz qqqq"}).json()["fixes"] == []
    assert client.get("/api/fixlog/search", params={"q": ""}).json() == {"query": "", "fixes": [], "guides": []}


def test_write_ups_and_export(client):
    rec = client.post("/api/fixlog", json=_fix(title="Fix <b>bold</b>", client="Acme", cause="Internal only cause")).json()
    md = client.get(f"/api/fixlog/{rec['id']}/doc").text
    assert "## Steps taken" in md and "1. Tried a known-good charger" in md and "Internal only cause" in md
    cl = client.get(f"/api/fixlog/{rec['id']}/doc", params={"client": "true"}).text
    assert "Internal only cause" not in cl and "## What was done" in cl and "Acme" not in cl
    h = client.get(f"/api/fixlog/{rec['id']}/doc", params={"format": "html"}).text
    assert "&lt;b&gt;bold" in h and "<b>bold" not in h
    ex = client.get("/api/fixlog/export")
    assert ex.status_code == 200 and "Fix log" in ex.text
    assert client.get("/api/fixlog/export", params={"area": "network"}).status_code == 400


def test_draft_from_ticket_and_back_link(client):
    t = client.post("/api/it/tickets", json={"title": "Wi-Fi drops every hour", "category": "network", "priority": "high", "requester": "Dana", "note": "Drops at the top of the hour"}).json()
    client.patch(f"/api/it/tickets/{t['id']}", json={"tick": {"index": 0, "done": True}})
    client.patch(f"/api/it/tickets/{t['id']}", json={"note": "Changed the channel to 36"})
    client.patch(f"/api/it/tickets/{t['id']}", json={"status": "resolved"})
    d = client.get(f"/api/fixlog/draft/ticket/{t['id']}").json()
    assert d["area"] == "network" and d["client"] == "Dana" and d["result"] == "fixed" and d["symptoms"] == "Drops at the top of the hour"
    assert "Changed the channel to 36" in d["steps"] and any("Can others" in s for s in d["steps"]) and not any(s.startswith("Status:") for s in d["steps"])
    saved = client.post("/api/fixlog", json=d).json()
    tl = client.get("/api/it/tickets").json()["tickets"][0]["timeline"]
    assert any(f"fix log (#{saved['id']})" in e["text"] for e in tl)
    assert client.get("/api/fixlog/draft/ticket/9999").status_code == 404


def test_concierge_points_at_the_fix_logs():
    from app.services import concierge
    hrefs = [r["href"] for r in concierge.route("have I fixed this before")["results"]]
    assert "/tracks/itsupport?view=tools&tab=fixlog" in hrefs
    hrefs = [r["href"] for r in concierge.route("security incident history")["results"]]
    assert "/tracks/security?view=tools&tab=fixlog" in hrefs
