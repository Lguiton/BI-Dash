"""Web panel helpers: a text "reader view" of a public page, and saved bookmarks.

The live web panel in the browser is an <iframe> that uses YOUR browser's internet, not this server's. Many sites forbid being embedded
(X-Frame-Options / CSP frame-ancestors) and show a blank frame; the reader view is the fallback. The reader fetches through this
backend with the same guard as the web-table source: https only, public addresses only, at most 3 redirects (each re-checked), 2 MB, no
cookies and no logins, scripts never run. It shows text and links, not the real page.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from app.services import state, webtable

MAX_TEXT = 60_000
MAX_LINKS = 60
MAX_BOOKMARKS = 40
SKIP = {"script", "style", "noscript", "svg", "head", "nav", "footer", "form", "template"}
BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "pre", "table", "ul", "ol", "blockquote"}

DEFAULTS = [
    {"title": "DuckDB docs", "url": "https://duckdb.org/docs/"}, {"title": "pandas docs", "url": "https://pandas.pydata.org/docs/"},
    {"title": "scikit-learn guide", "url": "https://scikit-learn.org/stable/user_guide.html"}, {"title": "MDN Web Docs", "url": "https://developer.mozilla.org/"},
    {"title": "OWASP Top 10", "url": "https://owasp.org/www-project-top-ten/"}, {"title": "FastAPI docs", "url": "https://fastapi.tiangolo.com/"},
    {"title": "Wikipedia", "url": "https://en.wikipedia.org/"},
]


class _Text(HTMLParser):
    def __init__(self, base: str):
        super().__init__(convert_charrefs=True)
        self.base, self.title, self.parts, self.links, self._skip, self._in_title, self._href = base, "", [], [], 0, False, None

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        if tag in SKIP:
            self._skip += 1
        if tag in BLOCK:
            self.parts.append("\n")
        if tag == "a" and not self._skip:
            self._href = dict(attrs).get("href")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in SKIP:
            self._skip = max(0, self._skip - 1)
        if tag in BLOCK:
            self.parts.append("\n")
        if tag == "a":
            self._href = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._skip:
            return
        self.parts.append(data)
        if self._href and data.strip() and len(self.links) < MAX_LINKS:
            u = urljoin(self.base, self._href)
            if u.startswith("https://"):
                self.links.append({"text": re.sub(r"\s+", " ", data).strip()[:80], "url": u[:500]})


def read(url: str, fetcher=webtable.get) -> dict:
    cur, hops = url.strip(), 0
    while True:
        status, loc, body = fetcher(cur)
        if 300 <= status < 400 and loc:
            hops += 1
            if hops > 3:
                raise webtable.WebTableError("Too many redirects.")
            cur = urljoin(cur, loc)
            webtable._target(cur)                      # re-check every hop: a redirect must not lead to a private address
            continue
        break
    if status >= 400:
        raise webtable.WebTableError(f"The server answered {status}.", 502)
    p = _Text(cur)
    p.feed(body)
    p.close()
    text = re.sub(r"[ \t\r\f\v]+", " ", "".join(p.parts))
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", re.sub(r" *\n *", "\n", text)).strip()
    seen, links = set(), []
    for l in p.links:
        if l["url"] not in seen:
            seen.add(l["url"]); links.append(l)
    return {"url": cur, "host": urlparse(cur).netloc, "title": re.sub(r"\s+", " ", p.title).strip()[:160], "text": text[:MAX_TEXT], "truncated": len(text) > MAX_TEXT, "links": links,
            "note": "Text only, fetched by this app's backend. No scripts, images, logins or cookies. Open the live page in a new tab for the real thing."}


def _key() -> str:
    from app.services import workspaces
    return f"web_bookmarks:{workspaces.active()}"


def bookmarks() -> list[dict]:
    raw = state.kv_get(_key())
    return json.loads(raw) if raw else list(DEFAULTS)


def save_bookmarks(items: list[dict]) -> list[dict]:
    out = []
    for it in items[:MAX_BOOKMARKS]:
        u = str(it.get("url", "")).strip()
        if urlparse(u).scheme != "https" or not urlparse(u).netloc:
            raise webtable.WebTableError(f"'{u[:60]}' isn't an https link.")
        out.append({"title": (str(it.get("title") or urlparse(u).netloc).strip())[:60], "url": u[:500]})
    state.kv_set(_key(), json.dumps(out))
    return out
