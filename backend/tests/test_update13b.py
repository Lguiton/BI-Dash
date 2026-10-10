"""Update 13, part 2: quality rules, pipelines, ops, model registry, security, web tables, PM calendar/rules, tool map, knowledge search."""
import pathlib
import socket

import pytest

from app.services import pipelines, security, seclogs, selfaudit, toolmap, webtable

ROOT = pathlib.Path(__file__).resolve().parents[2]


def import_sales(client, n=60, blanks=True):
    rows = ["id,city,amount,note"] + [f"{i},{'AB'[i % 2]},{i * 3},{'' if blanks and i % 10 == 0 else 'x'}" for i in range(1, n + 1)]
    r = client.post("/api/data/import", files={"file": ("sales.csv", "\n".join(rows).encode(), "text/csv")}, data={"table": "sales", "mode": "replace"})
    assert r.status_code == 200, r.text


# ------------------------------------------------------------------ data quality rules
def test_dq_rule_fails_with_a_sample_and_passes_when_fixed(client):
    import_sales(client)
    assert client.post("/api/dq/rules", json={"table": "sales", "kind": "not_null", "params": {"column": "note"}}).status_code == 200
    r = client.post("/api/dq/run?table=sales").json()
    assert r["failed"] == 1 and r["results"][0]["failing"] == 6 and r["results"][0]["sample"]
    import_sales(client, blanks=False)
    assert client.post("/api/dq/run?table=sales").json()["failed"] == 0
    assert len(client.get("/api/dq/history").json()["runs"]) == 2


def test_dq_rules_are_validated_and_scoped_to_real_columns(client):
    import_sales(client)
    bad = [{"table": "sales", "kind": "nope", "params": {}}, {"table": "sales", "kind": "not_null", "params": {"column": "ghost"}},
           {"table": "sales", "kind": "range", "params": {"column": "amount", "min": 9, "max": 1}}, {"table": "missing", "kind": "row_count", "params": {"min": 1}}]
    for b in bad:
        assert client.post("/api/dq/rules", json=b).status_code in (400, 404), b


def test_dq_failure_raises_an_alert_and_suggestions_exist(client):
    import_sales(client)
    sug = client.get("/api/dq/suggest?table=sales").json()["suggestions"]
    assert sug and all("why" in s for s in sug)
    client.post("/api/dq/rules", json={"table": "sales", "kind": "range", "params": {"column": "amount", "max": 10}})
    client.post("/api/dq/run?table=sales")
    ids = [a["id"] for a in client.get("/api/alerts").json()["alerts"]]
    assert any("dq" in i for i in ids)


# ------------------------------------------------------------------ pipelines
def test_pipeline_runs_in_order_and_records_history(client):
    p = client.post("/api/pipelines", json={"name": "p", "tasks": [{"id": "a", "kind": "backup"}, {"id": "b", "kind": "backup", "depends_on": ["a"]}]}).json()
    r = client.post(f"/api/pipelines/{p['id']}/run").json()
    assert r["ok"] and [t["id"] for t in r["results"]] == ["a", "b"]
    assert len(client.get(f"/api/pipelines/{p['id']}/history").json()["runs"]) == 1


def test_pipeline_cycles_and_unknown_dependencies_are_refused(client):
    for tasks in ([{"id": "a", "kind": "backup", "depends_on": ["b"]}, {"id": "b", "kind": "backup", "depends_on": ["a"]}],
                  [{"id": "a", "kind": "backup", "depends_on": ["zzz"]}],
                  [{"id": "a", "kind": "backup"}, {"id": "a", "kind": "backup"}],
                  [{"id": "a", "kind": "rm -rf"}]):
        assert client.post("/api/pipelines", json={"name": "x", "tasks": tasks}).status_code == 400


