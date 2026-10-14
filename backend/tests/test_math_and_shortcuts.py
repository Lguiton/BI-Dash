import pytest

from app.services import agents, biz_agents, calc_tool, providers
from app.services.providers import Turn, Call


class Fake:
    provider, model = "anthropic", "fake"

    def __init__(self, turns):
        self.turns, self.i, self.system, self.tools, self.results = turns, 0, "", [], []

    def start(self, system, tools, question):
        self.system, self.tools = system, tools

    def next_turn(self):
        t = self.turns[self.i]
        self.i += 1
        return t

    def add_results(self, turn, results):
        self.results.extend(results)


def test_calculator_math_stats_finance():
    c = lambda e: calc_tool.calculate(e)["result"]  # noqa: E731
    assert c("1200*(1+0.05)**3") == pytest.approx(1389.15, abs=0.01) and c("2^10") == 1024 and c("(7+3)*4/5") == 8
    assert c("mean([1,2,3,4])") == 2.5 and c("median([5,1,3])") == 3 and c("comb(5,2)") == 10 and c("factorial(5)") == 120
    assert c("pmt(0.06/12, 60, 25000)") == pytest.approx(-483.32, abs=0.01)
    assert c("npv(0.1,[-1000,400,500,600])") == pytest.approx(227.65, abs=0.01)
    assert c("irr([-100,60,60])") == pytest.approx(0.1306, abs=0.001)
    assert c("margin(200,150)") == 25 and c("pct_change(80,100)") == 25 and c("breakeven(1000,50,30)") == 50
    assert c("norm_cdf(0)") == 0.5 and c("0.1+0.2") == 0.3                      # float noise is trimmed


def test_calculator_refuses_anything_unsafe():
    for bad in ("__import__('os').system('ls')", "open('/etc/passwd')", "().__class__", "9**9**9", "10**100000", "factorial(10**9)", "x+1", "[i for i in range(9)]", "1/0", "", "a" * 500, "lambda: 1"):
        with pytest.raises(calc_tool.CalcError):
            calc_tool.calculate(bad)


def test_math_persona_on_dashboards_and_tracks(client):
    client.post("/api/biz-packs/retail-sales/sample")
    f = Fake([Turn("", [Call("1", "calculate", {"expression": "pct_change(80,100)"})]), Turn("It grew 25%.")])
    r = biz_agents.chat("retail-sales", "check my growth math", adapters={"anthropic": f, "openai": f, "google": f}, provider="anthropic", persona="math")
    assert "Mathematician" in f.system and "calculate" in [t["name"] for t in f.tools] and "25.0" in str(f.results[0]) and r.reply == "It grew 25%."
    g = Fake([Turn("ok")])
    agents.chat("analyst", "what is 15% of 80", adapters={"anthropic": g, "openai": g, "google": g}, provider="anthropic", persona="math")
    assert "Mathematician agent" in g.system and "calculate" in [t["name"] for t in g.tools]
    with pytest.raises(agents.AgentError):
        agents.chat("cpe", "hi there", provider="anthropic", persona="math")
    assert "math" in client.get("/api/biz-packs/retail-sales/assistant").json()["personas"]


def test_windows_shortcuts_endpoint(client):
    d = client.get("/api/it/shortcuts").json()
    assert d["count"] > 120 and "Troubleshooting and IT tools" in d["groups"]
    allk = {r["keys"] for g in d["groups"].values() for r in g}
    assert {"Win+L", "Ctrl+Shift+Esc", "Win+Shift+S", "Alt+Tab"} <= allk


