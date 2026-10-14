import pytest

from app.services import auth


@pytest.fixture()
def secured(client, monkeypatch, tmp_path):
    monkeypatch.setenv("BI_AUTH", "1")
    monkeypatch.setenv("BI_OWNER_PASSWORD", "correct horse battery")
    auth.init()
    auth._fails.clear()
    return client


def test_off_by_default(client):
    assert client.get("/api/auth/status").json() == {"enabled": False, "authenticated": True}
    assert client.get("/api/ops").status_code == 200


def test_everything_needs_login_when_on(secured):
    c = secured
    assert c.get("/health").status_code == 200
    assert c.get("/api/auth/status").json() == {"enabled": True, "authenticated": False}
    for path in ("/api/ops", "/metrics", "/api/pm", "/api/sources"):
        assert c.get(path).status_code == 401, path
    assert c.post("/api/auth/login", json={"password": "wrong"}).status_code == 401
    r = c.post("/api/auth/login", json={"password": "correct horse battery"})
    assert r.status_code == 200 and "httponly" in r.headers["set-cookie"].lower() and "samesite=lax" in r.headers["set-cookie"].lower()
    assert c.get("/api/ops").status_code == 200 and c.get("/api/auth/status").json()["authenticated"]
    c.post("/api/auth/logout")
    assert c.get("/api/ops").status_code == 401


def test_cross_site_writes_are_blocked(secured):
    c = secured
    c.post("/api/auth/login", json={"password": "correct horse battery"})
    assert c.post("/api/pm/example", json={}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert c.post("/api/pm/example", json={}, headers={"Origin": "http://localhost:3000"}).status_code == 200


def test_throttle_and_tampering(secured):
    c = secured
    for _ in range(5):
        assert c.post("/api/auth/login", json={"password": "nope"}).status_code == 401
    assert c.post("/api/auth/login", json={"password": "correct horse battery"}).status_code == 429
    tok = auth.make_token()
    assert auth.valid_token(tok) and not auth.valid_token(tok[:-2] + "00") and not auth.valid_token(None) and not auth.valid_token("a.b")
    assert not auth.valid_token(auth.make_token(now=1000))


def test_change_password_signs_out_old_sessions(secured):
    c = secured
    auth._fails.clear()
    c.post("/api/auth/login", json={"password": "correct horse battery"})
    old = c.cookies.get(auth.COOKIE)
    assert c.post("/api/auth/change-password", json={"current": "bad", "new": "another long password"}).status_code == 401
    assert c.post("/api/auth/change-password", json={"current": "correct horse battery", "new": "short"}).status_code == 400
    assert c.post("/api/auth/change-password", json={"current": "correct horse battery", "new": "another long password"}).status_code == 200
    assert not auth.valid_token(old)
    assert c.get("/api/ops").status_code == 200


def test_startup_refuses_without_password(monkeypatch, client):
    monkeypatch.setenv("BI_AUTH", "1")
    monkeypatch.delenv("BI_OWNER_PASSWORD", raising=False)
    auth._file().unlink(missing_ok=True)
    with pytest.raises(RuntimeError):
        auth.init()
    monkeypatch.setenv("BI_OWNER_PASSWORD", "short")
    with pytest.raises(auth.AuthError):
        auth.init()