def test_failed_task_retries_then_skips_dependents(client, monkeypatch):
    calls = []
    monkeypatch.setattr(pipelines.time, "sleep", lambda s: None)

    def boom(task):
        calls.append(task["id"])
        raise pipelines.PipelineError("nope")
    monkeypatch.setattr(pipelines, "_do", boom)
    p = client.post("/api/pipelines", json={"name": "f", "tasks": [{"id": "a", "kind": "backup", "retries": 2}, {"id": "b", "kind": "backup", "depends_on": ["a"]}]}).json()
    r = client.post(f"/api/pipelines/{p['id']}/run").json()
    assert calls == ["a", "a", "a"]
    assert not r["ok"] and r["results"][0]["status"] == "failed" and r["results"][1]["status"] == "skipped"


def test_pipeline_workflow_and_dq_tasks_need_real_references(client):
    for t in ({"id": "w", "kind": "workflow", "ref": 99, "table": "x"}, {"id": "q", "kind": "dq", "ref": "sales"}, {"id": "s", "kind": "source", "ref": 99}):
        assert client.post("/api/pipelines", json={"name": "x", "tasks": [t]}).status_code == 400


# ------------------------------------------------------------------ ops
def test_ops_summary_and_prometheus_text(client):
    client.get("/health")
    client.get("/api/kpis")
    o = client.get("/api/ops").json()
    assert o["requests"] >= 2 and "slowest" in o and "files" in o
    txt = client.get("/metrics")
    assert txt.status_code == 200 and "text/plain" in txt.headers["content-type"] and "# TYPE" in txt.text
    assert "/api/kpis" in txt.text


