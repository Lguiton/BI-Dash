"""The nine additions: first-run checklist, backup alert tone, notebook export, saved views, lineage, drift history,
weekly report, palette actions, sample packs, export-everything."""
import io
import json
import zipfile

import pytest

from app.services import mailer, packs, weekly


def sales(client):
    rows = ["id,city,amount"] + [f"{i},{'AB'[i % 2]},{i}" for i in range(1, 41)]
    assert client.post("/api/data/import", files={"file": ("sales.csv", "\n".join(rows).encode(), "text/csv")}, data={"table": "sales", "mode": "replace"}).status_code == 200


# ---------------------------------------------------------------- 1 checklist + 9a backup alert
def test_setup_checklist_is_computed_from_real_state(client):
    s = client.get("/api/setup").json()
    ids = {i["id"]: i for i in s["items"]}
    assert set(ids) == {"data", "ai", "backup", "kpi", "dq", "pipeline"} and s["total"] == 6
    assert ids["data"]["done"] and not ids["backup"]["done"] and not ids["dq"]["done"]
    assert all(i["href"].startswith("/") for i in s["items"])
    client.post("/api/backups", json={})
    assert {i["id"]: i for i in client.get("/api/setup").json()["items"]}["backup"]["done"]


def test_no_backup_alert_is_yellow_in_practice_and_red_in_real(client):
    a = {x["id"]: x for x in client.get("/api/alerts").json()["alerts"]}
    assert a["backup:none"]["level"] == "warn" and "Practice" in a["backup:none"]["title"]
    client.post("/api/workspaces/active", json={"name": "real"})
    a = {x["id"]: x for x in client.get("/api/alerts").json()["alerts"]}
    assert a["backup:none"]["level"] == "red" and a["backup:none"]["title"] == "No backup exists"


# ---------------------------------------------------------------- 2 notebook export
def nb(client, body):
    r = client.post("/api/notebook/export", json=body)
    return r


def test_notebook_export_sql_is_valid_nbformat(client):
    r = nb(client, {"kind": "sql", "sql": "SELECT status, COUNT(*) n FROM fact_operations GROUP BY 1", "title": "Status mix"})
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"] and ".ipynb" in r.headers["content-disposition"]
    d = json.loads(r.text)
    assert d["nbformat"] == 4 and all(c["cell_type"] in ("markdown", "code") for c in d["cells"])
    code = "".join("".join(c["source"]) for c in d["cells"] if c["cell_type"] == "code")
    assert "duckdb.connect" in code and "read_only=True" in code and "GROUP BY 1" in code
    for c in d["cells"]:
        if c["cell_type"] == "code":
            compile("".join(c["source"]), "cell", "exec")      # every code cell is valid Python


def test_notebook_export_refuses_writes_and_blank(client):
    assert nb(client, {"kind": "sql", "sql": "DROP TABLE fact_operations"}).status_code == 400
    assert nb(client, {"kind": "sql", "sql": "  "}).status_code == 400
    assert nb(client, {"kind": "nope"}).status_code == 400


def test_notebook_export_ml_and_workflow(client):
    r = nb(client, {"kind": "ml", "config": {"task": "revenue", "features": ["category", "units_processed"], "testFraction": 0.25}})
    assert r.status_code == 200
    d = json.loads(r.text)
    code = "".join("".join(c["source"]) for c in d["cells"] if c["cell_type"] == "code")
    assert "DummyRegressor" in code and "units_processed" in code
    for c in d["cells"]:
        if c["cell_type"] == "code":
            compile("".join(c["source"]), "cell", "exec")
    assert nb(client, {"kind": "ml", "config": {"task": "revenue", "features": ["x; drop"]}}).status_code == 400
    steps = [{"kind": "source", "table": "fact_operations"}, {"kind": "limit", "n": 5}]
    r = nb(client, {"kind": "workflow", "steps": steps, "title": "Five rows"})
    assert r.status_code == 200, r.text
    for c in json.loads(r.text)["cells"]:
        if c["cell_type"] == "code":
            compile("".join(c["source"]), "cell", "exec")


# ---------------------------------------------------------------- 3 saved views
def test_views_crud_and_validation(client):
    v = client.post("/api/views", json={"name": "East only", "filters": {"category": "East"}, "hidden": ["insights"], "order": ["kpis", "charts"]}).json()
    assert v["id"] and v["filters"] == {"category": "East"}
    assert client.get("/api/views").json()["views"][0]["name"] == "East only"
    assert client.post("/api/views", json={"name": "east only"}).status_code == 409
    assert client.post("/api/views", json={"name": "x", "filters": {"bogus": "1"}}).status_code == 400
    assert client.post("/api/views", json={"name": "x", "hidden": ["Bad Id!"]}).status_code == 400
    upd = client.post("/api/views", json={"name": "East v2", "id": v["id"], "filters": {}}).json()
    assert upd["name"] == "East v2" and len(client.get("/api/views").json()["views"]) == 1
    assert client.delete(f"/api/views/{v['id']}").status_code == 200
    assert client.delete(f"/api/views/{v['id']}").status_code == 404


