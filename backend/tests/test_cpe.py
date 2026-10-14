import pytest

from app.services import auto_elec as ae, cpe_lab as cl, known_errors


def test_numbers_twos_complement_and_overflow():
    r = cl.convert("-45", 10, 8)
    assert r["twos_complement"] == "11010011" and r["hex"] == "-2D"
    assert cl.convert("FF", 16, 8)["decimal"] == 255
    assert cl.convert("200", 10, 8)["steps"][0].startswith("200 does not fit")
    assert cl.convert("-129", 10, 8)["twos_complement"] is None
    a = cl.signed_add(100, 50, 8)
    assert a["overflow"] and a["result"] == -106
    assert not cl.signed_add(-100, 50, 8)["overflow"]
    assert cl.signed_add(-100, -50, 8)["overflow"]
    assert cl.signed_add(5, 3, 8, subtract=True)["result"] == 2
    for bad in (("zz", 10, 8), ("", 10, 8), ("12", 1, 8), ("1", 10, 1)):
        with pytest.raises(cl.CpeError):
            cl.convert(*bad)
    with pytest.raises(cl.CpeError):
        cl.signed_add(200, 1, 8)


def test_float_storage():
    r = cl.ieee754(0.1)
    assert r["hex"] == "3DCCCCCD" and r["error"] != 0 and r["exponent_value"] == -4
    assert cl.ieee754(0.5)["error"] == 0
    with pytest.raises(cl.CpeError):
        cl.ieee754(1e300)


def test_logic_simplifies_and_checks_equivalence():
    assert cl.logic("A AND B OR A AND NOT B")["minimal_sum_of_products"] == "A"
    assert cl.logic("A XOR B")["minimal_sum_of_products"] == "A'B + AB'"
    assert cl.logic("A'B + AB'")["minimal_sum_of_products"] == "A'B + AB'"
    assert cl.logic("A OR NOT A")["result_is"].startswith("always 1")
    assert cl.logic("A AND NOT A")["result_is"].startswith("always 0")
    assert cl.logic("(A AND B) OR (NOT A AND C) OR (B AND C)")["minimal_sum_of_products"] == "A'C + AB"
    assert cl.equivalent("NOT(A AND B)", "NOT A OR NOT B")["equivalent"]
    e = cl.equivalent("NOT(A OR B)", "NOT A OR NOT B")
    assert not e["equivalent"] and e["differences"]
    for bad in ("", "A AND", "(A OR B", "A $ B", "A B C D E F G"):
        with pytest.raises(cl.CpeError):
            cl.logic(bad)


def test_circuits():
    o = cl.ohm(v=12, r=4)
    assert o["current_a"] == 3 and o["power_w"] == 36
    assert cl.ohm(i=2, p=8)["resistance_ohm"] == 2
    assert cl.ohm(p=36, r=4)["voltage_v"] == pytest.approx(12)
    for bad in ((12, 3, 4, None), (12, None, None, None), (0, None, None, 5)):
        with pytest.raises(cl.CpeError):
            cl.ohm(*bad)
    assert cl.resistors("series", [100, 220])["total_ohm"] == 320
    assert cl.resistors("parallel", [100, 100])["total_ohm"] == 50
    assert cl.resistors("parallel", [100, 0])["total_ohm"] == 0
    assert cl.divider(12, 10000, 10000)["unloaded_v"] == 6
    assert cl.divider(12, 10000, 10000, 10000)["loaded_v"] == pytest.approx(4)
    assert cl.led_resistor(12, 2, 20)["next_standard_ohm_E12"] == 560
    with pytest.raises(cl.CpeError):
        cl.led_resistor(1.5, 2, 20)
    assert cl.color_code("yellow", "violet", "red")["ohms"] == 4700
    assert cl.rc_time(10000, 100)["tau_s"] == pytest.approx(1.0)


def test_architecture():
    c = cl.cache_split(32, 32768, 64, 4)
    assert (c["offset_bits"], c["index_bits"], c["tag_bits"]) == (6, 7, 19) and c["organisation"] == "4-way set associative"
    with pytest.raises(cl.CpeError):
        cl.cache_split(32, 3000, 64, 1)
    assert cl.amat(1, 5, 100)["amat"] == 6
    assert cl.amdahl(90, 10)["overall_speedup"] == pytest.approx(5.263, abs=0.01) and cl.amdahl(90, 10)["limit_if_part_infinitely_fast"] == pytest.approx(10)
    assert cl.pipeline(5, 100)["pipelined_cycles"] == 104 and cl.pipeline(5, 100, 10)["speedup"] < cl.pipeline(5, 100)["speedup"]
    assert cl.raid(5, 4, 4)["usable_tb"] == 12 and cl.raid(10, 4, 2)["usable_tb"] == 4
    with pytest.raises(cl.CpeError):
        cl.raid(5, 2, 4)


