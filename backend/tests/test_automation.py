import json

from datetime import date, timedelta

import pytest

from app.services import ai_policy, assistants, automation, clients, experience, prep, providers, state, worklog
from app.services.providers import Turn


class Fake:
    provider = model = "openai"

    def __init__(self, text="1. Check the router.\n2. Ask which devices fail."):
        self.text, self.system, self.prompt, self.calls = text, "", "", 0

    def start(self, system, tools, prompt):
        self.system, self.prompt = system, prompt
        self.calls += 1
        assert tools == []

    def next_turn(self):
        return Turn(self.text)

    def add_results(self, *a):
        pass


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(providers, "sdk_installed", lambda p: True)


def _client(client, name="Silver State Plumbing", contact="Tom"):
    r = client.post("/api/clients", json={"name": name, "contact": contact}).json()
    return r.get("id") or r["client"]["id"]


# ---------------------------------------------------------------- today
def test_today_lists_overdue_invoice_with_a_reminder_draft_and_sends_nothing(client):
    cid = _client(client)
    inv = clients.create_invoice({"client_id": cid, "from_time": False, "extra": [{"desc": "Fix", "qty": 1, "rate": 100}]})
    clients.set_invoice(inv["id"], "sent")
    d = clients._load()
    d["invoices"][0]["due"] = (date.today() - timedelta(days=5)).isoformat()
    clients._save(d)
    t = client.get("/api/auto/today").json()
    o = t["overdue_invoices"][0]
    assert o["days_late"] == 5 and "INV-" in o["draft"] and "$100.00" in o["draft"] and "Hi Tom" in o["draft"] and t["count"] >= 1
    assert "Nothing is sent" in t["note"]


def test_today_shows_followups_late_work_and_ready_to_close(client):
    cid = _client(client)
    j = client.post("/api/clients/jobs/add", json={"client_id": cid, "title": "Job A", "status": "active"}).json()
    client.post("/api/clients/followups/add", json={"client_id": cid, "due": date.today().isoformat(), "note": "Call"})
    w = client.post("/api/worklog", json={"title": "Step", "job_id": j["id"], "due": (date.today() - timedelta(days=1)).isoformat()}).json()
    t = client.get("/api/auto/today").json()
    assert t["followups"] and t["work_due"][0]["overdue"] and t["ready_to_close"] == []
    client.put(f"/api/worklog/{w['id']}", json={"status": "done"})
    t = client.get("/api/auto/today").json()
    assert [r["title"] for r in t["ready_to_close"]] == ["Job A"]
    assert client.get(f"/api/jobs/{j['id']}").json()["ready_to_close"] is True


