import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import agent_tools, agents, elec_calc as ec, it_repair, repair_search


def test_voltage_drop_math_and_advice():
    r = ec.voltage_drop(20, 100, 12, 120)
    assert r["volts_lost"] == 7.92 and r["percent"] == 6.6 and r["smallest_size_under_3pct"] == "8 AWG"
    assert "3%" in ec.voltage_drop(5, 20, 14, 120)["verdict"]
    with pytest.raises(ec.ElecError):
        ec.voltage_drop(5, 20, 13)


def test_circuit_load_and_continuous_rule():
    r = ec.circuit_load(120, 15, "Space heater, 1500\nLamp, 60")
    assert r["total_watts"] == 1560 and r["amps"] == 13.0 and r["percent_of_usable"] == 87
    assert ec.circuit_load(120, 15, "Heater, 1500", True)["percent_of_usable"] == 104
    assert "bigger breaker" in ec.circuit_load(120, 15, "Heater, 1500", True)["verdict"]
    with pytest.raises(ec.ElecError):
        ec.circuit_load(120, 15, "heater")


def test_energy_hvac_ohm_deltat():
    assert ec.energy_cost(1000, 5, 0.2, 30)["cost"] == 30.0
    h = ec.hvac_size(1000, 8, "average", "average", 2)
    assert h["btu_per_hour"] == 20000 and h["tons"] == 1.7
    assert ec.ohm(volts=120, amps=10)["watts"] == 1200 and ec.ohm(amps=2, ohms=5)["volts"] == 10
    with pytest.raises(ec.ElecError):
        ec.ohm(volts=1)
    assert "Normal" in ec.delta_t(55, 75)["verdict"] and "Low split" in ec.delta_t(65, 75)["verdict"] and "airflow" in ec.delta_t(50, 78)["verdict"]


def test_home_guides_exist_are_findable_and_safe():
    ids = {g["id"] for g in it_repair.GUIDES}
    for i in ("washer-no-drain", "dryer-slow", "fridge-warm", "dishwasher-fault", "microwave-fault", "oven-range", "water-heater-checks", "disposal-jam", "window-portable-ac", "ac-not-cooling", "furnace-no-heat", "thermostat-problems", "hvac-sizing-airflow"):
        assert i in ids
    for g in it_repair.GUIDES:
        if g["id"] in ("fridge-warm", "ac-not-cooling", "furnace-no-heat", "microwave-fault", "water-heater-checks", "oven-range"):
            assert len(g["safety"]) > 40 and g["escalate"]
    assert repair_search.search("fridge not cooling", 1)["results"][0]["id"] == "fridge-warm"
    assert repair_search.search("furnace no heat", 1)["results"][0]["id"] == "furnace-no-heat"
    text = " ".join(" ".join(g["steps"]) for g in it_repair.GUIDES if g["id"] in ("ac-not-cooling", "fridge-warm"))
    assert "recharge" not in text.lower() and "top up" not in text.lower()


def test_endpoints_agent_tools_and_scope():
    c = TestClient(app)
    assert c.post("/api/elec/voltage-drop", json={"amps": 15, "length_ft": 50, "awg": 14}).status_code == 200
    assert c.post("/api/elec/hvac-size", json={"sqft": 400}).json()["btu_per_hour"] > 0
    assert c.post("/api/elec/ohm", json={"volts": 12}).status_code == 400
    assert c.get("/api/elec/reference").json()["who_does_what"]
    for t in ("voltage_drop", "circuit_load", "energy_cost", "hvac_size", "ohm", "delta_t"):
        assert t in agent_tools.BY_TRACK["cpe"]
    text, err = agent_tools.run_tool("cpe", {"tool": "delta_t", "args": {"supply_f": 55, "release": 0, "return_f": 75}})
    assert not err and "split" in text
    f = agents.AGENTS["cpe"]["focus"]
    assert "licensed" in f and "HVAC" in f
