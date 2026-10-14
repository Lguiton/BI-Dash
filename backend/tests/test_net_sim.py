import base64
import struct

import pytest

from app.services import known_errors, net_pcap as pc, net_sim as ns
from app.services.netlab import NetError


def test_switch_learns_source_and_isolates_vlans():
    r = ns.switch(**ns.SWITCH_SAMPLE)
    s = r["steps"]
    assert s[0]["action"].startswith("flood") and "3" not in s[0]["out_ports"]
    assert s[1]["action"] == "forward to 1"
    assert s[3]["out_ports"] == ["4"]
    assert {(t["vlan"], t["port"]) for t in r["table"]} >= {(10, "1"), (10, "2")}
    with pytest.raises(NetError):
        ns.switch("1 access 10", "9 aa:00:00:00:00:01 aa:00:00:00:00:02")
    with pytest.raises(NetError):
        ns.switch("1 access 10", "1 zz ff:ff:ff:ff:ff:ff")


def test_stp_root_and_blocking():
    r = ns.stp(**ns.STP_SAMPLE)
    assert r["root"] == "SW1" and r["blocked"] == 1
    r2 = ns.stp("A 32768 00:00:00:00:00:09\nB 4096 00:00:00:00:00:08", "A B 5")
    assert r2["root"] == "B" and r2["blocked"] == 0
    with pytest.raises(NetError):
        ns.stp("A 100 00:00:00:00:00:01\nB 0 00:00:00:00:00:02", "A B 1")
    with pytest.raises(NetError):
        ns.stp("A 0 00:00:00:00:00:01\nB 0 00:00:00:00:00:02\nC 0 00:00:00:00:00:03", "A B 1")


def test_spf_equal_cost():
    r = ns.spf(**ns.SPF_SAMPLE)
    row = {x["to"]: x for x in r["routes"]}
    assert row["R4"]["cost"] == 20 and row["R4"]["ecmp"] and row["R5"]["cost"] == 25
    with pytest.raises(NetError):
        ns.spf("A B 1", "Z")


def test_bgp_order():
    r = ns.bgp(**ns.BGP_SAMPLE)
    assert r["best"] == "B" and r["decided_by"] == "Highest local preference"
    r = ns.bgp("A | 0 | 100 | 1 2 | igp | 0 | ebgp | 10 | 1.1.1.1\nB | 0 | 100 | 3 | igp | 0 | ebgp | 10 | 2.2.2.2")
    assert r["best"] == "B" and r["decided_by"] == "Shortest AS path"
    with pytest.raises(NetError):
        ns.bgp("A | 0")


def test_acl_first_match_and_shadow():
    r = ns.acl(**ns.ACL_SAMPLE)
    assert [x["result"] for x in r["results"]] == ["permit", "deny", "deny", "permit"]
    assert r["warnings"] and "Line 4" in r["warnings"][0]
    r = ns.acl("permit tcp any any eq 80", "udp 1.1.1.1 2.2.2.2 5 53")
    assert r["results"][0]["rule"].startswith("implicit")
    with pytest.raises(NetError):
        ns.acl("allow ip any any", "tcp 1.1.1.1 2.2.2.2 1 2")


def test_nat_pat():
    r = ns.nat(**ns.NAT_SAMPLE)
    assert r["flows"][0]["result"].endswith(":1024") and r["flows"][1]["result"].endswith(":1025")
    assert not r["flows"][2]["new_entry"] and r["flows"][3]["result"] == "not translated"
    with pytest.raises(NetError):
        ns.nat("192.168.1.0/24", "10.1.1.1", "tcp 192.168.1.2 1 8.8.8.8 53")


def _pcap():
    def tcp(sp, dp, fl, seq=1, payload=b""):
        t = struct.pack(">HHIIBBHHH", sp, dp, seq, 0, 5 << 4, fl, 1000, 0, 0) + payload
        ip = struct.pack(">BBHHHBBH4s4s", 0x45, 0, 20 + len(t), 0, 0, 64, 6, 0, bytes((10, 0, 0, 1)), bytes((10, 0, 0, 2)))
        return b"\0" * 6 + b"\1" * 6 + b"\x08\x00" + ip + t
    pk = [tcp(40000, 80, 2), tcp(40001, 81, 2), tcp(40000, 80, 0x18, 5, b"hi"), tcp(40000, 80, 0x18, 5, b"hi")]
    b = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    for i, p in enumerate(pk):
        b += struct.pack("<IIII", i, 0, len(p), len(p)) + p
    return b


def test_pcap_reader():
    r = pc.read(base64.b64encode(_pcap()).decode())
    assert r["packets"] == 4 and r["protocols"][0] == ("TCP", 4)
    assert any("no SYN-ACK" in f for f in r["findings"]) and any("repeat a sequence" in f for f in r["findings"])
    for bad in ("", base64.b64encode(b"not a capture").decode()):
        with pytest.raises(NetError):
            pc.read(bad)


def test_endpoints_and_sources(client):
    ref = client.get("/api/netsim/reference").json()
    assert set(ref["samples"]) == {"switch", "stp", "spf", "bgp", "acl", "nat"}
    assert client.post("/api/netsim/stp", json=ref["samples"]["stp"]).status_code == 200
    assert client.post("/api/netsim/acl", json={"rules": "x", "packets": "y"}).status_code == 400
    r = client.post("/api/netsim/pcap", json={"data": base64.b64encode(_pcap()).decode()})
    assert r.status_code == 200 and r.json()["packets"] == 4
    for m in ("net_sim", "net_pcap"):
        assert m in known_errors.SOURCES
    assert len(ns.SLIPS) == 5
