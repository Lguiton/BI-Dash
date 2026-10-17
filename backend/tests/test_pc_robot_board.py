from fastapi.testclient import TestClient

from app.main import app
from app.services import agent_tools, it_repair, repair_search, robotics

c = TestClient(app)


def test_pc_check_catches_problems():
    r = c.post("/api/pcbuild/check", json={"cpu_socket": "AM5", "board_socket": "AM4", "board_ram": "DDR4", "ram_type": "DDR5", "board_form": "ATX", "case_form": "Mini-ITX",
                                           "gpu_len_mm": 340, "case_gpu_mm": 300, "cooler_mm": 165, "case_cooler_mm": 160, "cpu_tdp": 120, "gpu_tdp": 320, "psu_w": 450}).json()
    txt = " ".join(r["problems"])
    for w in ("socket", "RAM", "bigger than the case", "too long", "too tall", "too small"):
        assert w in txt
    good = c.post("/api/pcbuild/check", json={"cpu_socket": "AM5", "board_socket": "AM5", "board_ram": "DDR5", "ram_type": "DDR5", "board_form": "Micro-ATX", "case_form": "ATX"}).json()
    assert not good["problems"] and good["passes"]
    assert c.post("/api/pcbuild/check", json={}).status_code == 400


def test_psu_diagnose_checklist():
    p = c.post("/api/pcbuild/psu", json={"cpu_w": 125, "gpu_w": 300, "ssd": 2, "hdd": 1, "fans": 5}).json()
    assert p["recommended_w"] >= p["estimated_load_w"] * 1.3 and p["recommended_w"] in (750, 850)
    assert c.post("/api/pcbuild/diagnose", json={"symptom": "fans spin but no display"}).json()["matches"][0]["id"] == "fans-no-display"
    assert len(c.get("/api/pcbuild/checklist").json()["phases"]) == 5
    assert c.post("/api/pcbuild/psu", json={"cpu_w": "x", "gpu_w": 1}).status_code == 400


def test_robotics_math():
    d = robotics.drive_motor(5, 100, 1.0, 0.5, 0, 2, 0.03, 0.7, 2)
    assert abs(d["force_n"] - 5 * (9.81 * 0.03 + 0.5)) < 0.05 and d["wheel_rpm"] == round(60 / (3.14159265 * 0.1), 1)
    b = robotics.battery(5000, 11.1, 10, 20, 150)
    assert b["runtime_minutes"] == 24.0 and b["peak_ok"] is False
    s = robotics.servo(20, 0.5, 0.1)
    assert abs(s["torque_needed_kgcm"] - (0.5 * 20 + 0.1 * 10)) < 1e-6
    ik = robotics.arm_ik(10, 10, 10, 10)
    fk = robotics.arm_fk(10, 10, ik["solutions"][0]["angle1_deg"], ik["solutions"][0]["angle2_deg"])
    assert abs(fk["end"][0] - 10) < 0.05 and abs(fk["end"][1] - 10) < 0.05
    try:
        robotics.arm_ik(10, 10, 30, 0)
        assert False
    except robotics.RoboError:
        pass
    assert robotics.ultrasonic(5832, 20)["distance_cm"] == round(5832 * 343.42 / 10000 / 2, 2)
    dd = robotics.diff_drive(1, 1, 0.2, 2)
    assert abs(dd["x"] - 2.0) < 0.1 and abs(dd["y"]) < 1e-6
    assert robotics.encoder(11, 65, 30)["ticks_per_wheel_rev"] == 11 * 4 * 30


def test_pid_behaviour():
    good = robotics.pid(2.0, 1.0, 0.0, 1.0, 1.0, 1.0, 0, 10, 10)
    assert not good["unstable"] and abs(good["final"] - 1.0) < 0.02
    p_only = robotics.pid(2.0, 0, 0, 1.0, 1.0, 1.0, 0, 10, 10)
    assert p_only["final"] < 0.98           # P-only leaves a steady-state error
    bad = robotics.pid(200, 0, 0, 1.0, 1.0, 1.0, 0.3, 1000, 10)
    assert bad["unstable"]


def test_robotics_api_and_agent_tools():
    assert c.post("/api/robotics/calc/drive", json={"mass_kg": 3, "wheel_mm": 80, "speed_ms": 0.8}).status_code == 200
    assert c.post("/api/robotics/calc/nope", json={}).status_code == 400
    assert c.post("/api/robotics/calc/drive", json={"mass_kg": 3}).status_code == 400
    assert c.get("/api/robotics/reference").json()["projects"]
    t, e = agent_tools.run_tool("cpe", {"tool": "robot_calc", "args": {"kind": "servo", "args": {"arm_cm": 15, "load_kg": 0.3}}})
    assert not e and "choose_servo_kgcm" in t
    t, e = agent_tools.run_tool("cpe", {"tool": "pc_psu", "args": {"cpu_w": 100, "gpu_w": 200}})
    assert not e and "recommended_w" in t
    t, e = agent_tools.run_tool("cpe", {"tool": "pc_nopost", "args": {"symptom": "debug led DRAM"}})
    assert not e


def test_board_guides_registered_and_searchable():
    ids = {g["id"] for g in it_repair.GUIDES}
    assert {"board-microsolder", "board-hotair", "board-schematic", "board-short", "board-rails", "board-usbc", "board-backlight", "board-bga", "board-liquid", "board-trace"} <= ids
    for g in it_repair.GUIDES:
        if g["id"].startswith("board-"):
            assert g["steps"] and g["safety"] and g["escalate"]
    assert repair_search.search("short circuit rail hot", 3)["results"][0]["id"] == "board-short"
