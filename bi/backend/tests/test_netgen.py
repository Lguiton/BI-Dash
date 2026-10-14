from app.services import honeypot as hp, net_gen as ng

VL = [{"id": 10, "name": "HR", "subnet": "192.168.10.0/24", "ports": ["fa0/1", "fa0/2"]}, {"id": 20, "name": "IT", "subnet": "192.168.20.0/24", "ports": ["fa0/3"]}]


def plan(client, **kw):
    return client.post("/api/netgen/plan", json={"vlans": VL} | kw)


def test_plan_generates_matching_switch_and_router_config(client):
    d = plan(client, loopback="1.1.1.1", native=99).json()
    sw, rt = "\n".join(d["switch_config"]), "\n".join(d["router_config"])
    assert "switchport access vlan 10" in sw and "switchport trunk allowed vlan 10,20" in sw and "switchport trunk native vlan 99" in sw
    assert "encapsulation dot1Q 10" in rt and "ip address 192.168.20.1 255.255.255.0" in rt and "interface g0/0.20" in rt
    assert "ip address 1.1.1.1 255.255.255.255" in "\n".join(d["loopback_config"]) and "route to it" in "\n".join(d["loopback_config"])
    assert not any("default VLAN 1" in w and "Native" in w for w in d["warnings"])
    assert any("Native VLAN is the default" in w for w in plan(client).json()["warnings"])


def test_plan_svi_style_and_optional_encapsulation_line(client):
    d = plan(client, style="svi").json()
    assert "ip routing" in "\n".join(d["router_config"]) and "interface vlan 10" in "\n".join(d["router_config"])
    assert "trunk encapsulation" not in "\n".join(plan(client).json()["switch_config"])
    assert "trunk encapsulation dot1q" in "\n".join(plan(client, encapsulation_line=True).json()["switch_config"])


def test_plan_rejects_bad_input(client):
    bad = lambda v, **k: client.post("/api/netgen/plan", json={"vlans": v} | k).status_code
    assert bad([{"id": 1003, "name": "X", "subnet": "10.0.0.0/24"}]) == 400            # reserved
    assert bad([{"id": 5000, "name": "X", "subnet": "10.0.0.0/24"}]) == 400
    assert bad([{"id": 10, "name": "A", "subnet": "10.0.0.0/24"}, {"id": 20, "name": "B", "subnet": "10.0.0.128/25"}]) == 400   # overlap
    assert bad([{"id": 10, "name": "A", "subnet": "10.0.0.0/24"}, {"id": 10, "name": "B", "subnet": "10.0.1.0/24"}]) == 400
    assert bad([{"id": 10, "name": "has space", "subnet": "10.0.0.0/24"}]) == 400
    assert bad([{"id": 10, "name": "A", "subnet": "10.0.0.0/24", "gateway": "10.0.1.1"}]) == 400
    assert bad([{"id": 10, "name": "A", "subnet": "10.0.0.0/24", "ports": ["g0/1"]}]) == 400                   # trunk port reused
    assert bad([{"id": 10, "name": "A", "subnet": "10.0.0.0/24", "ports": ["fa0/1"]}, {"id": 20, "name": "B", "subnet": "10.0.1.0/24", "ports": ["fa0/1"]}]) == 400
    assert bad(VL, loopback="192.168.10.5") == 400
    assert bad(VL, trunk_port="; reload") == 400
    assert client.post("/api/netgen/plan", json={"vlans": VL, "router_name": "R1; evil"}).status_code == 422


def test_trunk_check_finds_the_four_classic_faults(client):
    a = "\n".join(plan(client, native=99).json()["switch_config"])
    ok = client.post("/api/netgen/trunk", json={"a": a, "b": a}).json()
    assert ok["ok"] and not any(f["severity"] == "bad" for f in ok["findings"])
    b = a.replace("native vlan 99", "native vlan 1").replace("allowed vlan 10,20", "allowed vlan 10")
    r = client.post("/api/netgen/trunk", json={"a": a, "b": b}).json()
    t = {f["title"] for f in r["findings"] if f["severity"] == "bad"}
    assert {"Native VLAN mismatch", "Allowed VLAN lists differ"} <= t and not r["ok"]
    auto = "interface g0/1\n switchport mode dynamic auto\n"
    assert any(f["title"] == "Both ends are dynamic auto" for f in client.post("/api/netgen/trunk", json={"a": auto, "b": auto}).json()["findings"])
    assert client.post("/api/netgen/trunk", json={"a": "hostname x", "b": a}).status_code == 400


