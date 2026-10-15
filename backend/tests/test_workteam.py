import pytest

from app.services import ai_policy, clients, jobpage, practice_kits, providers, workspaces, workteam
from app.services.providers import Turn


class Fake:
    def __init__(self, name, text="Draft text", fail=False):
        self.provider = self.model = name
        self.text, self.fail, self.system, self.prompt, self.calls = text, fail, "", "", 0

    def start(self, system, tools, prompt):
        self.system, self.prompt = system, prompt
        self.calls += 1
        if self.fail:
            raise providers.ProviderError("boom", 500)

    def next_turn(self):
        return Turn(self.text)

    def add_results(self, *a):
        pass


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.setenv(k, "x")
    monkeypatch.setattr(providers, "sdk_installed", lambda p: True)


def _team(**over):
    d = {"google": Fake("google", "G draft"), "openai": Fake("openai", "O draft"), "anthropic": Fake("anthropic", "FINAL ANSWER\n=== JUDGE NOTES ===\nO was best; verify totals.")}
    d.update(over)
    return d


def _job(client_name, title):
    c = clients.add_client({"name": client_name})
    cid = c.get("id") or c["client"]["id"]
    return jobpage.quick_start(title, client_id=cid)["job"]["id"]


def test_kits_cover_20_jobs_and_have_true_answers():
    assert len(practice_kits.list_titles()) == 20
    k = practice_kits.for_title("Engineering: Check shelf bracket load calculation")
    assert "3.33" in " ".join(k["answer"]) and practice_kits.for_title("IT repair: Laptop tune-up and cleanup") is None
    assert practice_kits.for_title("Full-stack: Fix a booking form that returns an error")["files"][0]["text"] == practice_kits.BOOKING_CODE
    with pytest.raises(ValueError):
        exec(practice_kits.BOOKING_CODE + "\nbook({'name':'Ben','guests':'3','date':''}, set())")        # the kit's bug is real
    assert practice_kits.for_title("x: Weekly sales dashboard")["files"][0]["text"] == practice_kits.for_title("Weekly sales dashboard")["files"][0]["text"]   # same every time


def test_off_by_default_and_cap_counts_runs(client):
    jid = _job("(practice) Cafe", "Data analyst: Weekly sales dashboard")
    with pytest.raises(workteam.TeamError) as e:
        workteam.run(jid, "", "", _team())
    assert e.value.status == 403
    workteam.update_config({"enabled": True, "daily_cap": 1})
    r = workteam.run(jid, "", "", _team())
    assert r["text"] == "FINAL ANSWER" and "verify totals" in r["judge_notes"] and len(r["drafts"]) == 3 and r["judge"] == "Claude"
    with pytest.raises(workteam.TeamError) as e2:
        workteam.run(jid, "", "", _team())
    assert e2.value.status == 429
    assert client.put("/api/workteam/config", json={"daily_cap": 21}).status_code == 400


def test_practice_kit_is_sent_but_the_answer_key_is_not(client):
    jid = _job("(practice) Cafe", "Data analyst: Weekly sales dashboard")
    workteam.update_config({"enabled": True, "daily_cap": 3})
    t = _team()
    r = workteam.run(jid, "", "", t)
    p = t["google"].prompt
    assert "sales_6_weeks.csv" in p and "Exact duplicate rows: 2" in p
    assert "Top item by revenue" not in p and "Revenue after removing" not in p
    assert r["workspace"] == "practice" and r["mode"] == "work"
    assert workteam.kit_for_job(jid) and "answer" not in workteam.kit_for_job(jid)
    assert "answer" in workteam.kit_answer(jid)


def test_it_network_security_jobs_get_advice_only(client):
    jid = _job("(practice) Office", "Networking: Fix office Wi-Fi dropping")
    workteam.update_config({"enabled": True, "daily_cap": 3})
    t = _team()
    r = workteam.run(jid, "", "", t)
    assert r["mode"] == "advice" and "Do NOT say anything was fixed" in t["openai"].system


