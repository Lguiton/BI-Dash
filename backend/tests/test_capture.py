import base64

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import capture, net_pcap

client = TestClient(app)
sc = pytest.importorskip("scapy.all")


def fake_packets(n=12):
    out = []
    for i in range(n):
        out.append(sc.Ether(src="aa:bb:cc:00:00:01", dst="aa:bb:cc:00:00:02") / sc.IP(src="192.168.1.10", dst="93.184.216.34") / sc.TCP(sport=40000 + i, dport=443, flags="S") / (b"x" * 300))
    out.append(sc.Ether() / sc.IP(src="192.168.1.10", dst="192.168.1.1") / sc.UDP(sport=5353, dport=53) / sc.DNS(rd=1, qd=sc.DNSQR(qname="example.com")))
    return out


@pytest.fixture
def fake_sniff(monkeypatch):
    seen = {}

    def sniff(**kw):
        seen.update(kw)
        return fake_packets()
    monkeypatch.setattr(sc, "sniff", sniff)
    monkeypatch.setattr(capture, "interfaces", lambda: [{"name": "eth0", "label": "eth0"}])
    return seen


def test_status_shape():
    s = client.get("/api/capture/status").json()
    assert {"available", "system", "in_wsl", "admin", "interfaces", "install", "message"} <= set(s)
    assert s["install"]["windows"] and s["install"]["linux"]


def test_requires_confirmation_and_limits(fake_sniff):
    base = {"iface": "eth0", "seconds": 5, "count": 100}
    assert client.post("/api/capture/run", json=base).status_code == 400
    ok = {**base, "confirm": True}
    assert client.post("/api/capture/run", json={**ok, "seconds": 600}).status_code == 400
    assert client.post("/api/capture/run", json={**ok, "count": 999999}).status_code == 400
    assert client.post("/api/capture/run", json={**ok, "iface": "wlan9"}).status_code == 400
    assert client.post("/api/capture/run", json={**ok, "filter": "tcp; rm -rf /"}).status_code == 400


def test_capture_runs_and_is_summarised(fake_sniff):
    r = client.post("/api/capture/run", json={"iface": "eth0", "seconds": 5, "count": 100, "filter": "tcp port 443", "confirm": True})
    assert r.status_code == 200
    j = r.json()
    assert j["captured"] == 13 and fake_sniff["filter"] == "tcp port 443" and fake_sniff["timeout"] == 5
    assert j["summary"]["packets"] == 13
    raw = base64.b64decode(j["pcap_base64"])
    assert raw[:4] in (b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4")
    # headers only: no packet holds more than the snap length
    assert len(raw) < 24 + 13 * (16 + 140)


def test_full_packets_when_asked(fake_sniff):
    j = client.post("/api/capture/run", json={"iface": "eth0", "seconds": 5, "count": 100, "confirm": True, "headers_only": False}).json()
    assert len(base64.b64decode(j["pcap_base64"])) > 24 + 12 * 340


def test_no_packets_is_a_message(monkeypatch):
    monkeypatch.setattr(sc, "sniff", lambda **kw: [])
    monkeypatch.setattr(capture, "interfaces", lambda: [{"name": "eth0", "label": "eth0"}])
    r = client.post("/api/capture/run", json={"iface": "eth0", "seconds": 1, "count": 10, "confirm": True})
    assert r.status_code == 400 and "No packets" in r.json()["detail"]


def test_permission_error_is_explained(monkeypatch):
    def boom(**kw):
        raise PermissionError("denied")
    monkeypatch.setattr(sc, "sniff", boom)
    monkeypatch.setattr(capture, "interfaces", lambda: [{"name": "eth0", "label": "eth0"}])
    r = client.post("/api/capture/run", json={"iface": "eth0", "seconds": 1, "count": 10, "confirm": True})
    assert r.status_code == 403 and "administrator" in r.json()["detail"]
