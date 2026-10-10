"""Network Engineer and IT Specialist tracks."""
import socket
from datetime import date

import pytest

from app.services import itlab, netlab


# ---------------------------------------------------------------- network: subnetting
def test_subnet_facts_are_exact(client):
    r = client.post("/api/net/subnet", json={"cidr": "192.168.10.77/26"}).json()
    assert r["network"] == "192.168.10.64" and r["broadcast"] == "192.168.10.127" and r["usable_hosts"] == 62
    assert r["first_host"] == "192.168.10.65" and r["last_host"] == "192.168.10.126" and r["netmask"] == "255.255.255.192"
    assert r["wildcard"] == "0.0.0.63" and r["class"] == "C" and r["scope"] == "private"
    assert r["netmask_binary"] == "11111111.11111111.11111111.11000000"
    assert client.post("/api/net/subnet", json={"cidr": "10.0.0.0/31"}).json()["usable_hosts"] == 2
    assert client.post("/api/net/subnet", json={"cidr": "10.0.0.5/32"}).json()["usable_hosts"] == 1
    v6 = client.post("/api/net/subnet", json={"cidr": "2001:db8::/48"}).json()
    assert v6["version"] == 6 and v6["total_addresses"] == 2 ** 80
    assert client.post("/api/net/subnet", json={"cidr": "not-a-network"}).status_code == 400


def test_split_and_limits(client):
    r = client.post("/api/net/split", json={"cidr": "10.0.0.0/24", "new_prefix": 26}).json()
    assert r["count"] == 4
    assert [s["network"] for s in r["subnets"]] == ["10.0.0.0/26", "10.0.0.64/26", "10.0.0.128/26", "10.0.0.192/26"]
    assert client.post("/api/net/split", json={"cidr": "10.0.0.0/24", "new_prefix": 24}).status_code == 400
    assert client.post("/api/net/split", json={"cidr": "10.0.0.0/8", "new_prefix": 24}).status_code == 400


def test_vlsm_places_big_first_on_boundaries_without_overlap(client):
    r = client.post("/api/net/vlsm", json={"base": "192.168.1.0/24", "needs": [{"name": "C", "hosts": 2}, {"name": "A", "hosts": 50}, {"name": "B", "hosts": 20}]}).json()
    assert [(p["name"], p["network"]) for p in r["plan"]] == [("A", "192.168.1.0/26"), ("B", "192.168.1.64/27"), ("C", "192.168.1.96/30")]
    assert all(p["spare"] >= 0 for p in r["plan"])
    nets = [p["network"] for p in r["plan"]]
    assert client.post("/api/net/overlaps", json={"cidrs": nets}).json()["ok"]
    too_big = client.post("/api/net/vlsm", json={"base": "192.168.1.0/24", "needs": [{"name": "X", "hosts": 200}, {"name": "Y", "hosts": 100}]})
    assert too_big.status_code == 400 and "too small" in too_big.json()["detail"]
    assert client.post("/api/net/vlsm", json={"base": "10.0.0.0/24", "needs": [{"name": "Z", "hosts": "many"}]}).status_code == 400


def test_overlap_contains_and_summarize(client):
    o = client.post("/api/net/overlaps", json={"cidrs": ["10.0.0.0/24", "10.0.0.128/25", "10.1.0.0/24"]}).json()
    assert not o["ok"] and o["overlaps"][0]["relation"] == "a contains b"
    assert client.post("/api/net/contains", json={"cidr": "10.0.0.0/24", "ip": "10.0.0.200"}).json()["inside"] is True
    assert client.post("/api/net/contains", json={"cidr": "10.0.0.0/24", "ip": "10.0.1.1"}).json()["inside"] is False
    assert client.post("/api/net/contains", json={"cidr": "10.0.0.0/24", "ip": "bad"}).status_code == 400
    s = client.post("/api/net/summarize", json={"cidrs": ["10.0.0.0/25", "10.0.0.128/25", "10.0.1.0/24"]}).json()
    assert s["summary"] == ["10.0.0.0/23"]


