"""Project AIDA link: off unless configured, signed, counts only, and never any of your data or error text."""
import hashlib
import hmac
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from app.services import aida, db, metrics, sources, state

SECRET = "test-secret"
PRIVATE = "Jane Customer 4471"   # stands in for anything from your data


class FakeAida:
    def __init__(self):
        self.received = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                outer.received.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()},
                                       "body": body, "json": json.loads(body)})
                self.send_response(202)
                self.end_headers()

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/intake/errors"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def wait(self, n=1, path=None):
        deadline = time.time() + 5
        while time.time() < deadline:
            got = [r for r in self.received if path is None or r["path"] == path]
            if len(got) >= n:
                return got
            time.sleep(0.02)
        return [r for r in self.received if path is None or r["path"] == path]


@pytest.fixture()
def fake_aida(monkeypatch):
    server = FakeAida()
    monkeypatch.setenv("AIDA_INTAKE_URL", server.url)
    monkeypatch.setenv("AIDA_INTAKE_SECRET", SECRET)
    aida._last_sent.clear()
    yield server
    server.server.shutdown()


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    """Like the shared client, but server errors come back as 500 answers instead of raising in the test."""
    monkeypatch.setenv("BI_DB_PATH", str(tmp_path / "test.duckdb"))
    monkeypatch.setenv("BI_SCHEDULER", "0")
    monkeypatch.setenv("BI_SEED_DEMO", "0")
    state.close_all()
    db.close_connection()
    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    db.close_connection()
    state.close_all()


def signed_correctly(request):
    h = request["headers"]
    expected = hmac.new(SECRET.encode(), h["x-aida-timestamp"].encode() + b"." + request["body"], hashlib.sha256).hexdigest()
    return h["x-aida-product"] == "bi-dashboard" and hmac.compare_digest(expected, h["x-aida-signature"])


def test_off_unless_both_settings_are_present_and_local(monkeypatch):
    monkeypatch.delenv("AIDA_INTAKE_URL", raising=False)
    monkeypatch.delenv("AIDA_INTAKE_SECRET", raising=False)
    assert not aida.is_enabled() and aida.send_status() is False and aida.start() is None
    monkeypatch.setenv("AIDA_INTAKE_SECRET", SECRET)
    for url in ("http://example.com/intake/errors", "http://user:pw@127.0.0.1:8006/intake/errors",
                "ftp://127.0.0.1/intake/errors", "http://127.0.0.1:8006/intake/errors?x=1", "not a url"):
        monkeypatch.setenv("AIDA_INTAKE_URL", url)
        assert not aida.is_enabled(), url
    monkeypatch.setenv("AIDA_INTAKE_URL", "http://127.0.0.1:8006/intake/errors")
    assert aida.is_enabled() and aida._sibling_url("health") == "http://127.0.0.1:8006/intake/health"


def test_unhandled_error_is_reported_without_its_message(app_client, fake_aida, monkeypatch):
    def broken():
        raise ValueError(f"could not read row for {PRIVATE}")

    monkeypatch.setattr(metrics, "summary", broken)
    answer = app_client.get("/api/ops", params={"q": PRIVATE})
    assert answer.status_code == 500 and PRIVATE not in answer.text
    [report] = fake_aida.wait(1, "/intake/errors")
    assert signed_correctly(report)
    sent = report["json"]
    assert sent["error_type"] == "ValueError" and sent["route"] == "/api/ops" and sent["method"] == "GET"
    assert sent["product"] == "bi-dashboard" and len(sent["signature"]) == 16
    assert any(f["in_app"] and f["file"] == "backend/app/main.py" and f["function"] == "ops" for f in sent["frames"])
    assert all(set(f) == {"file", "line", "function", "in_app"} for f in sent["frames"])  # no source text, no locals
    assert PRIVATE not in report["body"].decode() and "4471" not in report["body"].decode()

    # the same error again within 10 minutes is not sent again
    app_client.get("/api/ops")
    time.sleep(0.3)
    assert len(fake_aida.wait(2, "/intake/errors")) == 1


def test_nothing_is_sent_when_the_link_is_off(app_client, monkeypatch):
    monkeypatch.delenv("AIDA_INTAKE_URL", raising=False)
    calls = []
    monkeypatch.setattr(aida, "_signed_post", lambda *a: calls.append(a))
    monkeypatch.setattr(metrics, "summary", lambda: 1 / 0)
    assert app_client.get("/api/ops").status_code == 500
    assert app_client.get("/health").json()["status"] == "healthy"
    assert calls == []


