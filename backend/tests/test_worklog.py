from datetime import date, timedelta


def test_add_list_and_status_log(client):
    r = client.post("/api/worklog", json={"title": "Fix printer for Silver State", "client": "Silver State Plumbing", "status": "doing"})
    assert r.status_code == 200
    it = r.json()
    assert it["status"] == "doing" and it["log"][0]["text"].startswith("Added")
    up = client.put(f"/api/worklog/{it['id']}", json={"status": "waiting", "note": "Waiting on a new toner"}).json()
    texts = [e["text"] for e in up["log"]]
    assert any("Marked waiting" in t for t in texts) and any("Left off: Waiting on a new toner" in t for t in texts)
    lst = client.get("/api/worklog").json()
    assert lst["counts"]["waiting"] == 1 and lst["items"][0]["id"] == it["id"]


def test_order_overdue_and_done(client):
    old = (date.today() - timedelta(days=2)).isoformat()
    a = client.post("/api/worklog", json={"title": "Late one", "due": old}).json()
    b = client.post("/api/worklog", json={"title": "Doing one", "status": "doing"}).json()
    assert a["overdue"] is True
    lst = client.get("/api/worklog").json()
    assert [i["id"] for i in lst["items"]][:2] == [b["id"], a["id"]] and lst["overdue"] == 1
    client.put(f"/api/worklog/{a['id']}", json={"status": "done"})
    lst = client.get("/api/worklog").json()
    assert all(i["id"] != a["id"] for i in lst["items"]) and lst["done_recent"][0]["id"] == a["id"] and lst["overdue"] == 0


def test_log_entry_secrets_blanked_and_validation(client):
    it = client.post("/api/worklog", json={"title": "Router work"}).json()
    r = client.post(f"/api/worklog/{it['id']}/log", json={"text": "admin password is Hunter22xx now"}).json()
    assert "Hunter22xx" not in r["log"][-1]["text"] and "[hidden]" in r["log"][-1]["text"]
    assert client.post("/api/worklog", json={"title": "  "}).status_code == 400
    assert client.post("/api/worklog", json={"title": "x", "due": "tomorrow"}).status_code == 400
    assert client.post("/api/worklog", json={"title": "x", "status": "nope"}).status_code == 400
    assert client.put("/api/worklog/9999", json={"note": "a"}).status_code == 404
    assert client.delete(f"/api/worklog/{it['id']}").status_code == 200 and client.get("/api/worklog").json()["items"] == []