# ---------------------------------------------------------------- network: config, capture
def test_config_review_finds_the_planted_mistakes_and_passes_a_clean_one(client):
    s = client.get("/api/net/config/sample").json()["text"]
    r = client.post("/api/net/config/audit", json={"text": s}).json()
    titles = " | ".join(f["title"] for f in r["findings"])
    for t in ("Telnet", "SNMP", "Clear-text", "Enable password", "HTTP management", "permits everything", "Trunks carry every VLAN"):
        assert t.lower() in titles.lower(), t
    assert r["counts"]["high"] >= 4 and r["findings"][0]["severity"] == "high" and "CIS" in r["caveat"]
    clean = """hostname R1
service password-encryption
enable algorithm-type scrypt secret xyz
aaa new-model
logging host 192.0.2.5
ntp server 192.0.2.6
banner login ^Authorised use only^
no ip http server
snmp-server community Zx9fQ2mL RO
line vty 0 4
 transport input ssh
"""
    c = client.post("/api/net/config/audit", json={"text": clean}).json()
    assert c["counts"].get("high", 0) == 0 and c["counts"].get("medium", 0) == 0
    assert client.post("/api/net/config/audit", json={"text": "  "}).status_code == 400


def test_capture_reader_sees_the_handshake_and_the_scan(client):
    text = client.get("/api/net/capture/sample").json()["text"]
    r = client.post("/api/net/capture/read", json={"text": text}).json()
    assert r["protocols"]["TCP"] == 12 and r["protocols"]["ARP"] == 1 and r["protocols"]["ICMP"] == 2 and r["protocols"]["UDP"] == 1
    assert r["handshakes_completed"] == 1
    assert any("203.0.113.9" in f["title"] and "6 different ports" in f["title"] for f in r["findings"])
    assert r["top_sources"][0]["ip"] == "192.0.2.50" or r["top_sources"][0]["ip"] == "203.0.113.9"
    assert "Leads" in r["caveat"]
    assert client.post("/api/net/capture/read", json={"text": "hello world"}).status_code == 400


# ---------------------------------------------------------------- network: DNS and TCP (no real network)
def fake_resolver(mapping):
    def fn(host, port=None, **kw):
        if host not in mapping:
            raise socket.gaierror("nope")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, 0)) for a in mapping[host]]
    return fn


def test_dns_lookup_reports_addresses_and_scope():
    r = netlab.dns_lookup("example.com", resolver=fake_resolver({"example.com": ["93.184.216.34", "10.0.0.5"]}))
    assert [(a["address"], a["scope"]) for a in r["addresses"]] == [("93.184.216.34", "public"), ("10.0.0.5", "private")]
    with pytest.raises(netlab.NetError):
        netlab.dns_lookup("http://example.com/x")
    with pytest.raises(netlab.NetError) as e:
        netlab.dns_lookup("missing.example", resolver=fake_resolver({}))
    assert e.value.status == 502


def test_tcp_check_states_and_private_refusal(monkeypatch):
    res = fake_resolver({"site.example": ["93.184.216.34"], "lan.example": ["192.168.1.5"]})

    class S:
        def close(self): pass

    ok = netlab.tcp_check("site.example", 443, resolver=res, connector=lambda a, t: S())
    assert ok["state"] == "open" and ok["service"] == "HTTPS"

    def refuse(a, t): raise ConnectionRefusedError()
    def slow(a, t): raise socket.timeout()
    assert netlab.tcp_check("site.example", 81, resolver=res, connector=refuse)["state"] == "closed"
    assert netlab.tcp_check("site.example", 81, resolver=res, connector=slow)["state"].startswith("filtered")
    with pytest.raises(netlab.NetError):
        netlab.tcp_check("lan.example", 443, resolver=res, connector=lambda a, t: S())
    with pytest.raises(netlab.NetError):
        netlab.tcp_check("site.example", 70000, resolver=res)


