import pytest

from app.services import cpe_sim as sim, veh_decode as vd, known_errors
from app.services.cpe_lab import CpeError


def test_logic_adder_and_counter():
    n, s = sim.LOGIC_SAMPLES["adder"]
    r = sim.logic_circuit(n, s, 8)
    assert r
    with pytest.raises(CpeError):
        sim.logic_circuit("INPUT A\nX = NOT(Y)\nY = NOT(X)", "A: 0", 2)


def test_cpu_programs():
    assert sim.cpu_run(sim.CPU_SAMPLES["sum"])["registers"][0] == 15
    assert sim.cpu_run(sim.CPU_SAMPLES["multiply"])["registers"][0] == 42
    with pytest.raises(CpeError):
        sim.cpu_run("BOGUS R0")


def test_circuits():
    d = sim.circuit_dc(sim.NET_SAMPLES["divider"])
    assert "out" in str(d)
    assert sim.circuit_transient(sim.NET_SAMPLES["rc"], 0.005, 50)
    with pytest.raises(CpeError):
        sim.circuit_dc("R1 a b")


def test_cache():
    r = sim.cache_trace(sim.CACHE_SAMPLE, 256, 16, 2, "LRU")
    assert r
    with pytest.raises(CpeError):
        sim.cache_trace("0 4", 100, 16, 2)


def test_vehicle_decoders():
    c = vd.can_signals(vd.CAN_SAMPLE["data"], vd.CAN_SAMPLE["signals"])
    assert c["signals"][0]["value"] == 2822.5 and c["signals"][1]["value"] == -40
    assert vd.j1939("0CF00400", "00 00 00 A0 0F 00 00 00")["signals"][0]["value"] == 500
    assert vd.dtc("P0301")["meaning"] == "Cylinder 1 misfire"
    assert vd.obd_pid("0C", "1A F8")["value"] == 1726
    assert vd.cp_duty(53)["amps"] == 31.8 and vd.cp_duty(5)["amps"] is None
    assert vd.cp_state(5.8)["state"] == "C"
    with pytest.raises(CpeError):
        vd.dtc("zzzz")
    with pytest.raises(CpeError):
        vd.cp_duty(120)


def test_slips_and_endpoints(client):
    assert len(sim.SLIPS) == 3 and vd.SLIPS
    for m in ("cpe_sim", "veh_decode"):
        assert m in known_errors.SOURCES
    ref = client.get("/api/cpesim/reference").json()
    r = client.post("/api/cpesim/cpu", json={"source": ref["cpu_samples"]["sum"]})
    assert r.status_code == 200
    assert client.post("/api/cpesim/dtc", json={"code": "zz"}).status_code == 400
    assert client.post("/api/cpesim/isotp", json={"frames": ref["vehicle"]["isotp_sample"]}).status_code == 200
