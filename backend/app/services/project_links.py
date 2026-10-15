"""Quick links to your other projects (Eivanta Analytics, Project AIDA), shown in Settings.

A link is a name, an address to open (http or https only) and optionally a folder path to copy. The status check only ever contacts addresses
on THIS computer (localhost, 127.0.0.1, ::1), with a one-second limit, so it can't be pointed at anything else. Nothing is sent to those apps."""
from __future__ import annotations

import ipaddress
import json
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

from app.services import state

KEY = "project_links"
MAX_LINKS = 12
DEFAULTS = [
    {"id": 1, "name": "Project AIDA dashboard", "url": "http://localhost:8501", "folder": "C:\\Users\\Guito\\project-aida"},
    {"id": 2, "name": "Project AIDA API", "url": "http://localhost:8006", "folder": ""},
    {"id": 3, "name": "Eivanta Analytics app", "url": "http://localhost:3000", "folder": "C:\\Users\\Guito\\nexusflow-portal"},
    {"id": 4, "name": "Eivanta Analytics API", "url": "http://localhost:8000", "folder": ""},
    {"id": 5, "name": "Eivanta Grid (VibeGrid)", "url": "http://localhost:3010", "folder": "C:\\Users\\Guito\\Eivanta Grid"},
    {"id": 6, "name": "Eivanta Grid API", "url": "http://localhost:8005", "folder": ""},
    {"id": 7, "name": "DataFabric", "url": "http://localhost:5173", "folder": "C:\\Users\\Guito\\datafabric-agent-mesh-live"},
    {"id": 8, "name": "DataFabric API", "url": "http://localhost:8004", "folder": ""},
]
NOTE = "Starting links, read from the project-aida and nexusflow-portal folders on Oct 14 (AIDA: dashboard 8501, API 8006; Eivanta: app 3000, API 8000; Eivanta Grid 3010/8005; DataFabric 5173/8004). Change them if you move things."


class LinkError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _clean_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    p = urlparse(u)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise LinkError("Addresses must start with http:// or https://")
    return u[:200]


def _clean_folder(f: str) -> str:
    f = (f or "").strip()
    if re.search(r"[\x00-\x1f]", f):
        raise LinkError("That folder path has characters that aren't allowed.")
    return f[:260]


def listing() -> dict:
    raw = state.kv_get(KEY)
    rows = json.loads(raw) if raw else DEFAULTS
    return {"links": rows, "saved": raw is not None, "note": NOTE}


def save(rows: list) -> dict:
    if not isinstance(rows, list) or len(rows) > MAX_LINKS:
        raise LinkError(f"Send a list of up to {MAX_LINKS} links.")
    out = []
    for i, r in enumerate(rows, 1):
        name = str((r or {}).get("name") or "").strip()[:60]
        if not name:
            raise LinkError("Every link needs a name.")
        url, folder = _clean_url(str(r.get("url") or "")), _clean_folder(str(r.get("folder") or ""))
        if not url and not folder:
            raise LinkError(f"'{name}' needs an address or a folder.")
        out.append({"id": i, "name": name, "url": url, "folder": folder})
    state.kv_set(KEY, json.dumps(out))
    state.audit("project_links", f"{len(out)} links")
    return listing()


def _is_local(host: str | None) -> bool:
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def status() -> dict:
    res = []
    for r in listing()["links"]:
        host = urlparse(r["url"]).hostname if r["url"] else None
        if not r["url"]:
            res.append({"id": r["id"], "state": "none"})
        elif not _is_local(host):
            res.append({"id": r["id"], "state": "not-checked"})        # only this computer is ever contacted
        else:
            try:
                with urllib.request.urlopen(urllib.request.Request(r["url"], method="GET"), timeout=1.0):
                    res.append({"id": r["id"], "state": "up"})
            except urllib.error.HTTPError:
                res.append({"id": r["id"], "state": "up"})             # it answered, even if with an error page
            except Exception:  # noqa: BLE001 - refused, timed out, bad host: all mean "not running"
                res.append({"id": r["id"], "state": "down"})
    return {"status": res}