def test_network_checks_are_rate_limited(client, monkeypatch):
    from app.routers import net
    net._hits.clear()
    monkeypatch.setattr(netlab, "dns_lookup", lambda h: {"host": h, "addresses": []})
    codes = [client.post("/api/net/dns", json={"host": "example.com"}).status_code for _ in range(14)]
    assert codes[:12] == [200] * 12 and codes[12] == 429
    net._hits.clear()


def test_calculators(client):
    t = client.post("/api/net/transfer", json={"size_gb": 100, "mbps": 1000, "efficiency_pct": 80}).json()
    assert t["seconds"] == 1000.0 and "minutes" in t["human"]
    b = client.post("/api/net/bdp", json={"mbps": 1000, "rtt_ms": 80, "window_kb": 64}).json()
    assert b["bdp_bytes"] == 10_000_000 and b["window_is_the_limit"] and b["window_limited_mbps"] == pytest.approx(6.55, abs=0.01)
    assert not client.post("/api/net/bdp", json={"mbps": 10, "rtt_ms": 1, "window_kb": 64}).json()["window_is_the_limit"]
    assert client.post("/api/net/transfer", json={"size_gb": -1, "mbps": 10}).status_code == 400


def test_reference_tables(client):
    r = client.get("/api/net/reference").json()
    assert any(p["port"] == 3389 and "VPN" in p["note"] for p in r["ports"]) and [o["layer"] for o in r["osi"]] == [7, 6, 5, 4, 3, 2, 1]
    assert set(r["commands"]) == {"Windows (cmd / PowerShell)", "Linux / macOS", "Cisco IOS (read-only)"} and len(r["method"]) >= 6


# ---------------------------------------------------------------- IT: tickets
def test_ticket_lifecycle_sla_and_checklist(client):
    t = client.post("/api/it/tickets", json={"title": "Wi-Fi drops", "category": "network", "priority": "urgent", "requester": "Dana", "note": "since Monday"}).json()
    assert t["status"] == "open" and t["sla_hours"] == 4 and len(t["checklist"]) == 5 and t["timeline"][0]["text"].startswith("Opened")
    p = client.patch(f"/api/it/tickets/{t['id']}", json={"tick": {"index": 0, "done": True}, "note": "Checked the switch", "status": "in_progress"}).json()
    assert p["checklist"][0]["done"] and p["status"] == "in_progress" and len(p["timeline"]) == 3
    r = client.patch(f"/api/it/tickets/{t['id']}", json={"status": "resolved"}).json()
    assert r["resolved_at"] and not r["is_open"] and not r["breached"] and r["hours_left"] is None
    s = client.get("/api/it/tickets").json()["stats"]
    assert s["open"] == 0 and s["mean_hours_to_resolve"] is not None and s["resolved_within_sla_pct"] == 100
    assert client.patch(f"/api/it/tickets/{t['id']}", json={"tick": {"index": 99}}).status_code == 400
    assert client.patch(f"/api/it/tickets/{t['id']}", json={"status": "bogus"}).status_code == 400
    assert client.post("/api/it/tickets", json={"title": " ", "category": "network", "priority": "low"}).status_code == 400
    assert client.post("/api/it/tickets", json={"title": "x", "category": "alien", "priority": "low"}).status_code == 400
    assert client.delete(f"/api/it/tickets/{t['id']}").status_code == 200 and client.get("/api/it/tickets").json()["tickets"] == []


def test_sla_breach_is_computed_from_elapsed_time(client):
    from app.services import state
    t = client.post("/api/it/tickets", json={"title": "Old one", "category": "email", "priority": "high"}).json()
    state.run("UPDATE it_tickets SET opened_at = '2020-01-01 00:00:00' WHERE id = ?", (t["id"],))
    d = client.get("/api/it/tickets").json()
    assert d["tickets"][0]["breached"] and d["tickets"][0]["hours_left"] < 0 and d["stats"]["breached_open"] == 1


