import io
from datetime import date

import pytest

from app.services import breach, endpoint_unix as eu, phish, sec_fixes as sf, sec_report as sr, sec_tracker as st


def test_fix_library_covers_everything_findable():
    from app.services import endpoint_audit as ea
    assert len(sf.FIXES) >= 40 and len({f["id"] for f in sf.FIXES}) == len(sf.FIXES)
    for f in sf.FIXES:
        assert f["steps"] and f["verify"] and f["why"] and f["minutes"] > 0
    for c in ea.CHECKS:
        assert sf.for_ref(c[0]), c[0]
    for c in sr.CHECKLIST:
        assert sf.for_ref(c[0]), c[0]
    for r in ("hsts", "csp", "nosniff", "framing", "referrer", "permissions", "expiry", "tls", "brute", "brute-success", "enum", "scan", "sensitive"):
        assert sf.for_ref(r), r
    for c in eu.MAC + eu.LINUX:
        assert sf.for_ref(c[0]), c[0]
    assert sf.search("clicked a phishing link")[0]["id"] == "phish-clicked"
    assert sf.search("smb1")[0]["id"] == "win-smb1"
    assert sf.search("zzzz") == []
    assert '"steps"' in sf.tool_result({"action": "guide", "id": "win-rdp"})


def test_report_items_link_to_guides():
    r = sr.build(endpoints=[{"label": "PC", "text": "smb1=True\nrdp=0"}], checklist={"mfa_email": "no"})
    assert all(i["fix_id"] for i in r["items"])


def test_tracker_flow(client):
    cid = client.post("/api/clients", json={"name": "Shop"}).json()["id"]
    base = {"client_id": cid, "checklist": {"mfa_email": "no", "antivirus": "no"}}
    a = client.post("/api/sectrack/reports/save", json=base).json()
    assert client.get(f"/api/sectrack/{cid}/compare").status_code == 400
    client.post("/api/sectrack/reports/save", json={"client_id": cid, "checklist": {"mfa_email": "yes", "antivirus": "no", "backups_exist": "no"}})
    c = client.get(f"/api/sectrack/{cid}/compare").json()
    assert len(c["fixed"]) == 1 and len(c["new"]) == 1 and len(c["still_open"]) == 1 and c["from"]["id"] == a["id"]
    assert client.get(f"/api/sectrack/{cid}/reports").json()["reports"][0]["band"]
    assert client.post("/api/sectrack/backups", json={"client_id": 999, "system": "x", "result": "ok"}).status_code == 404
    assert client.post("/api/sectrack/backups", json={"client_id": cid, "system": "NAS", "result": "meh"}).status_code == 400
    client.post("/api/sectrack/backups", json={"client_id": cid, "system": "NAS", "result": "ok", "date": "2026-01-01", "every_days": 30})
    client.post("/api/sectrack/backups", json={"client_id": cid, "system": "Cloud", "result": "fail"})
    s = st.backup_status(cid, date(2026, 3, 1))
    assert {x["system"]: x["status"] for x in s["systems"]} == {"NAS": "overdue", "Cloud": "failed"}
    client.post("/api/sectrack/accounts", json={"client_id": cid, "name": "Work email", "kind": "email", "mfa": "none"})
    client.post("/api/sectrack/accounts", json={"client_id": cid, "name": "Bank", "kind": "money", "mfa": "app", "recovery_stored": True, "last_review": "2026-09-01"})
    rv = st.account_review(cid, date(2026, 10, 1))
    assert [f["account"] for f in rv["flags"]] == ["Work email"] and rv["flags"][0]["severity"] == "high"
    client.post("/api/sectrack/devices", json={"client_id": cid, "name": "Front PC", "os": "Windows 10 Pro"})
    client.post("/api/sectrack/devices", json={"client_id": cid, "name": "New PC", "os": "Windows 11", "eol_date": "2030-01-01"})
    ds = st.device_status(cid, date(2026, 10, 13))
    assert ds["devices"][0]["name"] == "Front PC" and ds["devices"][0]["status"] == "expired" and ds["devices"][1]["status"] == "ok"
    client.post("/api/sectrack/timeline", json={"client_id": cid, "kind": "detected", "what": "Odd login <b>x</b>", "at": "2026-10-13T09:30"})
    h = client.get(f"/api/sectrack/{cid}/timeline/html").text
    assert "Odd login &lt;b&gt;x" in h and "SAMPLE" in h
    rid = client.get(f"/api/sectrack/timeline/list/{cid}").json()["rows"][0]["id"]
    assert client.delete(f"/api/sectrack/timeline/{rid}").status_code == 200
    assert client.get("/api/sectrack/nope/list/1").status_code == 404


