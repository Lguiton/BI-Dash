"""Single-owner login for when the dashboard is put online. Off by default (local use needs no login).

Turn it on with BI_AUTH=1 and set BI_OWNER_PASSWORD (12+ characters) in backend/.env. There are no accounts or roles:
one owner, one password. The password is stored only as a salted scrypt hash; sessions are signed, expire, and live in an
HttpOnly cookie. Failed logins are slowed down. Behind HTTPS also set BI_COOKIE_SECURE=1."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path

from app.config import db_path

COOKIE = "bi_session"
SESSION_SECONDS = int(os.environ.get("BI_SESSION_HOURS", "168")) * 3600
MIN_LEN = 12
_lock = threading.Lock()
_fails: dict[str, list[float]] = {}


class AuthError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def enabled() -> bool:
    return os.environ.get("BI_AUTH", "0") == "1"


def secure_cookie() -> bool:
    return os.environ.get("BI_COOKIE_SECURE", "0") == "1"


def _file() -> Path:
    return db_path().parent / "auth.json"


def _hash(pw: str, salt: bytes) -> str:
    return hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32).hex()


def _load() -> dict:
    try:
        return json.loads(_file().read_text())
    except (OSError, ValueError):
        return {}


def _save(d: dict) -> None:
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d))
    os.chmod(tmp, 0o600)
    os.replace(tmp, f)


def _check_len(pw: str) -> None:
    if not isinstance(pw, str) or len(pw) < MIN_LEN or len(pw) > 200:
        raise AuthError(f"The password must be {MIN_LEN} to 200 characters. A few random words is better than a clever short one.")


def init() -> None:
    """Called at start-up. Creates the secret and the owner's password hash from BI_OWNER_PASSWORD."""
    if not enabled():
        return
    d = _load()
    pw = os.environ.get("BI_OWNER_PASSWORD", "")
    if not d.get("hash"):
        if not pw:
            raise RuntimeError("BI_AUTH=1 but no password is set. Put BI_OWNER_PASSWORD=<12+ characters> in backend/.env and restart.")
        _check_len(pw)
        salt = secrets.token_bytes(16)
        d = {"salt": salt.hex(), "hash": _hash(pw, salt), "secret": secrets.token_hex(32)}
        _save(d)
    elif "secret" not in d:
        d["secret"] = secrets.token_hex(32)
        _save(d)


def _sign(payload: bytes, secret: str) -> str:
    return hmac.new(bytes.fromhex(secret), payload, hashlib.sha256).hexdigest()


def make_token(now: float | None = None) -> str:
    d = _load()
    body = base64.urlsafe_b64encode(json.dumps({"exp": int((now or time.time()) + SESSION_SECONDS), "v": d.get("gen", 0)}).encode())
    return body.decode() + "." + _sign(body, d["secret"])


def valid_token(tok: str | None, now: float | None = None) -> bool:
    if not tok or "." not in tok:
        return False
    d = _load()
    if not d.get("secret"):
        return False
    body, sig = tok.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(body.encode(), d["secret"])):
        return False
    try:
        p = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except ValueError:
        return False
    return p.get("exp", 0) > (now or time.time()) and p.get("v", 0) == d.get("gen", 0)


def _throttle(ip: str, now: float) -> None:
    with _lock:
        recent = [t for t in _fails.get(ip, []) if now - t < 900]
        _fails[ip] = recent
        if len(recent) >= 5:
            wait = int(60 * 2 ** min(len(recent) - 5, 5) - (now - recent[-1]))
            if wait > 0:
                raise AuthError(f"Too many wrong passwords. Try again in {wait} seconds.", 429)


def login(pw: str, ip: str = "?", now: float | None = None) -> str:
    now = now or time.time()
    d = _load()
    if not d.get("hash"):
        raise AuthError("Login is not set up. Set BI_OWNER_PASSWORD and restart.", 503)
    _throttle(ip, now)
    ok = isinstance(pw, str) and len(pw) <= 200 and hmac.compare_digest(_hash(pw, bytes.fromhex(d["salt"])), d["hash"])
    if not ok:
        with _lock:
            _fails.setdefault(ip, []).append(now)
        raise AuthError("Wrong password.", 401)
    with _lock:
        _fails.pop(ip, None)
    return make_token(now)


def change_password(current: str, new: str) -> str:
    d = _load()
    if not d.get("hash") or not hmac.compare_digest(_hash(current or "", bytes.fromhex(d["salt"])), d["hash"]):
        raise AuthError("The current password is wrong.", 401)
    _check_len(new)
    salt = secrets.token_bytes(16)
    d.update({"salt": salt.hex(), "hash": _hash(new, salt), "gen": d.get("gen", 0) + 1})
    _save(d)
    return make_token()


def sign_out_everywhere() -> None:
    d = _load()
    d["gen"] = d.get("gen", 0) + 1
    _save(d)


OPEN_PREFIXES = ("/api/auth/",)
OPEN_PATHS = {"/health", "/docs", "/openapi.json"}


def needs_login(path: str) -> bool:
    return enabled() and not (path in OPEN_PATHS or path.startswith(OPEN_PREFIXES))