def test_status_carries_counts_and_ai_use_but_no_data(app_client, fake_aida, monkeypatch):
    now = state.now()
    state.run("INSERT INTO study_progress (item_id, done_at) VALUES (?, ?)", (PRIVATE, now))
    state.run("INSERT INTO study_progress (item_id, done_at) VALUES ('old', '2020-01-01 00:00:00')")
    state.run("INSERT INTO sources (workspace, name, kind) VALUES ('real', ?, 'file')", (PRIVATE,))
    state.run("INSERT INTO source_runs (source_id, at, ok, rows, message) VALUES (1, ?, 0, 0, ?)", (now, PRIVATE))
    for provider, tin, tout in (("google", 1000, 500), ("anthropic", 2000, 1000)):
        state.run("INSERT INTO ai_log (created_at, question, provider, model, input_tokens, output_tokens, ok) "
                  "VALUES (?, ?, ?, 'm', ?, ?, 1)", (now, PRIVATE, provider, tin, tout))
    state.run("INSERT INTO ai_log (created_at, question, provider, model, input_tokens, output_tokens, ok) "
              "VALUES ('2020-01-01 00:00:00', 'old', 'google', 'm', 9, 9, 1)")

    assert aida.send_status() is True
    [beat] = fake_aida.wait(1, "/intake/health")
    assert signed_correctly(beat)
    doc = beat["json"]
    assert doc["status"] == "healthy" and doc["database_reachable"] is True and doc["product"] == "bi-dashboard"
    pulse = doc["pulse"]
    assert pulse["Lessons completed"] == 2 and pulse["Lessons completed (7 days)"] == 1
    assert pulse["Data sources"] == 1 and pulse["Failed source loads (24h)"] == 1
    assert pulse["Failed pipeline runs (24h)"] == 0 and "Hours since last Real backup" not in pulse  # no backup yet
    assert all(type(v) in (int, float) for v in pulse.values()) and len(pulse) <= 12
    assert doc["ai_usage"] == {"calls_today": 2, "tokens_today": 4500}  # no prices set: no dollar figure
    assert PRIVATE not in beat["body"].decode()

    monkeypatch.setenv("BI_PRICE_GOOGLE_IN", "1")
    monkeypatch.setenv("BI_PRICE_GOOGLE_OUT", "2")
    priced = aida.ai_usage()
    assert priced["cost_usd_today"] == pytest.approx(0.002) and priced["cost_usd_month"] == pytest.approx(0.002)


def test_backup_age_is_reported(app_client, fake_aida):
    from app.services import backups, workspaces
    workspaces.activate("real")
    backups.create("manual", "real")
    assert 0 <= aida.pulse()["Hours since last Real backup"] < 0.1


def test_database_trouble_reads_as_degraded(app_client, fake_aida, monkeypatch):
    def no_database():
        raise RuntimeError("database is locked")

    monkeypatch.setattr(db, "get_cursor", no_database)
    doc = aida.status()
    assert doc["status"] == "degraded" and doc["database_reachable"] is False and "database is locked" not in json.dumps(doc)


def test_failed_scheduled_task_is_reported(app_client, fake_aida, monkeypatch):
    from app.services import backups

    def backup_fails():
        raise OSError(f"disk full writing C:/Users/{PRIVATE}/backup")

    monkeypatch.setattr(backups, "maybe_auto", backup_fails)
    monkeypatch.setattr(sources, "due", lambda: [])
    sources.tick()
    [report] = fake_aida.wait(1, "/intake/errors")
    assert report["json"]["route"] == "scheduler:backup" and report["json"]["method"] == "TASK"
    assert report["json"]["error_type"] == "OSError" and PRIVATE not in report["body"].decode()


def test_heartbeat_loop_starts_and_stops(fake_aida, monkeypatch):
    import asyncio
    monkeypatch.setattr(aida, "status", lambda: {"status": "healthy"})

    async def run():
        task = aida.start()
        assert task is not None
        for _ in range(100):
            if fake_aida.received:
                break
            await asyncio.sleep(0.05)
        await aida.stop(task)
        assert task.cancelled() or task.done()

    asyncio.run(run())
    assert fake_aida.wait(1, "/intake/health")[0]["json"] == {"status": "healthy", "product": "bi-dashboard"}