def test_route_selection_order(client):
    r = client.post("/api/netgen/route", json={"destination": "10.1.2.3", "routes": [{"prefix": "10.0.0.0/8", "protocol": "static"}, {"prefix": "10.1.0.0/16", "protocol": "rip", "metric": 2}, {"prefix": "10.1.0.0/16", "protocol": "ospf", "metric": 20}]}).json()
    assert r["winner"] == [3]                                        # longest prefix, then AD 110 beats RIP 120; the /8 static never wins
    none = client.post("/api/netgen/route", json={"destination": "172.16.0.1", "routes": [{"prefix": "10.0.0.0/8", "protocol": "ospf"}]}).json()
    assert none["winner"] is None
    assert client.post("/api/netgen/route", json={"destination": "x", "routes": [{"prefix": "10.0.0.0/8", "protocol": "ospf"}]}).status_code == 400
    assert client.post("/api/netgen/route", json={"destination": "10.0.0.1", "routes": [{"prefix": "10.0.0.0/8", "protocol": "magic"}]}).status_code == 400
    assert client.post("/api/netgen/route", json={"destination": "10.0.0.1", "routes": [{"prefix": "10.0.0.0/8", "ad": 999}]}).status_code == 400


def test_cable_and_reference(client):
    assert client.post("/api/netgen/cable", json={"speed_gbps": 10, "distance_m": 90}).json()["pick"] == "Cat 6a"
    assert client.post("/api/netgen/cable", json={"speed_gbps": 1, "distance_m": 50}).json()["pick"].startswith("Cat 5e")
    assert client.post("/api/netgen/cable", json={"speed_gbps": 10, "distance_m": 500}).status_code == 400
    ref = client.get("/api/netgen/reference").json()
    assert len(ref["devices"]) == 12 and len(ref["dora"]) == 4 and ref["slips"] and ref["admin_distance"][0] == {"source": "connected", "ad": 0}
    assert any(p["name"] == "OSPF" and p["ad"] == "110" for p in ref["protocols"])
    assert ng.AD["ebgp"] == 20 and ng.AD["ibgp"] == 200 and ng.AD["eigrp"] == 90


def test_honeypot_counts_classifies_and_defangs(client):
    r = client.post("/api/honeypot/analyze", json={"text": hp.SAMPLE}).json()
    assert r["format"] == "json" and r["login_attempts"] == 5 and r["logins_succeeded"] == 1 and r["unique_ips"] == 3
    assert r["top_ips"][0]["value"] == "203.0.113.7"
    cls = {c["class"] for c in r["command_classes"]}
    assert {"download", "execute", "recon"} <= cls
    assert r["urls_defanged"][0]["value"].startswith("hxxp://") and "http://" not in str(r["urls_defanged"])
    assert any("private" in f["title"].lower() for f in r["findings"])


def test_honeypot_text_format_and_errors(client):
    t = "[2026-01-10 14:22:12] [SSHService] login attempt [root/123456] failed\n[2026-01-10 14:22:18] CMD: rm -rf /\n"
    r = client.post("/api/honeypot/analyze", json={"text": t}).json()
    assert r["format"] == "text" and r["login_attempts"] == 1 and any(c["class"] == "destructive" for c in r["command_classes"])
    assert client.post("/api/honeypot/analyze", json={"text": "hello world"}).status_code == 400
    assert client.post("/api/honeypot/analyze", json={"text": "  "}).status_code == 400
    assert hp.classify("ls -la") == ["recon"] and hp.defang("https://a.b/c") == "hxxps://a[.]b/c"
    assert client.get("/api/honeypot/reference").json()["sample"]