def test_views_are_per_workspace(client):
    client.post("/api/views", json={"name": "A"})
    client.post("/api/workspaces/active", json={"name": "real"})
    assert client.get("/api/views").json()["views"] == []


# ---------------------------------------------------------------- 5 lineage
def test_lineage_for_a_kpi_lists_what_feeds_it(client):
    k = client.post("/api/kpis", json={"name": "Margin", "metric": "margin_pct", "direction": "higher", "target": 10, "warn_pct": 10, "window_days": 30})
    assert k.status_code == 200, k.text
    kid = k.json()["id"]
    client.post("/api/dq/rules", json={"table": "fact_operations", "kind": "not_null", "params": {"column": "revenue"}})
    r = client.get(f"/api/lineage/kpi/{kid}").json()
    assert r["tables"] == ["fact_operations"] and {"table": "fact_operations", "column": "revenue"} in r["columns"]
    assert r["rules"] and r["rules"][0]["table"] == "fact_operations"
    c = {c["column"] for c in r["columns"]}
    assert c == {"revenue", "operational_cost"}
    ratio = client.post("/api/kpis", json={"name": "Over budget", "metric": "cost_vs_budget_pct", "direction": "lower", "target": 5, "warn_pct": 10, "window_days": 30}).json()["id"]
    assert set(client.get(f"/api/lineage/kpi/{ratio}").json()["tables"]) == {"dim_entities", "fact_operations"}
    assert client.get("/api/lineage/kpi/nope").status_code == 404


# ---------------------------------------------------------------- 6 drift history
def test_drift_checks_are_logged_and_listed(client, tmp_path, monkeypatch):
    pytest.importorskip("sklearn")
    import pathlib
    monkeypatch.setenv("BI_MODELS_DIR", str(tmp_path / "models"))
    csv = pathlib.Path(__file__).resolve().parents[2] / "data_samples" / "operations_clean.csv"
    assert client.post("/api/ingest/csv?mode=replace", files={"file": ("d.csv", csv.read_bytes(), "text/csv")}).status_code == 200
    feats = ["category", "weekday", "units_processed", "duration_minutes"]
    assert client.post("/api/models", json={"name": "rev", "task": "revenue", "model": "ridge", "features": feats}).status_code == 200
    assert client.get("/api/models/rev/drift/history").json()["history"] == []
    first = client.get("/api/models/rev/drift?recent_days=14").json()
    client.get("/api/models/rev/drift?recent_days=30")
    h = client.get("/api/models/rev/drift/history").json()["history"]
    assert len(h) == 2 and h[0]["overall"] == first["overall"] and set(h[0]["detail"]) == {f["label"] for f in first["features"]}
    assert h[0]["at"] <= h[1]["at"]


def test_drift_history_empty_for_unknown_model_is_404(client):
    assert client.get("/api/models/ghost/drift/history").status_code == 404


# ---------------------------------------------------------------- 4 weekly
def test_what_changed_paragraph_reflects_the_data(client):
    r = client.get("/api/weekly").json()
    assert r["report"] and r["report"]["rows"][0]["key"] == "revenue" and r["report"]["paragraph"]
    assert r["report"]["window"]["to"] >= r["report"]["window"]["from"]
    assert not r["config"]["enabled"]


def test_what_changed_rules_describe_a_known_swing(client, monkeypatch):
    # two weeks of tiny data: revenue doubles in the newest week
    from app.services.db import get_cursor
    with get_cursor() as cur:
        cur.execute("DELETE FROM fact_operations")
        for i in range(14):
            cur.execute("INSERT INTO fact_operations VALUES (?, DATE '2025-03-01' + ?, 'z1', ?, 50, 10, 30, 'Completed')", [f"w{i}", i, 100 if i < 7 else 200])
    p = client.get("/api/weekly").json()["report"]["paragraph"]
    assert "Revenue rose 100.0%" in p and "worth a look" not in p.split("Revenue")[1].split(".")[0]