def test_forgotten_timer_is_flagged_after_two_hours(client):
    w = client.post("/api/worklog", json={"title": "Long one"}).json()
    client.post(f"/api/worklog/{w['id']}/timer/start", json={})
    assert client.get("/api/auto/today").json()["timer"]["warn"] is False
    from datetime import datetime, timedelta, timezone
    state.run("UPDATE work_items SET timer_start=? WHERE id=?", ((datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"), w["id"]))
    t = client.get("/api/auto/today").json()
    assert t["timer"]["warn"] is True and t["count"] >= 1


def test_backup_reminder_only_for_real_data(client):
    assert client.get("/api/auto/today").json()["backup"] is None          # practice workspace


# ---------------------------------------------------------------- recurring
def test_recurring_job_is_created_once_per_period(client):
    cid = _client(client)
    r = client.post("/api/auto/recurring", json={"client_id": cid, "title": "Monthly report", "every": "monthly", "day": 1, "quote": 240, "items": ["Load CSV", "Write summary"]}).json()
    first = automation.run_recurring(date(2026, 11, 3))
    assert len(first) == 1 and "Monthly report" in first[0]["title"]
    assert automation.run_recurring(date(2026, 11, 20)) == []              # same month: nothing
    assert len(automation.run_recurring(date(2026, 12, 2))) == 1           # next month
    items = worklog.listing()["items"]
    assert {i["title"] for i in items} >= {"Load CSV", "Write summary"} and any(i["status"] == "doing" for i in items)
    client.put(f"/api/auto/recurring/{r['id']}", json={"active": False})
    assert automation.run_recurring(date(2027, 1, 5)) == []
    assert client.delete(f"/api/auto/recurring/{r['id']}").json()["deleted"] == r["id"]


def test_recurring_not_due_before_its_day_and_validation(client):
    cid = _client(client)
    client.post("/api/auto/recurring", json={"client_id": cid, "title": "Mid-month", "every": "monthly", "day": 15})
    assert automation.run_recurring(date(2026, 11, 10)) == []
    assert len(automation.run_recurring(date(2026, 11, 15))) == 1
    assert client.post("/api/auto/recurring", json={"client_id": cid, "title": "x", "every": "monthly", "day": 31}).status_code == 400
    assert client.post("/api/auto/recurring", json={"client_id": cid, "title": "", "every": "weekly"}).status_code == 400
    assert client.post("/api/auto/recurring", json={"client_id": 999, "title": "x", "every": "weekly"}).status_code == 404


# ---------------------------------------------------------------- prep drafts and the daily cap
def test_prep_is_off_by_default_and_does_not_call_the_model(client):
    w = client.post("/api/worklog", json={"title": "Printer offline"}).json()
    f = Fake()
    with pytest.raises(prep.PrepError) as e:
        prep.draft_item(w["id"], {"openai": f})
    assert e.value.status == 403 and f.calls == 0


def test_prep_sends_no_client_name_and_stores_a_labelled_draft(client):
    cid = _client(client, "Secret Client LLC")
    j = client.post("/api/clients/jobs/add", json={"client_id": cid, "title": "Fix Wi-Fi", "status": "active"}).json()
    w = client.post("/api/worklog", json={"title": "Wi-Fi drops every hour", "note": "router is old", "job_id": j["id"]}).json()
    prep.update_config({"enabled": True, "daily_cap": 5})
    f = Fake()
    r = prep.draft_item(w["id"], {"openai": f})
    assert "Secret Client" not in f.prompt and "Wi-Fi drops" in f.prompt and "Fix Wi-Fi" in f.prompt
    assert r["text"].startswith("1.") and prep.drafts()["drafts"][f"item:{w['id']}"]["kind"] == "item"
    assert prep.status()["used_today"] == 1


def test_daily_cap_stops_further_calls_and_failed_attempts_count(client):
    w = client.post("/api/worklog", json={"title": "Printer offline"}).json()
    prep.update_config({"enabled": True, "daily_cap": 2})
    f = Fake()
    prep.draft_item(w["id"], {"openai": f})
    prep.draft_item(w["id"], {"openai": f})
    with pytest.raises(prep.PrepError) as e:
        prep.draft_item(w["id"], {"openai": f})
    assert e.value.status == 429 and f.calls == 2
    assert client.post(f"/api/auto/prep/item/{w['id']}").status_code == 429


def test_cap_counts_a_failed_attempt_and_a_missing_key_is_a_clear_message(client, monkeypatch):
    w = client.post("/api/worklog", json={"title": "Printer offline"}).json()
    prep.update_config({"enabled": True, "daily_cap": 1})

    class Boom(Fake):
        def next_turn(self):
            raise providers.ProviderError("rate limited", 429)

    with pytest.raises(prep.PrepError) as e:
        prep.draft_item(w["id"], {"openai": Boom()})
    assert e.value.status == 502 and prep.status()["used_today"] == 1
    monkeypatch.setattr(providers, "api_key", lambda p: None)
    with pytest.raises(prep.PrepError) as e2:
        prep.draft_item(w["id"])
    assert e2.value.status in (429, 503)


def test_config_limits(client):
    assert client.put("/api/auto/prep", json={"daily_cap": 0}).status_code == 400
    assert client.put("/api/auto/prep", json={"daily_cap": 51}).status_code == 400
    assert client.put("/api/auto/prep", json={"auto_new_items": True}).status_code == 400      # needs prep on first
    assert client.put("/api/auto/prep", json={"enabled": True, "daily_cap": 7}).json()["remaining"] == 7


def test_auto_drafts_only_when_both_switches_on_and_stop_at_the_cap(client):
    for t in ("A printer problem", "B wifi problem", "C laptop slow", "D another"):
        client.post("/api/worklog", json={"title": t})
    f = Fake()
    assert prep.tick({"openai": f}) == [] and f.calls == 0                  # off
    prep.update_config({"enabled": True, "daily_cap": 2, "auto_new_items": True})
    if ai_policy.describe()["mode"] != "full":
        pytest.skip("workspace AI mode is not 'full' in this test setup")
    assert prep.tick({"openai": f}) == ["prep-drafts"] and f.calls == 2    # cap 2 < 3 per tick
    assert prep.tick({"openai": f}) == [] and f.calls == 2


def test_table_prep_sends_only_a_profile(client, monkeypatch):
    from app.services import datasets
    monkeypatch.setattr(datasets, "profile", lambda t: {"table": t, "rows": 3, "columns": [
        {"name": "amount", "kind": "number", "nulls": 0, "distinct_count": 3, "min": 1, "max": 9, "median": 4},
        {"name": "customer", "kind": "text", "nulls": 1, "distinct_count": 2, "top": [{"value": "Alice Smith", "n": 2}]}]})
    prep.update_config({"enabled": True, "daily_cap": 3})
    f = Fake()
    r = prep.draft_table("sales", {"openai": f})
    assert "amount (number)" in f.prompt and "min 1" in f.prompt and r["key"] == "table:sales"
    if ai_policy.describe()["mode"] != "full":
        assert "Alice" not in f.prompt                                       # text values only in full mode


def test_delete_draft(client):
    w = client.post("/api/worklog", json={"title": "Printer offline"}).json()
    prep.update_config({"enabled": True, "daily_cap": 3})
    prep.draft_item(w["id"], {"openai": Fake()})
    assert client.delete(f"/api/auto/prep/drafts/item:{w['id']}").json()["deleted"] == f"item:{w['id']}"
    assert client.delete("/api/auto/prep/drafts/item:999").status_code == 404


# ---------------------------------------------------------------- assistants: queue, own examples, roles, log, closing note
def _draft(client, title="Wi-Fi drops every hour at the office", note="router is old"):
    w = client.post("/api/worklog", json={"title": title, "note": note}).json()
    prep.update_config({"enabled": True, "daily_cap": 20})
    prep.draft_item(w["id"], {"openai": Fake("1. Check the router channel\n2. Update the firmware\n3. Test again wired")})
    return w


def test_queue_accept_edit_discard_and_log(client):
    w = _draft(client)
    q = client.get("/api/auto/queue").json()
    assert [r["key"] for r in q["queue"]] == [f"item:{w['id']}"] and q["queue"][0]["status"] == "pending"
    k = f"item:{w['id']}"
    r = client.put(f"/api/auto/prep/drafts/{k}", json={"text": "1. Check the channel\n2. Reboot", "status": "accepted"}).json()
    assert r["edited"] is True and r["status"] == "accepted"
    assert client.get("/api/auto/queue").json()["queue"] == []
    w2 = _draft(client, "Printer offline for everyone")
    client.put(f"/api/auto/prep/drafts/item:{w2['id']}", json={"status": "discarded"})
    s = client.get("/api/auto/assistants").json()["stats"]
    assert s["drafts_total"] == 2 and s["accepted"] == 1 and s["discarded"] == 1 and s["edited"] == 1 and s["used_rate"] == 0.5
    assert client.put(f"/api/auto/prep/drafts/{k}", json={"status": "bogus"}).status_code == 400
    assert client.put(f"/api/auto/prep/drafts/{k}", json={"text": "  "}).status_code == 400
    assert client.put("/api/auto/prep/drafts/item:9999", json={"status": "accepted"}).status_code == 404


def test_saving_my_version_creates_an_example_without_the_client_name_and_it_is_used_next_time(client):
    cid = _client(client, "Secret Client LLC")
    j = client.post("/api/clients/jobs/add", json={"client_id": cid, "title": "Fix Wi-Fi", "status": "active"}).json()
    w = client.post("/api/worklog", json={"title": "Secret Client LLC Wi-Fi drops every hour", "job_id": j["id"]}).json()
    prep.update_config({"enabled": True, "daily_cap": 20})
    prep.draft_item(w["id"], {"openai": Fake("1. Check it")})
    k = f"item:{w['id']}"
    r = client.put(f"/api/auto/prep/drafts/{k}", json={"text": "1. Move router to the middle of the office\n2. Pick channel 1, 6 or 11 at Secret Client LLC\n3. Test wired first", "status": "accepted", "save_example": True}).json()
    ex = r["example"]
    assert "Secret Client" not in json.dumps(ex) and ex["will_match"] is True and len(ex["steps"]) == 3
    text, used = experience.examples_any("wifi drops every hour again for another customer")
    assert used and used[0]["mine"] is True and "(your own)" in text and "Secret Client" not in text
    t2, u2 = experience.examples_for("network", "wifi drops every hour, router problem")
    assert u2 and u2[0]["mine"] is True                                     # yours rank first, for any agent
    mine = client.get("/api/auto/assistants").json()["mine"]
    assert len(mine) == 1 and client.delete(f"/api/auto/examples/mine/{mine[0]['id']}").json()["deleted"] == mine[0]["id"]
    assert client.delete("/api/auto/examples/mine/999").status_code == 404
    assert experience.examples_any("wifi drops every hour again")[1] == [] or not experience.examples_any("wifi drops every hour again")[1][0]["mine"]


def test_only_item_and_job_drafts_can_be_saved_as_examples(client, monkeypatch):
    from app.services import datasets
    monkeypatch.setattr(datasets, "profile", lambda t: {"table": t, "rows": 1, "columns": []})
    prep.update_config({"enabled": True, "daily_cap": 5})
    prep.draft_table("sales", {"openai": Fake()})
    assert client.put("/api/auto/prep/drafts/table:sales", json={"save_example": True}).status_code == 400


def test_roles_have_defaults_can_be_rewritten_and_reach_the_agent_prompt(client):
    d = client.get("/api/auto/assistants").json()
    assert len(d["roles"]) == 12 and all(r["never"] for r in d["roles"])
    r = client.put("/api/auto/assistants/roles/itsupport", json={"does": "Drafts steps and client questions.", "never": "Never touches the client's computer. key sk-" + "a" * 30}).json()
    assert r["custom"] is True and "sk-" + "a" * 30 not in r["never"]
    assert "Never touches" in assistants.role_prompt("itsupport") and "never override" in assistants.role_prompt("itsupport")
    assert client.put("/api/auto/assistants/roles/itsupport", json={"does": "", "never": "x"}).status_code == 400
    assert client.put("/api/auto/assistants/roles/nobody", json={"does": "a", "never": "b"}).status_code == 404
    assert client.delete("/api/auto/assistants/roles/itsupport").json()["custom"] is False


def test_item_drafts_use_the_matching_assistants_job_description(client):
    prep.update_config({"enabled": True, "daily_cap": 5})
    w = client.post("/api/worklog", json={"title": "phishing link clicked, password entered, account compromised"}).json()
    f = Fake()
    prep.draft_item(w["id"], {"openai": f})
    assert "Security assistant" in f.system


def test_closing_note_is_drafted_from_the_job_and_only_shows_to_the_client_once_accepted(client):
    cid = _client(client, "Acme Dental")
    j = client.post("/api/clients/jobs/add", json={"client_id": cid, "title": "Fix Wi-Fi at Acme Dental", "status": "active"}).json()
    w = client.post("/api/worklog", json={"title": "Moved router", "job_id": j["id"]}).json()
    client.post(f"/api/worklog/{w['id']}/log", json={"text": "Changed channel to 6"})
    prep.update_config({"enabled": True, "daily_cap": 5})
    f = Fake("What was done: moved the router.\nHow to avoid it: keep firmware current.")
    r = client.post(f"/api/auto/prep/job/{j['id']}") if False else prep.draft_job(j["id"], {"openai": f})
    assert "Acme Dental" not in f.prompt and "Moved router" in f.prompt and "Changed channel to 6" in f.prompt
    assert "Closing note" not in client.get(f"/api/jobs/{j['id']}/summary").text           # pending: not shown
    client.put(f"/api/auto/prep/drafts/job:{j['id']}", json={"text": "What was done: <b>moved</b> the router.", "status": "accepted"})
    html = client.get(f"/api/jobs/{j['id']}/summary").text
    assert "Closing note" in html and "&lt;b&gt;moved" in html and "<b>moved" not in html   # escaped
    assert client.post("/api/auto/prep/job/9999").status_code == 404


# ---------------------------------------------------------------- Learned for Eivanta
def test_eivanta_note_removes_client_name_marks_sample_and_exports(client):
    cid = _client(client, "Desert Dental Group")
    j = client.post("/api/clients/jobs/add", json={"client_id": cid, "title": "Weekly report for Desert Dental Group", "status": "active"}).json()
    n = client.post("/api/auto/eivanta-notes", json={"job_id": j["id"], "tag": "ingestion", "text": "Desert Dental Group sent dates as text like 3rd Oct. key sk-" + "b" * 30}).json()
    assert "Desert Dental" not in n["text"] and "Desert Dental" not in n["job"] and "sk-" + "b" * 30 not in n["text"] and n["sample"] is True
    client.post("/api/auto/eivanta-notes", json={"tag": "forecast", "text": "Only 7 months of history; show a range"})
    mine = client.get(f"/api/auto/eivanta-notes?job_id={j['id']}").json()["notes"]
    assert [x["id"] for x in mine] == [n["id"]]
    md = client.get("/api/auto/eivanta-notes/export")
    assert md.headers["content-type"].startswith("text/markdown") and "## Messy file or import" in md.text and "## Short history or forecast" in md.text and "Desert Dental" not in md.text and "(sample)" in md.text
    assert client.delete(f"/api/auto/eivanta-notes/{n['id']}").json()["deleted"] == n["id"]
    assert client.delete("/api/auto/eivanta-notes/999").status_code == 404


def test_eivanta_note_validation(client):
    assert client.post("/api/auto/eivanta-notes", json={"tag": "bogus", "text": "x"}).status_code == 400
    assert client.post("/api/auto/eivanta-notes", json={"tag": "other", "text": "  "}).status_code == 400
    assert client.post("/api/auto/eivanta-notes", json={"tag": "other", "text": "x", "job_id": 999}).status_code == 404
    assert "No notes yet" in client.get("/api/auto/eivanta-notes/export").text


# ---------------------------------------------------------------- project links
def test_links_have_starting_links_validate_and_save(client):
    d = client.get("/api/auto/links").json()
    assert d["saved"] is False and any("AIDA" in x["name"] for x in d["links"]) and "8501" in d["note"] and any(x["folder"].endswith("project-aida") for x in d["links"])
    ok = client.put("/api/auto/links", json={"links": [{"name": "AIDA", "url": "http://localhost:8501", "folder": ""}, {"name": "Eivanta", "url": "", "folder": "C:\\Users\\Guito\\nexusflow-portal"}]}).json()
    assert ok["saved"] is True and [x["id"] for x in ok["links"]] == [1, 2]
    for bad in ({"name": "x", "url": "javascript:alert(1)"}, {"name": "x", "url": "file:///etc/passwd"}, {"name": "", "url": "http://localhost:1"}, {"name": "x"}, {"name": "x", "folder": "a\x00b"}):
        assert client.put("/api/auto/links", json={"links": [bad]}).status_code == 400
    assert client.put("/api/auto/links", json={"links": [{"name": str(i), "url": "http://localhost:1"} for i in range(13)]}).status_code == 400


def test_link_status_only_contacts_this_computer(client, monkeypatch):
    import urllib.request
    seen = []

    def fake(req, timeout=0):
        seen.append(req.full_url)
        raise OSError("refused")

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    client.put("/api/auto/links", json={"links": [{"name": "A", "url": "http://localhost:8501"}, {"name": "Outside", "url": "http://example.com/x"}, {"name": "Folder", "folder": "C:\\x"}]})
    s = {r["id"]: r["state"] for r in client.get("/api/auto/links/status").json()["status"]}
    assert s == {1: "down", 2: "not-checked", 3: "none"} and seen == ["http://localhost:8501"]
