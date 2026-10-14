import pytest

from app.services import cpe_tools as c

P = [{"name": "ESP32 sensor", "qty": 1, "unit_cost": 8, "current_ma": 80, "pins": 1, "voltage": "3.3"}, {"name": "5V relay", "qty": 2, "unit_cost": 3, "current_ma": 70, "pins": 1, "voltage": "5"}]


def test_parts_levels_and_power():
    r = c.parts_check("esp32", P, 500)
    assert r["total_cost"] == 14 and r["pins_needed"] == 3 and r["total_current_ma"] == 220
    assert any("level shifter" in f["says"] for f in r["findings"]) and r["status"] == "problems"
    big = c.parts_check("uno", [{"name": "motor", "qty": 1, "current_ma": 900, "pins": 1, "voltage": "5"}], 500)
    assert any(f["severity"] == "high" and "supply" in f["says"] for f in big["findings"])
    with pytest.raises(c.CpeError):
        c.parts_check("nope", P)
    with pytest.raises(c.CpeError):
        c.parts_check("uno", [{"name": "", "qty": 1}])
    with pytest.raises(c.CpeError):
        c.parts_check("uno", [{"name": "x", "voltage": "12"}])


def test_runtime_arithmetic():
    r = c.runtime(2000, 100, 0.01, 2, 600)
    assert abs(r["average_ma"] - (100 * 2 + 0.01 * 598) / 600) < 0.001
    assert r["runtime"]["pessimistic"]["hours"] < r["runtime"]["typical"]["hours"] < r["runtime"]["optimistic"]["hours"]
    with pytest.raises(c.CpeError):
        c.runtime(2000, 100, 0, 700, 600)


def test_sketch_and_plan():
    s = c.sketch("arduino", "dht22", 4, 5)
    assert "DHT dht(4, DHT22)" in s["code"] and "delay(5000)" in s["code"] and "void loop" in s["code"]
    m = c.sketch("micropython", "analog", 34, 10, "wifi_post", "https://example.com/r")
    assert "urequests.post('https://example.com/r'" in m["code"] and "YOUR_WIFI_PASSWORD" in m["code"]
    with pytest.raises(c.CpeError):
        c.sketch("arduino", "dht22", 4, 5, "wifi_post", "javascript:alert(1)")
    with pytest.raises(c.CpeError):
        c.sketch("arduino", "dht22", 99)
    h = c.test_plan("Garden <b>logger</b>", ["Soil sensor"], 120, 5)
    assert "<b>logger</b>" not in h and "Soil sensor" in h and "Soak test" in h