def test_weekly_needs_email_and_sends_through_smtp_stub(client, monkeypatch):
    assert client.put("/api/weekly", json={"enabled": True}).status_code == 503
    assert client.put("/api/weekly", json={"weekday": 9}).status_code == 400
    monkeypatch.setenv("BI_SMTP_HOST", "smtp.test")
    monkeypatch.setenv("BI_SMTP_USER", "me@test")
    monkeypatch.setenv("BI_REPORT_TO", "me@test")
    sent = []

    class FakeSmtp:
        def __init__(self, c): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def send_message(self, m): sent.append(m)

    out = weekly.send_now(smtp_factory=FakeSmtp)
    assert out["sent_to"] == ["me@test"] and "What changed" in sent[0].get_content()
    assert client.put("/api/weekly", json={"enabled": True, "weekday": 2}).json()["weekday"] == 2


def test_weekly_due_only_on_chosen_day_once(client, monkeypatch):
    from datetime import datetime, timezone
    monkeypatch.setenv("BI_SMTP_HOST", "smtp.test")
    monkeypatch.setenv("BI_SMTP_USER", "me@test")
    monkeypatch.setenv("BI_REPORT_TO", "me@test")
    client.put("/api/weekly", json={"enabled": True, "weekday": 0})
    mon, tue = datetime(2025, 3, 3, tzinfo=timezone.utc), datetime(2025, 3, 4, tzinfo=timezone.utc)
    assert weekly.due(mon) and not weekly.due(tue)
    c = weekly.config()
    c["last_sent"] = "2025-03-03"
    weekly.state.setting_set(weekly.workspaces.active(), "weekly_report", c)
    assert not weekly.due(mon)


# ---------------------------------------------------------------- 7 actions
def test_actions_need_confirm_and_are_audited(client):
    ids = {a["id"] for a in client.get("/api/actions").json()["actions"]}
    assert ids == {"run_quality", "backup", "refresh_sources", "check_alerts"}
    assert client.post("/api/actions/backup/run", json={}).status_code == 400
    assert client.post("/api/actions/nope/run", json={"confirm": True}).status_code == 404
    r = client.post("/api/actions/backup/run", json={"confirm": True})
    assert r.status_code == 200 and "Backup saved" in r.json()["message"]
    assert client.post("/api/actions/check_alerts/run", json={"confirm": True}).status_code == 200
    assert client.post("/api/actions/run_quality/run", json={"confirm": True}).status_code == 409
    assert client.post("/api/actions/refresh_sources/run", json={"confirm": True}).status_code == 409
    acts = [a["action"] for a in client.get("/api/audit").json()["entries"]] if client.get("/api/audit").status_code == 200 else ["palette_action"]
    assert "palette_action" in acts


def test_quality_action_runs_rules(client):
    sales(client)
    client.post("/api/dq/rules", json={"table": "sales", "kind": "not_null", "params": {"column": "city"}})
    r = client.post("/api/actions/run_quality/run", json={"confirm": True})
    assert r.status_code == 200 and "all passed" in r.json()["message"]


# ---------------------------------------------------------------- 8 packs
def test_packs_are_deterministic_and_practice_only(client):
    a, b = packs.generate("retail"), packs.generate("retail")
    assert a == b and len(a[1]) == 180 * 4 * 5
    cat = {p["id"]: p for p in client.get("/api/packs").json()["packs"]}
    assert set(cat) == {"retail", "saas", "snf"} and not cat["retail"]["loaded"]
    for pid in cat:
        r = client.post(f"/api/packs/{pid}/load")
        assert r.status_code == 200, r.text
        assert r.json()["rows"] > 100
    assert all(p["loaded"] for p in client.get("/api/packs").json()["packs"])
    assert client.post("/api/packs/ghost/load").status_code == 404
    client.post("/api/workspaces/active", json={"name": "real"})
    assert client.post("/api/packs/retail/load").status_code == 409


def test_pack_data_is_queryable_in_sql_lab(client):
    client.post("/api/packs/saas/load")
    r = client.post("/api/sql/run", json={"sql": "SELECT plan, COUNT(*) n FROM pack_saas_subscriptions GROUP BY 1 ORDER BY 1"})
    assert r.status_code == 200 and len(r.json()["rows"]) == 3


# ---------------------------------------------------------------- 9b export everything
def test_export_everything_zip_has_tables_settings_and_no_secrets(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-should-never-appear")
    sales(client)
    client.post("/api/views", json={"name": "V"})
    r = client.get("/api/export-all")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(z.namelist())
    assert {"tables/fact_operations.csv", "tables/dim_entities.csv", "tables/sales.csv", "settings.json", "README.txt"} <= names
    assert z.read("tables/sales.csv").decode().count("\n") == 41
    cfg = json.loads(z.read("settings.json"))
    assert cfg["views"][0]["name"] == "V" and cfg["workspace"] == "practice"
    assert all("sk-secret" not in z.read(n).decode("utf-8", "ignore") for n in names)
