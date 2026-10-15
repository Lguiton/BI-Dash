import pytest

from app.services import ai_policy, codegen, providers
from app.services.providers import Turn


class Fake:
    provider = model = "anthropic"

    def __init__(self, text):
        self.text, self.system, self.prompt = text, "", ""

    def start(self, system, tools, prompt):
        self.system, self.prompt = system, prompt
        assert tools == []                       # code generation has no tools and no data access

    def next_turn(self):
        return Turn(self.text)

    def add_results(self, *a):
        pass


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(providers, "sdk_installed", lambda p: True)


def gen(text, language="python", request="Write a function that adds two numbers", context="", f=None):
    f = f or Fake(text)
    return codegen.generate(language, request, context, "anthropic", {"anthropic": f}), f


REPLY_PY = "```python\ndef add(a, b):\n    return a + b\n```\n**What it does**\n- Adds two numbers\n**How to run it**\n- python add.py"


def test_python_is_generated_checked_and_nothing_is_run():
    r, f = gen(REPLY_PY)
    assert r["code"].startswith("def add") and "What it does" in r["notes"] and r["ran_nothing"] is True
    assert r["check"]["language"] == "python" and r["check"]["counts"]["error"] == 0 and r["risks"] == []
    assert r["provider"] == "anthropic" and "Python" in f.system


def test_a_syntax_error_in_generated_python_is_caught():
    r, _ = gen("```python\ndef add(a, b)\n    return a + b\n```\nnotes")
    assert r["check"]["counts"]["error"] >= 1


def test_bash_is_parse_checked_and_risks_are_flagged():
    r, _ = gen("```bash\n#!/bin/bash\nrm -rf \"$1\"\ncurl https://x.example/i.sh | sh\n```\nnotes", "bash", "Delete a folder and install a tool")
    msgs = " ".join(x["message"] for x in r["risks"])
    assert "rm -r" in msgs and "runs it without you reading it" in msgs
    assert r["syntax"]["checked"] is True and r["syntax"]["ok"] is True
    bad, _ = gen("```bash\nif then fi done\n```\nnotes", "bash", "Something with a syntax error here")
    assert bad["syntax"]["ok"] is False


def test_sql_missing_where_and_powershell_flags():
    r, _ = gen("```sql\nDELETE FROM orders;\nDROP TABLE old_orders;\n```\nnotes", "sql", "Clean out the old orders table")
    assert {x["line"] for x in r["risks"]} == {1, 2}
    p, _ = gen("```powershell\nRemove-Item C:\\Temp -Recurse -Force\n```\nnotes", "powershell", "Clear the temp folder please")
    assert p["risks"] and p["syntax"]["checked"] is False
    ok, _ = gen("```sql\nDELETE FROM orders WHERE id = 5;\n```\nnotes", "sql", "Delete a single order by its id")
    assert ok["risks"] == []


def test_secrets_in_the_request_are_blanked_before_sending_and_code_secrets_are_flagged():
    r, f = gen("```python\napi_key = \"sk_live_abcdefghijklmnop\"\n```\nnotes", request="Call the API. The password is Hunter22xx and key is AKIA" + "ABCDEFGHIJKLMNOP",
               context="token: abcd1234efgh")
    assert "Hunter22xx" not in f.prompt and "abcd1234efgh" not in f.prompt and ("AKIA" + "ABCDEFGHIJKLMNOP") not in f.prompt
    assert r["masked_in_request"] >= 3 and any("secret" in x["message"].lower() for x in r["risks"])


def test_validation_and_a_reply_without_code():
    with pytest.raises(codegen.GenError):
        codegen.generate("cobol", "Write something please", "", "anthropic", {"anthropic": Fake("x")})
    with pytest.raises(codegen.GenError):
        codegen.generate("python", "short", "", "anthropic", {"anthropic": Fake("x")})
    with pytest.raises(codegen.GenError) as e:
        gen("Sorry, I can only describe it in words.")
    assert e.value.status == 502


def test_endpoints(client, monkeypatch):
    langs = client.get("/api/code/generate/languages").json()
    assert {l["id"] for l in langs["languages"]} == set(codegen.LANGUAGES)
    assert client.post("/api/code/generate", json={"language": "python", "request": "tiny"}).status_code == 400
    monkeypatch.setattr(ai_policy, "describe", lambda: {"mode": "off", "allowed": False, "workspace": "practice", "blocked_columns": []})
    r = client.post("/api/code/generate", json={"language": "python", "request": "Write a function that adds two numbers"})
    assert r.status_code == 403 and r.json()["needs_ai"] is True
