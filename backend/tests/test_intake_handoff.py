from fastapi.testclient import TestClient

from app.main import app

c = TestClient(app)
CSV = "date,description,category,amount\n" + "\n".join(f"2026-09-{d:02d},Sale {d},Cars,{1000 + d * 37}" for d in range(1, 21))
AUTH = "time,src_ip,user,event,severity\n" + "\n".join(f"2026-10-01 10:00:{d:02d},10.0.0.{d},root,failed login,high" for d in range(1, 20))


def run_full(name, text):
    r = c.post("/api/intake/start", data={"preview": "false", "name": name}, files={"file": (name + ".csv", text.encode(), "text/csv")}).json()
    for _ in range(12):
        r = c.post(f"/api/intake/{r['id']}/next").json()
        if r["status"] != "running":
            break
    return r["id"]


def test_sales_file_suggests_analyst_and_hands_over_the_table():
    rid = run_full("car_sales_ledger_t", CSV)
    s = c.get(f"/api/intake/{rid}/suggest").json()
    assert s["suggestions"][0]["track"] == "analyst" and s["suggestions"][0]["href"].startswith("/tracks/analyst?")
    assert all(x["why"] for x in s["suggestions"])
    b = c.get(f"/api/intake/{rid}/brief", params={"track": "analyst"}).json()
    assert "Stored" in b["text"] or "table" in b["text"]
    assert "First rows" in b["text"] and "Sale 1" in b["text"] and b["ask"]
    assert c.get(f"/api/intake/{rid}/brief", params={"track": "nope"}).status_code == 404
    c.post(f"/api/intake/{rid}/undo")


def test_login_log_suggests_security_first():
    rid = run_full("auth_events_t", AUTH)
    s = c.get(f"/api/intake/{rid}/suggest").json()
    assert s["suggestions"][0]["track"] in ("security", "network")
    assert "security" in [x["track"] for x in s["suggestions"]]
    c.post(f"/api/intake/{rid}/undo")
    assert c.get("/api/intake/nonexistent/suggest").status_code in (400, 404)