def test_phish():
    d = phish.deck(1, 6)
    assert len(d["mails"]) == 6 and not any("phish" in m or "tells" in m for m in d["mails"])
    g = phish.grade({"p1": "phish", "l1": "phish"})
    assert g["score"] == 1 and g["results"][0]["correct"] and not g["results"][1]["correct"]
    with pytest.raises(phish.PhishError):
        phish.grade({"p1": "maybe"})
    assert all(".example" in m["from_addr"] for m in phish.MAILS)


def test_breach_k_anonymity_and_email():
    seen = {}

    def fake(url, headers, timeout=8.0):
        seen["url"] = url
        return 200, "0018A45C4D1DEF81644B54AB7F969B88D65:3\r\n1E4C9B93F3F0682250B6CF8331B7EE68FD8:3730471\r\n"
    r = breach.password_exposure("password", fake)
    assert r["found"] and r["times_seen"] == 3730471 and seen["url"].endswith("/range/5BAA6") and "range/password" not in seen["url"]
    assert not breach.password_exposure("zq9-unlikely-xx", fake)["found"]
    with pytest.raises(breach.BreachError):
        breach.email_exposure("a@b.co", "")
    ok = breach.email_exposure("a@b.co", "k", lambda u, h, t=8.0: (200, '[{"Name":"Acme","BreachDate":"2020-01-01","DataClasses":["Emails"]}]'))
    assert ok["found"] and ok["breaches"][0]["name"] == "Acme"
    assert not breach.email_exposure("a@b.co", "k", lambda u, h, t=8.0: (404, ""))["found"]


def test_unix_audit():
    s = eu.script("macos")
    assert "mac_filevault" in s and "rm " not in s and "sudo " not in s.split("\n", 4)[-1]
    g = eu.grade("mac_filevault=FileVault is Off.\nmac_firewall=Firewall is enabled. (State = 1)\nmac_sip=System Integrity Protection status: enabled.", "macos")
    st_ = {r["id"]: r["status"] for r in g["rows"]}
    assert st_["mac_filevault"] == "fail" and st_["mac_firewall"] == "pass" and st_["mac_sip"] == "pass" and st_["mac_ssh"] == "missing"
    g = eu.grade("linux_ssh_root=yes\nlinux_ssh_password=unset\nlinux_firewall=Status: inactive\nlinux_sudo=2\nlinux_luks=0\nlinux_listen=4", "linux")
    sl = {r["id"]: r["status"] for r in g["rows"]}
    assert sl["linux_ssh_root"] == "fail" and sl["linux_ssh_password"] == "warn" and sl["linux_firewall"] == "fail" and sl["linux_sudo"] == "fail" and sl["linux_luks"] == "warn" and sl["linux_listen"] == "pass"
    with pytest.raises(eu.UnixError):
        eu.grade("nothing", "linux")


def test_api_extras(client):
    assert client.get("/api/security/fixes/search?q=rdp").json()["results"][0]["id"] == "win-rdp"
    assert client.get("/api/security/fixes/win-rdp").json()["steps"]
    assert client.get("/api/security/fixes/nope").status_code == 404
    assert len(client.get("/api/security/phish/deck?seed=3").json()["mails"]) == 8
    assert client.post("/api/security/phish/grade", json={"answers": {"p1": "phish"}}).json()["score"] == 1
    assert "linux_firewall" in client.get("/api/security/unix/script?os=linux").json()["script"]
    assert client.get("/api/security/unix/script?os=beos").status_code == 400
    assert client.post("/api/security/unix/grade", json={"os": "linux", "text": "linux_listen=3"}).status_code == 200
    assert client.post("/api/security/breach/email", json={"email": "a@b.co"}).status_code == 400


def test_security_agent_uses_fix_guides(client):
    from app.services import agents
    from app.services.providers import Call, Turn
    from tests.test_math_and_shortcuts import Fake
    f = Fake([Turn("", [Call("1", "sec_fix", {"action": "search", "query": "remote desktop open"})]), Turn("", [Call("2", "sec_fix", {"action": "guide", "id": "win-rdp"})]), Turn("Here are the steps.")])
    r = agents.chat("security", "RDP is open, how do I fix it?", adapters={"anthropic": f, "openai": f, "google": f}, provider="anthropic")
    assert "sec_fix" in [t["name"] for t in f.tools] and "win-rdp" in str(f.results[0]) and "verify" in str(f.results[1]) and r.reply == "Here are the steps."
    g = Fake([Turn("ok")])
    agents.chat("pm", "hi", adapters={"anthropic": g, "openai": g, "google": g}, provider="anthropic")
    assert "sec_fix" not in [t["name"] for t in g.tools]
