import ast
import sqlite3

import pytest

from app.services import fs_tools as fs

F = [{"name": "title", "type": "text", "required": True}, {"name": "price", "type": "decimal"}, {"name": "due", "type": "date"}]


def test_scaffold_compiles_and_runs():
    r = fs.scaffold("orders", F)
    py = next(x for x in r["files"] if x["language"] == "python")["code"]
    ast.parse(py)                                    # the generated API is valid Python
    sql = next(x for x in r["files"] if x["language"] == "sql")["code"]
    db = sqlite3.connect(":memory:")
    db.executescript(sql)
    db.execute("INSERT INTO orders (title) VALUES ('a')")
    assert "VALUES (?, ?, ?)" in py and "body.title" in py and "no login" in r["caution"]
    for bad in ("Orders", "x;y", ""):
        with pytest.raises(fs.FsError):
            fs.scaffold(bad, F)
    for bad in ([{"name": "id", "type": "text"}], [{"name": "a b", "type": "text"}], [{"name": "a", "type": "blob"}], []):
        with pytest.raises(fs.FsError):
            fs.scaffold("t", bad)


def test_api_contract():
    r = fs.api_contract("Shop API", [{"method": "post", "path": "/orders", "summary": "Create", "request": [{"name": "title", "type": "text"}], "response": [{"name": "id", "type": "integer"}]}, {"method": "GET", "path": "/orders/{id}"}])
    assert "## POST /orders" in r["markdown"] and r["openapi"]["paths"]["/orders"]["post"]["requestBody"]
    assert "curl -X POST" in r["markdown"]
    with pytest.raises(fs.FsError):
        fs.api_contract("x", [{"method": "FETCH", "path": "/a"}])
    with pytest.raises(fs.FsError):
        fs.api_contract("x", [{"method": "GET", "path": "a b"}])


def test_review_runbook_quote():
    h = fs.review_report("def f(:\n  pass", "python", "Demo <b>")
    assert "Demo &lt;b&gt;" in h and "Questions for a person" in h and "error" in h
    with pytest.raises(fs.FsError):
        fs.review_report("")
    rb = fs.runbook("web_app", "vps", "example.com")
    assert "DNS for example.com" in rb["markdown"] and "rollback" in rb["markdown"].lower()
    with pytest.raises(fs.FsError):
        fs.runbook("web_app", "vps", "bad domain; rm")
    q = fs.quote([{"name": "Login", "hours_low": 4, "hours_high": 8}, {"name": "Reports", "hours_low": 6, "hours_high": 10}], 80, 20)
    assert q["hours_before_buffer"] == [10, 18] and q["hours_with_buffer"] == [12, 21.6] and q["price_range"] == [960, 1728]
    assert abs(sum(p["amount"] for p in q["payments"]) - q["suggested_fixed_price"]) < 0.01
    with pytest.raises(fs.FsError):
        fs.quote([{"name": "x", "hours_low": 9, "hours_high": 2}], 80)
