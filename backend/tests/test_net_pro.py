from fastapi.testclient import TestClient

from app.main import app
from app.services import agent_tools, net_pro

c = TestClient(app)


def calc(kind, **b):
    return c.post(f"/api/netpro/calc/{kind}", json=b)


def test_ospf_stp_ipv6():
    assert calc("ospf", link_mbps=1000).json()["cost"] == 1
    assert calc("ospf", link_mbps=10, reference_mbps=1000).json()["cost"] == 100
    r = calc("stp", bridges="A,32768,00:00:00:00:00:02\nB,32768,00:00:00:00:00:01\nC,4096,00:00:00:00:00:09").json()
    assert r["root"] == "C"
    assert calc("stp", bridges="A,100,00:00:00:00:00:02\nB,32768,00:00:00:00:00:01").status_code == 400
    p = calc("ipv6", prefix="2001:db8:abcd::/48", subnet_prefix=64, count=2).json()
    assert p["first"] == ["2001:db8:abcd::/64", "2001:db8:abcd:1::/64"]
    assert calc("ipv6", prefix="10.0.0.0/8").status_code == 400
    assert calc("eui64", mac="00:1a:2b:3c:4d:5e").json()["address"] == "fe80::21a:2bff:fe3c:4d5e"


def test_poe_fiber_wifi_tcp():
    r = calc("poe", switch_watts=370, devices="Cam,12.95,8\nAP,at,4").json()
    assert r["total_w"] == 223.6 and "Comfortable" in r["verdict"]
    assert "Over budget" in calc("poe", switch_watts=100, devices="AP,bt4,2").json()["verdict"]
    f = calc("fiber", length_km=2, wavelength="1310", connectors=2).json()
    assert f["total_loss_db"] == 1.7 and f["ok"]
    assert not calc("fiber", length_km=60, wavelength="1310", connectors=4).json()["ok"]
    assert calc("fspl", freq_mhz=2400, distance_m=100).json()["free_space_loss_db"] == 80.0
    assert calc("link", tx_dbm=20, tx_gain_dbi=3, rx_gain_dbi=3, freq_mhz=5800, distance_m=200, rx_sensitivity_dbm=-80).json()["ok"] and not calc("link", tx_dbm=20, tx_gain_dbi=3, rx_gain_dbi=3, freq_mhz=5800, distance_m=300, rx_sensitivity_dbm=-80).json()["ok"]
    assert calc("tcp", rtt_ms=50, loss_pct=1).json()["max_throughput_mbps"] == 2.85
    assert calc("tcp", rtt_ms=0, loss_pct=1).status_code == 400
    assert c.post("/api/netpro/calc/nope", json={}).status_code == 400


def test_firewall_review_and_reference():
    r = c.post("/api/netpro/firewall", json={"text": "permit ip any any\nallow tcp any any eq 3389\nallow tcp any any eq 445"}).json()
    probs = " ".join(f["problem"] for f in r["findings"])
    assert r["counts"]["high"] >= 3 and "Remote Desktop" in probs
    assert c.post("/api/netpro/firewall", json={"text": "x"}).status_code == 400
    assert net_pro.reference()["vpn"] and c.get("/api/netpro/reference").json()["qos"]


def test_agent_tools():
    t, e = agent_tools.run_tool("network", {"tool": "fiber_budget", "args": {"length_km": 1}})
    assert not e
    t, e = agent_tools.run_tool("network", {"tool": "firewall_review", "args": {"text": "permit ip any any"}})
    assert not e and "allow-everything" in t
    t, e = agent_tools.run_tool("network", {"tool": "ipv6_plan", "args": {"prefix": "2001:db8::/48", "count": 2}})
    assert not e
