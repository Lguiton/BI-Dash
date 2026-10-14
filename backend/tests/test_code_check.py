import json

from app.services import code_check as cc


def codes(r):
    return {f["code"] for f in r["findings"]}


def test_python():
    r = cc.check("import os\nx = 1\nif x == None:\n    print(y)\ntry:\n    pass\nexcept:\n    pass\n", "python")
    assert {"unused-import", "compare-none", "undefined-name", "bare-except"} <= codes(r)
    assert cc.check("def f(:\n  pass", "python")["findings"][0]["severity"] == "error"
    r = cc.check("def q(c, n):\n    c.execute(f\"select * from t where n='{n}'\")\n", "python")
    assert "sql-injection" in codes(r)


def test_json_html_sql_js():
    assert cc.check('{"a": 1,}', "json")["findings"][0]["line"] == 1
    r = cc.check("<div><p>hi<img src=x></div><div id=a></div><div id=a></div>", "html")
    assert {"img-alt", "dup-id"} <= codes(r)
    assert cc.check("selec * from t", "sql")["counts"]["error"] == 1
    assert "no-where" in codes(cc.check("delete from t", "sql"))
    assert cc.check("const a = (1;\n", "javascript")["counts"]["error"] == 1
    assert "xss" in codes(cc.check("el.innerHTML = x;\n", "javascript"))


def test_fix_and_notebook():
    r = cc.safe_fixes("x = 1\nif x == None:  \n    pass\n", "python")
    assert "is None" in r["fixed"] and r["applied"] is False and r["diff"]
    assert cc.detect("<div>x</div>") == "html"
    nb = cc.notebook("print(1)", "python")
    assert nb["nbformat"] == 4 and nb["cells"][1]["cell_type"] == "code"
    json.dumps(cc.notebook("select 1", "sql"))
    assert cc.extract_code("hi\n```python\nx=1\n```\nbullets")[0] == "x=1\n"


def test_api(client):
    r = client.post("/api/code/check", json={"code": "import os\n", "language": "python"})
    assert r.status_code == 200 and r.json()["counts"]["warning"] == 1
    assert client.post("/api/code/check", json={"code": " "}).status_code == 400
    assert client.post("/api/code/fix", json={"code": "a == None", "language": "python"}).json()["changed"]
    assert client.post("/api/code/notebook", json={"code": "1+1"}).json()["nbformat"] == 4
    assert "running" in client.get("/api/code/jupyter").json()
