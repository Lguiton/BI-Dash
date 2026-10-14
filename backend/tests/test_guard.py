from datetime import datetime, timedelta, timezone

from app.services import backups, guard, workspaces


def test_host_rules():
    for ok in ("localhost:8020", "127.0.0.1:3012", "localhost", "[::1]:8020", "LOCALHOST:8020"):
        assert guard.host_ok(ok), ok
    for bad in ("evil.example.com", "evil.example.com:8020", "localhost.evil.com", "127.0.0.1.evil.com:80", "", None, "192.168.1.5:8020"):
        assert not guard.host_ok(bad), bad


def test_origin_rules():
    cors = ["http://localhost:3012"]
    assert guard.origin_ok("GET", "http://evil.com", "localhost:8020", cors)                       # reads are left to CORS
    assert guard.origin_ok("POST", "http://localhost:3012", "localhost:8020", cors)
    assert guard.origin_ok("POST", None, "localhost:8020", cors)                                   # curl / scripts
    assert not guard.origin_ok("POST", "http://evil.com", "localhost:8020", cors)
    assert not guard.origin_ok("DELETE", "http://localhost:3012", "localhost:8020", cors, "cross-site")
    assert guard.origin_ok("PUT", "http://localhost:8020", "localhost:8020", cors)                 # same host


def test_middleware_blocks_bad_host_and_foreign_writes_and_adds_headers(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert client.get("/health", headers={"host": "evil.example.com"}).status_code == 400
    r = client.post("/api/biz-packs/retail-sales/sample", headers={"origin": "http://evil.example.com"})
    assert r.status_code == 403
    assert client.post("/api/biz-packs/retail-sales/sample", headers={"origin": "http://localhost:3012"}).status_code == 200


def test_daily_backup_runs_once_and_catches_up(client):
    p = workspaces.path_of("real")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")
    now = datetime.now(timezone.utc)
    assert backups.daily_tick(now) == ["daily-backup"]
    assert backups.daily_tick(now + timedelta(hours=5)) == []                    # not again the same day
    assert backups.daily_tick(now + timedelta(hours=21)) == ["daily-backup"]      # the computer was off; catches up when it is back on
    assert any(b["kind"] == "daily" for b in backups.list_backups("real"))


def test_backup_endpoint_can_target_real(client):
    p = workspaces.path_of("real")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")
    r = client.post("/api/backups?workspace=real", json={})
    assert r.status_code == 200 and r.json()["kind"] == "manual"
    assert client.post("/api/backups?workspace=../etc", json={}).status_code == 400