def test_llm_monitor_reports_latency_and_no_cost_without_prices(client, monkeypatch):
    from app.services import state
    for k in ("GOOGLE", "OPENAI", "ANTHROPIC"):
        monkeypatch.delenv(f"BI_PRICE_{k}_IN", raising=False)
    now = state.now()
    for s in (0.5, 1.5, 4.0):
        state.run("INSERT INTO ai_log (created_at, question, provider, model, kind, input_tokens, output_tokens, ok, charted, workspace, seconds) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (now, "q", "google", "m", "simple", 100, 50, 1, 0, "practice", s))
    j = client.get("/api/ops/llm").json()
    g = [p for p in j["providers"] if p["provider"] == "google"][0]
    assert g["calls"] == 3 and g["max_s"] == 4.0 and g["avg_s"] == 2.0 and j["total_cost_usd"] is None
    monkeypatch.setenv("BI_PRICE_GOOGLE_IN", "1")
    monkeypatch.setenv("BI_PRICE_GOOGLE_OUT", "2")
    assert client.get("/api/ops/llm").json()["total_cost_usd"] == pytest.approx(0.0006, abs=1e-4)


# ------------------------------------------------------------------ model registry
@pytest.fixture()
def big(client):
    csv = ROOT / "data_samples" / "operations_clean.csv"
    assert client.post("/api/ingest/csv?mode=replace", files={"file": ("d.csv", csv.read_bytes(), "text/csv")}).status_code == 200
    return client


FEATS = ["category", "weekday", "units_processed", "duration_minutes"]


def test_registry_register_stage_predict_drift_delete(big, tmp_path, monkeypatch):
    pytest.importorskip("sklearn")
    monkeypatch.setenv("BI_MODELS_DIR", str(tmp_path / "models"))
    r = big.post("/api/models", json={"name": "rev", "task": "revenue", "model": "ridge", "features": FEATS})
    assert r.status_code == 200 and r.json()["version"] == 1
    assert big.post("/api/models", json={"name": "rev", "task": "revenue", "model": "ridge", "features": FEATS}).json()["version"] == 2
    assert big.put("/api/models/rev/versions/2/stage", json={"stage": "production"}).json()["stage"] == "production"
    card = big.get("/api/models/rev/card").json()
    assert card["inputs"] and card["caveats"]
    row = {"category": "Fleet", "weekday": "Monday", "units_processed": 50, "duration_minutes": 200}
    p = big.post("/api/models/rev/predict", json={"rows": [row]}).json()
    assert isinstance(p["predictions"][0]["prediction"], float) and p["version"] == 2 if "version" in p else True
    far = big.post("/api/models/rev/predict", json={"rows": [{**row, "units_processed": 99999}]}).json()
    assert far["warnings"]
    assert big.post("/api/models/rev/predict", json={"rows": [{**row, "bogus": 1}]}).status_code == 400
    assert big.post("/api/models/rev/predict", json={"rows": [{**row, "weekday": "Funday"}]}).status_code in (200, 400)
    d = big.get("/api/models/rev/drift").json()
    assert d["overall"] in ("stable", "some drift", "significant drift") and "can't see" in d["note"]
    assert big.delete("/api/models/rev/versions/1").status_code == 200
    assert big.get("/api/models/nope/card").status_code == 404


def test_registry_names_are_slugged_and_stages_validated(big, tmp_path, monkeypatch):
    pytest.importorskip("sklearn")
    models = tmp_path / "models"
    monkeypatch.setenv("BI_MODELS_DIR", str(models))
    r = big.post("/api/models", json={"name": "../evil", "task": "revenue", "model": "ridge", "features": FEATS})
    assert r.status_code == 200 and ".." not in r.json()["name"] and "/" not in r.json()["name"]
    written = [p for p in tmp_path.rglob("*.joblib")]
    assert written and all(models in p.parents for p in written)           # nothing escaped the models folder
    assert big.post("/api/models", json={"name": "", "task": "revenue", "model": "ridge", "features": FEATS}).status_code in (400, 422)
    name = r.json()["name"]
    assert big.put(f"/api/models/{name}/versions/1/stage", json={"stage": "live"}).status_code == 422


# ------------------------------------------------------------------ security: logs
def test_sample_log_finds_the_takeover_and_probing():
    a = seclogs.analyze(seclogs.sample_log(), 2026)
    ids = " ".join(f["id"] for f in a["findings"])
    assert "brute-success:203.0.113.50" in ids and "brute:198.51.100.7" in ids and "sqli" in ids
    crit = [f for f in a["findings"] if f["severity"] == "critical"]
    assert crit and crit[0]["evidence"] and "leads" in a["caveat"].lower()


def test_log_search_and_limits(client):
    j = client.post("/api/security/logs/search", json={"text": seclogs.sample_log(), "query": "root", "year": 2026}).json()
    assert j["matches"] and all("root" in m["line"].lower() for m in j["matches"])
    assert client.post("/api/security/logs/analyze", json={"text": ""}).status_code == 422
    assert client.get("/api/security/logs/sample").json()["text"]


def test_clean_log_has_no_findings():
    ok = "\n".join(f'192.0.2.{i} - - [10/Oct/2026:10:00:0{i} +0000] "GET /index.html HTTP/1.1" 200 10' for i in range(1, 6))
    assert seclogs.analyze(ok)["findings"] == []


# ------------------------------------------------------------------ security: public-host guard
def fake(ip):
    return lambda host, port, type=None: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]


@pytest.mark.parametrize("host,ip", [("intranet.example.com", "10.0.0.5"), ("a.example.com", "127.0.0.1"), ("meta.example.com", "169.254.169.254"), ("b.example.com", "192.168.1.9")])
def test_private_resolutions_are_refused(host, ip):
    with pytest.raises(security.SecError):
        security.resolve_public(host, resolver=fake(ip))


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "10.1.2.3", "169.254.169.254", "[::1]", "http://x", "a b.com", "exa_mple.com"])
def test_bad_hosts_are_refused_without_network(host):
    with pytest.raises(security.SecError):
        security.resolve_public(host, resolver=fake("10.0.0.1"))


def test_public_resolution_is_accepted():
    assert security.resolve_public("example.com", resolver=fake("93.184.216.34")) == "93.184.216.34"


