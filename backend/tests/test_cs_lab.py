import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import agent_tools, agents, cs_lab


def est(code):
    return cs_lab.complexity(code)["functions"][0]["estimate"]


def test_big_o_shapes():
    assert est("def f(xs):\n    return xs[0]\n") == "O(1)"
    assert est("def f(xs):\n    t = 0\n    for x in xs:\n        t += x\n    return t\n") == "O(n)"
    assert est("def f(xs):\n    for a in xs:\n        for b in xs:\n            pass\n") == "O(n^2)"
    assert est("def f(xs):\n    return sorted(xs)\n") == "O(n log n)"
    assert est("def fib(n):\n    return n if n < 2 else fib(n-1) + fib(n-2)\n") == "O(2^n)"
    assert est("def f(n):\n    while n > 1:\n        n //= 2\n") == "O(log n)"


def test_memoised_fib_is_not_exponential():
    r = cs_lab.complexity("from functools import lru_cache\n@lru_cache\ndef fib(n):\n    return n if n < 2 else fib(n-1) + fib(n-2)\n")
    assert r["functions"][0]["estimate"] != "O(2^n)"


def test_in_list_inside_loop_is_flagged_and_code_is_never_run():
    r = cs_lab.complexity("import os\nos.system('echo hi > /tmp/should_not_exist_cs')\ndef f(xs, ys):\n    for x in xs:\n        if x in ys:\n            pass\n")
    import os
    assert not os.path.exists("/tmp/should_not_exist_cs")
    assert any("set" in n for f in r["functions"] for n in f["notes"])


def test_non_python_is_read_as_text_and_empty_refused():
    assert "text" in cs_lab.complexity("for (i=0;i<n;i++) {\n  for (j=0;j<n;j++) {}\n}")["language"].lower()
    with pytest.raises(cs_lab.CsError):
        cs_lab.complexity("  ")


@pytest.mark.parametrize("algo", list(cs_lab.SORTS))
def test_every_sort_sorts(algo):
    r = cs_lab.sort_steps(algo, "5, 2, 9, 1, 5, 6, -3")
    assert r["sorted"] == sorted(r["input"]) and r["comparisons"] > 0


def test_search_and_limits():
    b = cs_lab.search_steps("binary", "9 1 5 3 7", 7)
    assert b["found_at"] == 4 and b["comparisons"] <= 3
    assert cs_lab.search_steps("linear", "4 8 15", 99)["found_at"] is None
    with pytest.raises(cs_lab.CsError):
        cs_lab.sort_steps("bubble", ",".join(["1"] * 500))
    with pytest.raises(cs_lab.CsError):
        cs_lab.sort_steps("bubble", "a, b")


def test_endpoints_and_agent_tools():
    c = TestClient(app)
    assert c.get("/api/cs/reference").json()["structures"]
    assert c.post("/api/cs/complexity", json={"code": "for i in x:\n  pass"}).status_code == 200
    assert c.post("/api/cs/sort", json={"algorithm": "merge", "data": "3 1 2"}).json()["sorted"] == [1, 2, 3]
    assert c.post("/api/cs/search", json={"algorithm": "x", "data": "1", "target": 1}).status_code == 400
    for t in ("big_o", "sort_steps", "search_steps"):
        assert t in agent_tools.BY_TRACK["cpe"]
    text, err = agent_tools.run_tool("cpe", {"tool": "sort_steps", "args": {"algorithm": "quick", "data": "3 1 2"}})
    assert not err and "sorted" in text
    assert "algorithms" in agents.AGENTS["cpe"]["focus"]