def test_tickets_are_per_workspace(client):
    client.post("/api/it/tickets", json={"title": "Practice only", "category": "other", "priority": "low"})
    client.post("/api/workspaces/active", json={"name": "real"})
    assert client.get("/api/it/tickets").json()["tickets"] == []


# ---------------------------------------------------------------- IT: inventory
def test_inventory_crud_and_warranty_flags(client):
    from datetime import timedelta
    past = date(2020, 1, 1)
    soon = (date.today() + timedelta(days=30)).isoformat()
    far = (date.today() + timedelta(days=400)).isoformat()
    a = client.post("/api/it/assets", json={"hostname": "LAPTOP-01", "kind": "laptop", "os": "Windows 11", "owner": "Dana", "warranty_end": soon}).json()
    client.post("/api/it/assets", json={"hostname": "SRV-01", "kind": "server", "os": "Ubuntu 24.04", "warranty_end": far})
    client.post("/api/it/assets", json={"hostname": "OLD-PC", "kind": "desktop", "warranty_end": past.isoformat()})
    d = client.get("/api/it/assets").json()
    by = {x["hostname"]: x for x in d["assets"]}
    assert by["LAPTOP-01"]["warranty_state"] == "expiring" and by["SRV-01"]["warranty_state"] == "ok" and by["OLD-PC"]["warranty_state"] == "expired"
    assert d["stats"]["warranty_expiring"] == 1 and d["stats"]["warranty_expired"] == 1 and d["stats"]["by_kind"]["laptop"] == 1
    assert client.post("/api/it/assets", json={"hostname": "laptop-01", "kind": "laptop"}).status_code == 409
    assert client.post("/api/it/assets", json={"hostname": "X", "kind": "toaster"}).status_code == 400
    assert client.post("/api/it/assets", json={"hostname": "Y", "kind": "laptop", "warranty_end": "soon"}).status_code == 400
    u = client.patch(f"/api/it/assets/{a['id']}", json={"status": "retired"}).json()
    assert u["status"] == "retired" and client.get("/api/it/assets").json()["stats"]["warranty_expiring"] == 0
    assert client.delete(f"/api/it/assets/{a['id']}").status_code == 200 and client.delete(f"/api/it/assets/{a['id']}").status_code == 404


# ---------------------------------------------------------------- IT: events, checklists, calculators
def test_event_reader_flags_the_takeover_pattern(client):
    text = client.get("/api/it/events/sample").json()["text"]
    r = client.post("/api/it/events/read", json={"text": text}).json()
    ids = {t["id"]: t for t in r["table"]}
    assert ids[4625]["count"] == 6 and ids[4625]["meaning"] == "Failed logon" and ids[1102]["level"] == "alert"
    titles = [f["title"] for f in r["findings"]]
    assert r["findings"][0]["severity"] == "high" and any("successful logon came from an address that had failed" in t for t in titles)
    assert any("audit log was cleared" in t for t in titles) and any("6 failed logons" in t for t in titles)
    assert "Leads" in r["caveat"]


def test_event_reader_accepts_plain_lines_and_rejects_junk(client):
    r = client.post("/api/it/events/read", json={"text": "Event ID: 4740 A user account was locked out. Account Name: bob\nEvent ID: 99999 something"}).json()
    assert r["events"] == 2 and {t["id"]: t["level"] for t in r["table"]} == {4740: "watch", 99999: "unknown"}
    assert client.post("/api/it/events/read", json={"text": "nothing useful here"}).status_code == 400


def test_checklists_tick_and_reset(client):
    d = client.get("/api/it/checklists").json()
    assert {l["id"] for l in d["lists"]} == {"onboard", "offboard", "new_pc", "outage"}
    d = client.post("/api/it/checklists/offboard", json={"index": 0, "done": True}).json()
    off = next(l for l in d["lists"] if l["id"] == "offboard")
    assert off["items"][0]["done"] and "Disable the account" in off["items"][0]["text"] and not off["items"][1]["done"]
    assert client.post("/api/it/checklists/offboard", json={"index": 99}).status_code == 400
    assert client.post("/api/it/checklists/nope", json={"index": 0}).status_code == 404
    d = client.post("/api/it/checklists/offboard", json={"reset": True}).json()
    assert not any(i["done"] for i in next(l for l in d["lists"] if l["id"] == "offboard")["items"])