def test_header_and_cert_checks_use_fetchers_but_still_guard_the_host(monkeypatch):
    orig = security.resolve_public
    monkeypatch.setattr(security, "resolve_public", lambda h: orig(h, resolver=fake("93.184.216.34")))
    out = security.check_headers("example.com", fetcher=lambda h: (200, {"server": "x"}, ""))
    assert out["score"]["pct"] < 100 and any(f["level"] == "fail" or f["level"] == "warn" for f in out["findings"])
    good = {"strict-transport-security": "max-age=31536000", "content-security-policy": "default-src 'self'", "x-content-type-options": "nosniff",
            "x-frame-options": "DENY", "referrer-policy": "no-referrer", "permissions-policy": "geolocation=()"}
    assert security.check_headers("example.com", fetcher=lambda h: (200, good, ""))["score"]["pct"] > out["score"]["pct"]
    monkeypatch.setattr(security, "resolve_public", lambda h: orig(h, resolver=fake("10.0.0.1")))
    with pytest.raises(security.SecError):
        security.check_headers("example.com", fetcher=lambda h: (200, good, ""))


def test_expired_cert_is_a_failure():
    from datetime import datetime, timezone
    info = {"cert": {"notAfter": "Jan  1 00:00:00 2020 GMT", "notBefore": "Jan  1 00:00:00 2019 GMT", "issuer": (), "subjectAltName": (("DNS", "example.com"),)}, "version": "TLSv1.3", "cipher": "x"}
    r = security.cert_report("example.com", info, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert r["days_left"] < 0 and any(f["level"] == "fail" for f in r["findings"])


def test_network_checks_are_rate_limited(client, monkeypatch):
    from app.routers import security as sr
    sr._hits.clear()
    codes = [client.get("/api/security/ports").status_code for _ in range(14)]
    sr._hits.clear()
    assert codes.count(429) >= 1 and codes[0] == 200


# ------------------------------------------------------------------ security: crypto and incidents
def test_hash_verify_and_wrong_hash():
    assert security.hash_bytes(b"abc", ["sha256"])["hashes"]["sha256"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert security.verify_hash(b"abc", "BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD")["match"]
    assert not security.verify_hash(b"abd", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")["match"]
    with pytest.raises(security.SecError):
        security.hash_bytes(b"x", ["rot13"])


def test_totp_matches_rfc6238_vector():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"            # base32 of "12345678901234567890"
    assert security.totp(secret, 59, digits=8) == "94287082"
    lab = security.totp_lab(secret, "287082", at=59)
    assert lab["verified"] is True and security.totp_lab(secret, "000000", at=59)["verified"] is False
    with pytest.raises(security.SecError):
        security.totp_lab("not base32!!", None)


def test_password_strength_is_honest_about_common_passwords():
    weak = security.password_strength("password123")
    strong = security.password_strength(security.generate("passphrase", 6)["value"])
    assert weak["score"] < strong["score"] and "assumption" in weak and strong["entropy_bits"] >= 60
    assert len(security.generate("password", 20)["value"]) == 20


def test_incident_flow(client):
    i = client.post("/api/security/incidents", json={"title": "Key leaked", "category": "credential", "severity": "high"}).json()
    assert i["status"] == "open" and i["checklist"] and not any(c["done"] for c in i["checklist"])
    u = client.patch(f"/api/security/incidents/{i['id']}", json={"tick": {"index": 0, "done": True}, "note": "rotated"}).json()
    assert u["checklist"][0]["done"] and any("rotated" in t["text"] for t in u["timeline"])
    r = client.patch(f"/api/security/incidents/{i['id']}", json={"status": "resolved"}).json()
    assert r["status"] == "resolved" and r["hours_to_resolve"] is not None
    assert client.get("/api/security/incidents").json()["stats"]["total"] == 1
    assert client.post("/api/security/incidents", json={"title": "x", "category": "alien", "severity": "high"}).status_code == 400
    assert client.patch(f"/api/security/incidents/{i['id']}", json={"tick": {"index": 99, "done": True}}).status_code == 400
    assert client.delete(f"/api/security/incidents/{i['id']}").status_code == 200
    assert client.patch("/api/security/incidents/999", json={"status": "open"}).status_code == 404


# ------------------------------------------------------------------ self-audit
def test_selfaudit_flags_untracked_secret_and_open_env_but_never_prints_the_secret(tmp_path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / ".env").write_text("GOOGLE_API_KEY=abc\n")
    (tmp_path / ".gitignore").write_text("node_modules\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "leak.py").write_text('KEY = "sk-ant-api03-' + "A" * 40 + '"\n')
    out = selfaudit.run(root=tmp_path)
    ids = {i["id"]: i for i in out["items"]}
    assert out["fails"] >= 1 and any(i["status"] == "fail" for i in out["items"])
    assert "A" * 20 not in str(out)
    assert any("leak.py" in (i["detail"] + i["title"]) for i in out["items"])
    assert ids["env-exists"]["status"] == "ok"


def test_selfaudit_endpoint(client):
    j = client.get("/api/security/audit").json()
    assert 0 <= j["score"]["pct"] <= 100 and j["items"] and "can't prove" in j["note"]


# ------------------------------------------------------------------ web tables
HTML = ("<html><body><script>var x='<table><tr><td>no</td></tr></table>'</script>"
        "<table><caption>Prices</caption><tr><th>Item</th><th>Price</th><th>Price</th></tr><tr><td>A</td><td>1,200</td><td>x</td></tr><tr><td>B<br>b</td><td>3</td></tr></table>"
        "<table><tr><td>only one row</td></tr></table></body></html>")


def test_parser_reads_headers_pads_rows_and_ignores_scripts():
    t = webtable.parse_tables(HTML)
    assert len(t) == 1 and t[0]["caption"] == "Prices"
    assert t[0]["header"] == ["Item", "Price", "Price_2"] and t[0]["rows"][1] == ["B b", "3", None]


def test_web_table_source_end_to_end(client, monkeypatch):
    monkeypatch.setattr(webtable, "fetch_page", lambda url, **k: HTML)
    monkeypatch.setattr(webtable.security, "resolve_public", lambda h, **k: "93.184.216.34")
    assert client.post("/api/sources/web-tables", json={"url": "https://example.com/p"}).json()["tables"][0]["rows"] == 2
    t = client.post("/api/sources/test", json={"kind": "html_table", "config": {"url": "https://example.com/p", "table": 0}})
    assert t.status_code == 200 and t.json()["rows"] == 2
    s = client.post("/api/sources", json={"name": "web", "kind": "html_table", "config": {"url": "https://example.com/p"}, "target": "web_prices"})
    assert s.status_code == 200
    assert client.post(f"/api/sources/{s.json()['id']}/run").status_code == 200
    assert client.get("/api/hub").json()["tables"][0]["table"] == "web_prices"


@pytest.mark.parametrize("url", ["http://example.com/x", "https://localhost/x", "https://127.0.0.1/x", "https://10.0.0.1/x", "https://example.com:8443/x", "https://user:pw@example.com/x", "ftp://example.com"])
def test_web_table_refuses_unsafe_links(client, url):
    r = client.post("/api/sources/web-tables", json={"url": url})
    assert r.status_code == 400 and "detail" in r.json()


def test_web_table_missing_table_number_lists_what_exists(monkeypatch):
    monkeypatch.setattr(webtable.security, "resolve_public", lambda h, **k: "93.184.216.34")
    with pytest.raises(webtable.WebTableError) as e:
        webtable.table("https://example.com/p", 5, fetcher=lambda u: HTML)
    assert "no table number 5" in e.value.message and "0" in e.value.message


def test_chunked_bodies_decode():
    assert webtable._dechunk(b"5\r\nhello\r\n6\r\n world\r\n0\r\n\r\n") == b"hello world"


# ------------------------------------------------------------------ PM calendar and rules
def test_calendar_places_items_on_their_days(client):
    from datetime import date
    client.post("/api/pm/items", json={"title": "Build", "status": "doing", "start_date": "2026-03-10", "duration_days": 3})
    client.post("/api/pm/items", json={"title": "Undated"})
    c = client.get("/api/pm/calendar?month=2026-03").json()
    on = {d["date"][-2:]: [i["title"] for i in d["items"]] for d in c["days"] if d["items"]}
    assert set(on) == {"10", "11", "12"} and c["unscheduled"] == 1 and c["lead_blanks"] == date(2026, 3, 1).weekday()
    assert client.get("/api/pm/calendar?month=2026-04").json()["days"][9]["items"] == []
    assert client.get("/api/pm/calendar?month=bad").status_code == 400


def test_rules_preview_changes_nothing_until_run_and_are_idempotent(client):
    iid = client.post("/api/pm/items", json={"title": "Late", "status": "doing", "start_date": "2020-01-01", "duration_days": 2, "priority": 3}).json()["id"]
    client.post("/api/pm/rules", json={"name": "late first", "trigger": "overdue", "action": "set_priority", "value": "1"})
    client.post("/api/pm/rules", json={"name": "late note", "trigger": "overdue", "action": "add_note", "value": "Chase owner"})
    pre = client.post("/api/pm/rules/run", json={}).json()
    assert len(pre["changes"]) == 2 and not pre["applied"]
    assert client.get("/api/pm").json()["items"][0]["priority"] == 3
    assert len(client.post("/api/pm/rules/run", json={"apply": True}).json()["changes"]) == 2
    it = [i for i in client.get("/api/pm").json()["items"] if i["id"] == iid][0]
    assert it["priority"] == 1 and "Chase owner" in it["notes"]
    assert client.post("/api/pm/rules/run", json={"apply": True}).json()["changes"] == []
    assert [i for i in client.get("/api/pm").json()["items"] if i["id"] == iid][0]["notes"].count("Chase owner") == 1


def test_rules_ignore_done_items_and_validate(client):
    client.post("/api/pm/items", json={"title": "Done", "status": "done", "start_date": "2020-01-01", "duration_days": 2})
    client.post("/api/pm/rules", json={"name": "r", "trigger": "overdue", "action": "set_priority", "value": "1"})
    assert client.post("/api/pm/rules/run", json={}).json()["changes"] == []
    bad = [{"name": "", "trigger": "overdue", "action": "add_note", "value": "x"}, {"name": "a", "trigger": "never", "action": "add_note", "value": "x"},
           {"name": "a", "trigger": "overdue", "action": "set_priority", "value": "9"}, {"name": "a", "trigger": "stuck", "action": "add_note", "value": "x", "days": 0},
           {"name": "a", "trigger": "overdue", "action": "move_status", "value": "limbo"}]
    for b in bad:
        assert client.post("/api/pm/rules", json=b).status_code == 400, b
    rid = client.get("/api/pm/rules").json()["rules"][0]["id"]
    client.patch(f"/api/pm/rules/{rid}", json={"enabled": False})
    assert client.post("/api/pm/rules/run", json={}).json()["rules_checked"] == 0
    assert client.delete(f"/api/pm/rules/{rid}").status_code == 200 and client.delete(f"/api/pm/rules/{rid}").status_code == 404


# ------------------------------------------------------------------ tool map and knowledge search
def test_tool_map_is_honest_about_what_is_not_built():
    m = toolmap.tool_map()
    by = {t["tool"]: t for c in m["categories"] for t in c["tools"]}
    assert by["Metasploit, C2 frameworks, fuzzers, exploit kits"]["status"] == "not_embedded"
    assert by["Nmap"]["status"] == "taught" and by["Snowflake, Databricks, BigQuery, Redshift"]["status"] == "not_embedded"
    assert set(m["counts"]) <= {"built", "partial", "taught", "not_embedded"} and sum(m["counts"].values()) == len(by)


def test_tool_map_links_point_at_real_pages():
    app = ROOT / "frontend" / "src" / "app"
    for c in toolmap.tool_map()["categories"]:
        for t in c["tools"]:
            if t["href"]:
                top = t["href"].strip("/").split("?")[0]
                assert (top == "" and (app / "page.tsx").exists()) or (app / top / "page.tsx").exists(), t


def test_knowledge_search_ranks_and_links(client):
    j = client.get("/api/kb?q=incident+checklist+evidence").json()
    assert j["results"] and j["results"][0]["score"] == 1.0 and "TF-IDF" in j["note"]
    assert any(r["href"] and "/tracks/security" in r["href"] for r in j["results"])
    assert client.get("/api/kb?q=the+of+and").json()["results"] == []
    assert client.get("/api/kb?q=zzzzqqqq").json()["results"] == []
    assert client.get("/api/kb?q=" + "a" * 300).status_code == 422


def test_security_track_is_wired_everywhere(client):
    from app.services import agents, company, manuals, quizzes
    assert "security" in manuals.MANUALS and "security" in agents.AGENTS and "security" in quizzes.QUIZZES
    assert any(d["id"] == "security" for d in client.get("/api/company").json()["disciplines"])
    ctx = agents.context("security")
    assert "audit_score_pct" in ctx and ctx["manual_steps_ticked"].endswith("/6")
    assert client.get("/api/tracks/security/dashboard").status_code in (200, 404)


# ------------------------------------------------------------------ web panel (reader + bookmarks)
READ_HTML = ("<html><head><title>Docs</title><style>x{}</style></head><body><nav>menu</nav><h1>Hello</h1><p>First <a href='/more'>more</a> text.</p>"
             "<script>alert(1)</script><p>Second.</p></body></html>")


def test_reader_returns_text_without_scripts_and_resolves_links(client, monkeypatch):
    monkeypatch.setattr(webtable.security, "resolve_public", lambda h, **k: "93.184.216.34")
    from app.services import webreader
    out = webreader.read("https://example.com/a", fetcher=lambda u: (200, "", READ_HTML))
    assert out["title"] == "Docs" and "Hello" in out["text"] and "alert" not in out["text"] and "menu" not in out["text"]
    assert out["links"][0]["url"] == "https://example.com/more"


def test_reader_rechecks_every_redirect_hop(monkeypatch):
    from app.services import webreader
    monkeypatch.setattr(webtable.security, "resolve_public", lambda h, **k: (_ for _ in ()).throw(security.SecError("private")) if h == "evil.example.com" else "93.184.216.34")
    hops = {"https://example.com/a": (302, "https://evil.example.com/x", "")}
    with pytest.raises(webtable.WebTableError):
        webreader.read("https://example.com/a", fetcher=lambda u: hops[u])
    loop = lambda u: (302, "https://example.com/again", "")           # noqa: E731
    with pytest.raises(webtable.WebTableError) as e:
        webreader.read("https://example.com/a", fetcher=loop)
    assert "redirects" in e.value.message


@pytest.mark.parametrize("url", ["http://example.com", "https://localhost/", "https://192.168.0.1/", "https://[::1]/", "https://example.com:81/"])
def test_reader_endpoint_refuses_private_or_plain_links(client, url):
    assert client.post("/api/web/read", json={"url": url}).status_code == 400


def test_bookmarks_default_save_and_validate(client):
    d = client.get("/api/web/bookmarks").json()["items"]
    assert d and all(i["url"].startswith("https://") for i in d)
    ok = client.put("/api/web/bookmarks", json={"items": [{"title": "Mine", "url": "https://example.com/x"}]})
    assert ok.json()["items"] == [{"title": "Mine", "url": "https://example.com/x"}]
    assert client.get("/api/web/bookmarks").json()["items"][0]["title"] == "Mine"
    assert client.put("/api/web/bookmarks", json={"items": [{"title": "x", "url": "javascript:alert(1)"}]}).status_code == 400
    assert client.put("/api/web/bookmarks", json={"items": [{"title": "x", "url": "http://example.com"}]}).status_code == 400