def test_wire_and_fuse_rules():
    w = ae.wire(10, 3)
    assert w["recommended"]["mm2"] == 4.0 and w["fuse_a"] == 15 and w["recommended"]["drop_pct"] < 3
    assert ae.wire(10, 3, round_trip=False)["recommended"]["mm2"] < 4.0
    assert ae.wire(300, 30)["recommended"] is None and ae.wire(300, 30)["notes"]
    h = ae.harness_check("Pump | 8 | 4 | 0.5 | 20\nHorn | 7 | 2 | 1.5 | 10\nRadio | 3 | 1 | 0.75 |")
    status = {c["circuit"]: c for c in h["circuits"]}
    assert status["Pump"]["status"] == "fix" and any("bigger than the wire" in i for i in status["Pump"]["issues"])
    assert status["Horn"]["status"] == "ok" and any("No fuse" in i for i in status["Radio"]["issues"])
    for bad in ("", "x | 1 | 1", "x | a | 1 | 1", "x | 1 | 1 | 7"):
        with pytest.raises(cl.CpeError):
            ae.harness_check(bad)


def test_can_load_and_termination():
    msgs = [{"name": "a", "bytes": 8, "per_second": 100}]
    r = ae.can_load(500, msgs)
    assert r["rows"][0]["bits_worst_case"] == 135 and r["rows"][0]["bits_no_stuffing"] == 111
    assert ae.can_load(500, [{"bytes": 8, "per_second": 5000}])["verdict"].startswith("Overloaded")
    assert ae.can_load(500, [{"bytes": 8, "per_second": 100, "extended": True}])["rows"][0]["bits_no_stuffing"] == 131
    for bad in ([], [{"bytes": 9, "per_second": 1}], [{"bytes": 8}]):
        with pytest.raises(cl.CpeError):
            ae.can_load(500, bad)
    assert "60 ohm" in ae.can_termination(60)["verdict"] and "missing" in ae.can_termination(120)["verdict"] and "Open" in ae.can_termination(5000)["verdict"]


def test_ev_maths_and_safety_limits():
    ac = ae.charge(60, 20, 80, "ac", 230, 32, 1, onboard_kw=11)
    assert ac["evse_kw"] == pytest.approx(7.36) and ac["limited_by"] == "the wall box" and ac["hours"] == pytest.approx(36 / (7.36 * 0.9), abs=0.01)
    three = ae.charge(60, 20, 80, "ac", 400, 16, 3, onboard_kw=7)
    assert three["limited_by"] == "the car's on-board charger"
    dc = ae.charge(75, 10, 80, "dc", station_kw=150, vehicle_max_kw=120)
    assert dc["used_kw"] == 120 and dc["limited_by"] == "the vehicle"
    assert ae.charge(75, 10, 100, "dc", station_kw=150, vehicle_max_kw=120)["minutes"] > dc["minutes"]
    for bad in (dict(capacity_kwh=60, start_pct=80, target_pct=20, source="ac"), dict(capacity_kwh=60, start_pct=1, target_pct=2, source="x"), dict(capacity_kwh=60, start_pct=1, target_pct=2, source="ac", phases=2)):
        with pytest.raises(cl.CpeError):
            ae.charge(**bad)
    p = ae.pack(96, 3)
    assert p["pack_voltage_v"] == 355.2 and p["voltage_class"].startswith("High") and ae.pack(3, 1)["voltage_class"] == "Low voltage."
    assert ae.precharge(400, 1000, 100)["time_to_95pct_ms"] == pytest.approx(300) and ae.precharge(400, 1000, 100)["peak_current_a"] == 4
    assert ae.isolation(400, 150)["status"].startswith("Pass for DC only") and ae.isolation(400, 250)["status"] == "Pass" and ae.isolation(400, 20)["status"].startswith("Fail")


def test_reference_is_complete_and_safe():
    r = ae.reference()
    assert {s["id"] for s in r["systems"]} == {"zonal", "dash", "eth", "keyless", "srs", "avm", "ev_hv", "charge"}
    assert all(s["caution"] for s in r["systems"])
    k = next(s for s in r["systems"] if s["id"] == "keyless")
    assert "does not teach" in k["caution"]
    assert len(ae.SLIPS) == 11 and len(cl.SLIPS) == 6
    for m in ("cpe_lab", "auto_elec"):
        assert m in known_errors.SOURCES


def test_endpoints_and_track(client):
    ts = client.get("/api/tracks").json()["tracks"]
    assert ts[-1]["id"] == "cpe"
    d = client.get("/api/tracks/cpe/dashboard").json()
    assert len(d["ideas"]) == 4
    assert client.post("/api/cpe/convert", json={"text": "-45", "base": 10, "bits": 8}).json()["twos_complement"] == "11010011"
    assert client.post("/api/cpe/convert", json={"text": "zz"}).status_code == 400
    assert client.post("/api/cpe/logic", json={"text": "A AND"}).status_code == 400
    assert client.post("/api/cpe/ohm", json={"v": 12, "r": 4}).json()["current_a"] == 3
    assert client.post("/api/cpe/wire", json={"load_a": 10, "length_m": 3}).json()["fuse_a"] == 15
    assert client.post("/api/cpe/ev-charge", json={"capacity_kwh": 60, "start_pct": 20, "target_pct": 80, "source": "dc"}).status_code == 200
    assert client.post("/api/cpe/can-load", json={"bitrate_kbps": 500, "frames": [{"bytes": 8, "per_second": 10}]}).status_code == 200
    assert client.get("/api/cpe/reference").json()["auto"]["buses"]
    m = client.get("/api/manuals/cpe").json()
    assert len(m["steps"]) == 10