def test_capacity_availability_and_raid(client):
    c = itlab.capacity(700, 1000, 25, 80, today=date(2026, 1, 1))
    assert c["used_pct"] == 70.0 and c["reach_warning"]["months"] == 4.0 and c["reach_full"]["months"] == 12.0 and c["reach_warning"]["date"] < c["reach_full"]["date"]
    assert itlab.capacity(900, 1000, 0, 80, today=date(2026, 1, 1))["reach_full"] is None
    assert client.post("/api/it/capacity", json={"used_gb": 2000, "total_gb": 1000, "growth_gb_per_month": 1}).status_code == 400
    a = client.post("/api/it/availability", json={"pct": 99.9}).json()
    assert a["per_year_hours"] == pytest.approx(8.77, abs=0.01) and a["nines"] == "about 3 nine(s)"
    assert client.post("/api/it/availability", json={"pct": 99}).json()["nines"] == "about 2 nine(s)"
    r5 = client.post("/api/it/raid", json={"level": "5", "disks": 4, "size_tb": 4}).json()
    assert r5["usable_tb"] == 12.0 and r5["efficiency_pct"] == 75 and "not backup" in r5["caveat"]
    assert client.post("/api/it/raid", json={"level": "RAID6", "disks": 6, "size_tb": 2}).json()["usable_tb"] == 8.0
    assert client.post("/api/it/raid", json={"level": "10", "disks": 6, "size_tb": 2}).json()["usable_tb"] == 6.0
    assert client.post("/api/it/raid", json={"level": "5", "disks": 2, "size_tb": 4}).status_code == 400
    assert client.post("/api/it/raid", json={"level": "10", "disks": 5, "size_tb": 4}).status_code == 400
    assert client.post("/api/it/raid", json={"level": "7", "disks": 5, "size_tb": 4}).status_code == 400


def test_cheats_and_methods(client):
    c = client.get("/api/it/cheats").json()
    assert "Active Directory (on-premises)" in c["groups"] and len(c["method"]) >= 5
    assert any("--dry-run" in x["cmd"] or "MIR" in x["cmd"] for x in c["groups"]["Backups and recovery"])


# ---------------------------------------------------------------- wiring into the rest of the app
@pytest.mark.parametrize("tid", ["network", "itsupport"])
def test_new_tracks_are_wired_everywhere(client, tid):
    assert client.get(f"/api/manuals/{tid}").status_code == 200
    q = client.get(f"/api/quizzes/{tid}").json()
    assert len(q["questions"]) == 6 and all("answer" not in x for x in q["questions"])
    assert client.get(f"/api/tracks/{tid}/dashboard").json()["ideas"]
    assert any(c["id"] == tid for c in client.get("/api/dataset").json()["careers"])
    ag = client.get(f"/api/agents/{tid}").json()
    assert ag["name"].endswith("agent")
    from app.services import agent_evals
    assert len(agent_evals.CASES[tid]) == 3
    plan = client.get("/api/company").json()
    assert any(d["id"] == tid for d in plan["disciplines"]) and any(i["discipline"] == tid for p in plan["phases"] for i in p["deliverables"])


def test_tool_map_has_the_new_groups_and_keeps_offensive_tools_out(client):
    tm = client.get("/api/toolmap").json()
    cats = {c["category"]: c["tools"] for c in tm["categories"]}
    assert {"Network engineering", "IT support and administration"} <= set(cats)
    status = {t["tool"]: t["status"] for t in cats["Network engineering"]}
    assert status["Subnet calculators (ipcalc, subnetting tools)"] == "built" and status["Nmap and other scanners"] == "taught"
    assert all(t["status"] != "built" for t in cats["Network engineering"] if "Cloud" in t["tool"])