def test_engineering_math_gray_ascii_bits():
    from app.services import eng_math as em
    assert em.run("gray", {"value": 5, "bits": 4})["gray"] == "0111" and em.run("gray", {"value": "0111", "direction": "from_gray", "bits": 4})["decimal"] == 5
    assert em.run("gray", {"value": 7, "direction": "from_gray", "bits": 4})["decimal"] == 5
    seq = em.run("gray", {"sequence_bits": 3})["sequence"]
    assert [r["gray"] for r in seq] == ["000", "001", "011", "010", "110", "111", "101", "100"]
    assert all(bin(int(seq[i]["gray"], 2) ^ int(seq[(i + 1) % 8]["gray"], 2)).count("1") == 1 for i in range(8))
    a = em.run("ascii", {"text": "Hi!"})
    assert [x["decimal"] for x in a["characters"]] == [72, 105, 33] and a["hex_string"] == "48 69 21"
    assert em.run("ascii", {"code": 65})["character"] == "A" and em.run("ascii", {"code": 10})["character"] == "LF"
    assert em.run("convert", {"value": "0xFF", "base": 16, "bits": 8})["decimal"] == 255
    assert em.run("convert", {"value": -5, "base": 10, "bits": 8})["twos_complement"] == "11111011"
    assert em.run("bitop", {"op": "xor", "a": "0xF0", "b": "0x3C"})["result_hex"] == "CC"
    assert em.run("bitop", {"op": "rol", "a": "0b10010001", "b": 1})["result_binary"] == "00100011"
    assert em.run("bitop", {"op": "sar", "a": "0x80", "b": 2})["result_hex"] == "E0"
    assert em.run("parity", {"value": "0b1011001"})["even_parity_bit"] == 0 and em.run("parity", {"value": 7})["even_parity_bit"] == 1
    assert em.run("bcd", {"value": 42})["bcd"] == "0100 0010" and em.run("bcd", {"bcd": "1001 0101"})["decimal"] == 95
    assert em.run("checksum", {"data": "31 32 33 34 35 36 37 38 39", "checksum": "crc16-ccitt"})["hex"] == "29B1"
    assert em.run("checksum", {"data": "31 32 33 34 35 36 37 38 39", "checksum": "crc8"})["hex"] == "F4"
    assert em.run("checksum", {"data": "31 32 33 34 35 36 37 38 39", "checksum": "crc16-modbus"})["hex"] == "4B37"
    cw = em.run("hamming", {"data": "1011"})["codeword"]
    assert cw == "0110011"
    bad = "0110111"                                    # bit 5 flipped
    r = em.run("hamming", {"received": bad})
    assert r["error_position"] == 5 and r["corrected"] == cw and r["data_bits"] == "1011"
    assert em.run("endian", {"value": "0x12345678"})["little_endian_bytes"] == "78 56 34 12"
    assert em.run("ieee754", {"x": 1.0})["hex"] == "3F800000"
    for bad_args in ({"kind": "gray", "value": 99, "bits": 4}, {"kind": "bitop", "op": "zap", "a": 1}, {"kind": "nope"}, {"kind": "bcd", "bcd": "1111"}):
        with pytest.raises(em.EngMathError):
            em.run(bad_args["kind"], bad_args)


def test_engmath_persona_only_on_cpe():
    f = Fake([Turn("", [Call("1", "eng_math", {"kind": "gray", "value": 5, "bits": 4})]), Turn("0111")])
    agents.chat("cpe", "gray code of 5?", adapters={"anthropic": f, "openai": f, "google": f}, provider="anthropic", persona="engmath")
    assert "Engineering Mathematician agent" in f.system and {"eng_math", "calculate"} <= {t["name"] for t in f.tools} and "0111" in str(f.results[0])
    g = Fake([Turn("ok")])
    agents.chat("cpe", "hello there", adapters={"anthropic": g, "openai": g, "google": g}, provider="anthropic")
    assert "eng_math" in {t["name"] for t in g.tools}
    with pytest.raises(agents.AgentError):
        agents.chat("analyst", "hello there", provider="anthropic", persona="engmath")


def test_how_to_repair_guides(client):
    d = client.get("/api/it/repair").json()
    ids = [g["id"] for g in d["guides"]]
    assert len(ids) == len(set(ids)) >= 40 and len(d["method"]) == 6 and len(d["safety"]) >= 4
    for g in d["guides"]:
        assert g["title"] and g["symptoms"] and g["causes"] and len(g["steps"]) >= 4 and g["tools"] and g["safety"] and g["escalate"] and g["objective"] in {"5.1", "5.2", "5.3", "5.4", "5.5", "5.6", "General"}
    assert {"5.1", "5.2", "5.3", "5.4", "5.5", "5.6"} <= {g["objective"] for g in d["guides"]}


def test_repair_toolkit_and_dhcp(client):
    d = client.get("/api/it/repair").json()
    cmds = [r for c in d["toolkit"]["commands"] for r in c["run"]]
    assert "sfc /scannow" in cmds and "DISM /Online /Cleanup-Image /RestoreHealth" in cmds and "netsh winsock reset" in cmds
    assert all(l["url"].startswith("https://") for l in d["toolkit"]["links"]) and len(d["toolkit"]["tools"]) == 10
    assert any(g["id"] == "dhcp" for g in d["guides"])


def test_scenario_what_if():
    from app.services import scenario
    r = scenario.run("price_change_pct", 10, 10000, 9000, cash=6000)
    assert r["projected"]["revenue"] == 11000 and r["net_change_per_month"] == 1000
    h = scenario.run("new_hire_monthly_cost", 4000, 10000, 9500, cash=9000)
    assert h["baseline"]["net"] == 500 and h["projected"]["net"] == -3500 and h["runway_months"]["before"] is None and h["runway_months"]["after"] == 2.6
    assert scenario.run("lost_account_monthly_revenue", 99999, 100, 50)["projected"]["revenue"] == 0
    import pytest
    with pytest.raises(scenario.ScenarioError):
        scenario.run("nope", 1, 1, 1)
