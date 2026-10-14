"""Web table scraper: read an HTML <table> from a public https page into rows, like a very small Power Query "From Web".

Safety: https only, the host must resolve to public addresses only (so it can't be aimed at your own network or cloud metadata),
the connection goes to the address that was checked, redirects are not followed, the page is capped at 2 MB, and the page is
parsed as data only (no scripts run). Please respect a site's terms of use; this reads one page per call.
"""
from __future__ import annotations

import re
import socket
import ssl
from html.parser import HTMLParser
from urllib.parse import urlparse

from app.services import security

MAX_BYTES = 2 * 1024 * 1024
MAX_TABLES = 40
MAX_CELL = 500


class WebTableError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _target(url: str) -> tuple[str, str]:
    u = urlparse((url or "").strip())
    if u.scheme != "https":
        raise WebTableError("Use an https:// link. Plain http pages are not fetched.")
    if u.port not in (None, 443) or u.username or u.password:
        raise WebTableError("Links with a custom port or a login in them are not allowed.")
    host = (u.hostname or "").lower()
    try:
        security.resolve_public(host)
    except security.SecError as e:
        raise WebTableError(e.args[0], e.status) from e
    path = (u.path or "/") + (f"?{u.query}" if u.query else "")
    if re.search(r"[\s\r\n]", path):
        raise WebTableError("That link has characters that aren't allowed.")
    return host, path


def _dechunk(body: bytes) -> bytes:
    out, i = b"", 0
    while True:
        j = body.find(b"\r\n", i)
        if j < 0:
            break
        try:
            n = int(body[i:j].split(b";")[0], 16)
        except ValueError:
            break
        if n == 0:
            break
        out += body[j + 2:j + 2 + n]
        i = j + 2 + n + 2
        if len(out) > MAX_BYTES:
            break
    return out


def get(url: str, timeout: float = 10.0) -> tuple[int, str, str]:
    """One guarded GET. Returns (status, location_header, body_text). Redirects are NOT followed here."""
    host, path = _target(url)
    ip = security.resolve_public(host)
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((ip, 443), timeout=timeout) as raw, ctx.wrap_socket(raw, server_hostname=host) as tls:
            tls.settimeout(timeout)
            tls.sendall(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: bi-dashboard-webtable/1\r\nAccept: text/html\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n".encode())
            buf = b""
            while len(buf) <= MAX_BYTES + 65536:
                chunk = tls.recv(65536)
                if not chunk:
                    break
                buf += chunk
    except (OSError, ssl.SSLError) as e:
        raise WebTableError(f"Couldn't fetch the page securely: {e}", 502) from e
    head, _, body = buf.partition(b"\r\n\r\n")
    lines = head.decode("latin-1", "replace").split("\r\n")
    m = re.match(r"HTTP/\d\.?\d? (\d{3})", lines[0])
    if not m:
        raise WebTableError("The server didn't answer like a web server.", 502)
    status = int(m.group(1))
    loc = next((l.split(":", 1)[1].strip() for l in lines[1:] if l.lower().startswith("location:")), "")
    if any(l.lower().startswith("transfer-encoding:") and "chunked" in l.lower() for l in lines[1:]):
        body = _dechunk(body)
    if len(body) > MAX_BYTES:
        raise WebTableError("That page is over 2 MB.")
    return status, loc, body.decode("utf-8", "replace")


def fetch_page(url: str, timeout: float = 10.0) -> str:
    status, _loc, body = get(url, timeout)
    if 300 <= status < 400:
        raise WebTableError("The page redirects somewhere else. Redirects are not followed; use the final link.")
    if status >= 400:
        raise WebTableError(f"The server answered {status}.", 502)
    return body


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[dict] = []
        self._stack: list[dict] = []
        self._cell: list[str] | None = None
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "table":
            if len(self.tables) + len(self._stack) < MAX_TABLES:
                self._stack.append({"rows": [], "caption": "", "row": None, "cap": False})
            else:
                self._stack.append({"rows": [], "caption": "", "row": None, "cap": False, "drop": True})
        elif not self._stack:
            return
        elif tag == "tr":
            self._stack[-1]["row"] = []
        elif tag in ("td", "th"):
            self._cell = []
        elif tag == "caption":
            self._stack[-1]["cap"] = True
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif not self._stack:
            return
        elif tag in ("td", "th") and self._cell is not None:
            t = self._stack[-1]
            if t["row"] is not None:
                t["row"].append(re.sub(r"\s+", " ", "".join(self._cell)).strip()[:MAX_CELL])
            self._cell = None
        elif tag == "tr":
            t = self._stack[-1]
            if t["row"]:
                t["rows"].append(t["row"])
            t["row"] = None
        elif tag == "caption":
            self._stack[-1]["cap"] = False
        elif tag == "table":
            t = self._stack.pop()
            if not t.get("drop") and t["rows"]:
                self.tables.append(t)

    def handle_data(self, data):
        if self._skip or not self._stack:
            return
        if self._cell is not None:
            self._cell.append(data)
        elif self._stack[-1]["cap"]:
            self._stack[-1]["caption"] += data


def _unique(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for i, n in enumerate(names):
        n = (n or "").strip() or f"column_{i + 1}"
        k = n.lower()
        seen[k] = seen.get(k, 0) + 1
        out.append(n if seen[k] == 1 else f"{n}_{seen[k]}")
    return out


def parse_tables(html: str) -> list[dict]:
    p = _Tables()
    p.feed(html)
    p.close()
    out = []
    for i, t in enumerate(p.tables):
        width = max(len(r) for r in t["rows"])
        rows = [r + [None] * (width - len(r)) for r in t["rows"]]
        if len(rows) < 2 or width < 2:
            continue
        out.append({"index": i, "caption": re.sub(r"\s+", " ", t["caption"]).strip()[:120], "header": _unique(rows[0]), "rows": rows[1:], "columns": width})
    return out


def table(url: str, index: int = 0, fetcher=None) -> tuple[list[str], list[list], str]:
    tables = parse_tables((fetcher or fetch_page)(url))
    if not tables:
        raise WebTableError("No usable tables on that page (a table needs a header row, at least one data row and two columns). Pages that build tables with JavaScript can't be read this way.")
    pick = [t for t in tables if t["index"] == index]
    if not pick:
        raise WebTableError(f"There's no table number {index}. Tables found: {', '.join(str(t['index']) for t in tables)}.")
    t = pick[0]
    return t["header"], t["rows"], urlparse(url).netloc


def preview(url: str, fetcher=None) -> dict:
    tables = parse_tables((fetcher or fetch_page)(url))
    return {"url": url, "tables": [{"index": t["index"], "caption": t["caption"], "columns": t["header"], "rows": len(t["rows"]), "sample": t["rows"][:3]} for t in tables[:MAX_TABLES]],
            "note": "Numbers on web pages often contain commas, currency signs or footnote marks. Clean them in a workflow after loading."}
