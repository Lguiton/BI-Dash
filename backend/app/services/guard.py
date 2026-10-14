"""Request guards that protect a dashboard with no login that runs on your own computer.

* Host check: stops "DNS rebinding", where a web page you visit points its own name at 127.0.0.1 so your browser will read your data.
  Only localhost-style names are served (add more with BI_ALLOWED_HOSTS=name1,name2 when you host it).
* Origin check: a page on another site cannot change data (POST/PUT/PATCH/DELETE) even if your browser would send the request.
* Security headers on every answer."""
from __future__ import annotations

import os
from urllib.parse import urlparse

LOCAL = {"localhost", "127.0.0.1", "[::1]", "::1", "testserver"}
SAFE = ("GET", "HEAD", "OPTIONS")
HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Resource-Policy": "same-site",
}


def allowed_hosts() -> set[str]:
    extra = {h.strip().lower() for h in os.environ.get("BI_ALLOWED_HOSTS", "").split(",") if h.strip()}
    return LOCAL | extra


def host_ok(host_header: str | None) -> bool:
    h = (host_header or "").strip().lower()
    if h.startswith("["):                       # [::1]:8020
        name = h.split("]")[0] + "]"
    else:
        name = h.rsplit(":", 1)[0] if h.count(":") == 1 else h
    return name in allowed_hosts()


def origin_ok(method: str, origin: str | None, host_header: str | None, cors: list[str], fetch_site: str | None = None) -> bool:
    """True when this request may go ahead. Reads are always fine here (CORS already stops other sites reading the answer)."""
    if method in SAFE:
        return True
    if fetch_site == "cross-site":
        return False
    if not origin:
        return True                                 # curl, scripts and same-site form posts that send no Origin
    return origin in cors or urlparse(origin).netloc == (host_header or "")