def test_one_failed_drafter_still_gets_judged_and_all_failed_is_an_error(client):
    jid = _job("(practice) Cafe", "Data analyst: Weekly sales dashboard")
    workteam.update_config({"enabled": True, "daily_cap": 5})
    r = workteam.run(jid, "", "", _team(google=Fake("google", fail=True)))
    assert r["failed"] == ["Gemini"] and len(r["drafts"]) == 2 and r["judge"] == "Claude"
    r2 = workteam.run(jid, "", "", _team(google=Fake("google", fail=True), anthropic=Fake("anthropic", fail=True)))
    assert len(r2["drafts"]) == 1 and r2["judge"] == "" and "Only OpenAI answered" in r2["judge_notes"]
    with pytest.raises(workteam.TeamError) as e:
        workteam.run(jid, "", "", {k: Fake(k, fail=True) for k in ("google", "openai", "anthropic")})
    assert e.value.status == 502


def test_judge_falls_back_when_claude_fails(client):
    jid = _job("(practice) Cafe", "Data analyst: Weekly sales dashboard")
    workteam.update_config({"enabled": True, "daily_cap": 5})
    r = workteam.run(jid, "", "", _team(anthropic=Fake("anthropic", fail=True), openai=Fake("openai", "J\n=== JUDGE NOTES ===\nok")))
    assert r["judge"] == "OpenAI" or r["judge"] == "Gemini"


def test_real_workspace_shares_computed_facts_not_rows_and_scrubs_client_names(client, monkeypatch):
    monkeypatch.setattr(workspaces, "active", lambda: "real")
    monkeypatch.setattr(ai_policy, "describe", lambda: {"mode": "full"})
    c = clients.add_client({"name": "Acme Dental"})
    cid = c.get("id") or c["client"]["id"]
    jid = jobpage.quick_start("Data analyst: Weekly report for Acme Dental", client_id=cid)["job"]["id"]
    workteam.update_config({"enabled": True, "daily_cap": 3})
    csv_text = "date,item,total\n2026-01-01,Cleaning,100\n2026-01-02,Whitening,250\n2026-01-02,Whitening,250\n2026-01-03,Cleaning,\n"
    t = _team()
    r = workteam.run(jid, "Acme Dental wants totals by item", csv_text, t)
    p = t["openai"].prompt
    assert "Acme Dental" not in p and "Exact duplicate rows: 1" in p and "total: number" in p
    assert "2026-01-03,Cleaning" not in p and any("summarised locally" in w for w in r["warnings"]) and r["workspace"] == "real"
    assert workteam.kit_for_job(jid) is None
    with pytest.raises(workteam.TeamError):
        workteam.kit_answer(jid)
    t2 = _team()
    r2 = workteam.run(jid, "", "Notes from the call: they want a monthly view.", t2)
    assert "monthly view" in t2["openai"].prompt and any("sent to the AI providers" in w for w in r2["warnings"])


def test_real_job_with_nothing_to_go_on_asks_for_it(client, monkeypatch):
    monkeypatch.setattr(workspaces, "active", lambda: "real")
    monkeypatch.setattr(ai_policy, "describe", lambda: {"mode": "full"})
    jid = _job("Real Client LLC", "Data analyst: Report")
    workteam.update_config({"enabled": True, "daily_cap": 3})
    with pytest.raises(workteam.TeamError) as e:
        workteam.run(jid, "", "", _team())
    assert e.value.status == 400


def test_result_lands_in_the_approval_queue_and_can_be_edited_long(client):
    jid = _job("(practice) Cafe", "Data analyst: Weekly sales dashboard")
    workteam.update_config({"enabled": True, "daily_cap": 3})
    r = workteam.run(jid, "", "", _team())
    assert any(x["key"] == r["key"] for x in client.get("/api/auto/queue").json()["queue"])
    key = r["key"]
    long = "x" * 4000
    res = client.put(f"/api/auto/prep/drafts/{key}", json={"text": long})
    assert res.status_code == 200 and len(res.json()["text"]) == 4000
    assert client.get(f"/api/workteam/kit/{jid}").json()["kit"]["files"]


def test_facts_helper():
    assert workteam.facts("just words") == ""
    f = workteam.facts("a,b\n1,x\n2,y\n2,y\n")
    assert "3 rows" in f and "duplicate rows: 1" in f and "min 1" in f


def test_real_workspace_respects_ai_off_by_default(client, monkeypatch):
    monkeypatch.setattr(workspaces, "active", lambda: "real")
    jid = _job("Real Client LLC", "Data analyst: Report")
    workteam.update_config({"enabled": True})
    with pytest.raises(workteam.TeamError) as e:
        workteam.run(jid, "x", "", _team())
    assert e.value.status == 403 and "Settings" in e.value.message
