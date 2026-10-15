"""How-to videos: a small library of lessons you watch inside the dashboard.

A lesson is a title, a field, and a link you paste (YouTube, Vimeo or any web page). The link opens in a new tab; the video is never downloaded or stored here,
so a lesson takes a few KB. Each lesson can have chapters (a time and a label; on YouTube and Vimeo they open the video at that time), your own notes, and
watched / watch-again flags. Notes are cleaned of passwords and keys before they are stored."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from app.services import clients, state, workspaces
from app.services.fixlog import hide_secrets
from app.services.service_catalog import GROUPS

KEY = "howto_videos"
MAX_VIDEOS = 300
MAX_CHAPTERS = 40
OTHER = "Other"


class HowtoError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def fields() -> list[str]:
    return [*GROUPS.values(), OTHER]


def _load() -> list[dict]:
    raw = state.kv_get(KEY)
    try:
        v = json.loads(raw) if raw else []
    except ValueError:
        v = []
    return v if isinstance(v, list) else []


def _save(rows: list[dict]) -> None:
    state.kv_set(KEY, json.dumps(rows))


def _txt(v, limit: int) -> str:
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(v or "")).strip()[:limit]
    return hide_secrets(s)[0]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def parse_time(v) -> int:
    """'1:05', '01:02:03' or a number of seconds -> seconds."""
    s = str(v if v is not None else "").strip()
    if re.fullmatch(r"\d{1,6}", s):
        return int(s)
    m = re.fullmatch(r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})", s)
    if not m:
        raise HowtoError("A chapter time looks like 1:05 or 0:01:05.")
    h, mi, se = int(m.group(1) or 0), int(m.group(2)), int(m.group(3))
    if se > 59 or (m.group(1) and mi > 59):
        raise HowtoError("A chapter time looks like 1:05 or 0:01:05.")
    return h * 3600 + mi * 60 + se


def classify(url: str) -> dict:
    """What a pasted link is: {"kind": youtube|vimeo|page, "embed": ..., "url": cleaned}. Only http and https links are accepted."""
    u = (url or "").strip()
    p = urlparse(u)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise HowtoError("A video link must start with http:// or https://")
    u = u[:500]
    host = p.netloc.lower().removeprefix("www.").removeprefix("m.")
    vid = ""
    if host == "youtu.be":
        vid = p.path.strip("/").split("/")[0]
    elif host in ("youtube.com", "youtube-nocookie.com"):
        if p.path == "/watch":
            vid = (parse_qs(p.query).get("v") or [""])[0]
        else:
            m = re.match(r"/(?:embed|shorts|live|v)/([\w-]+)", p.path)
            vid = m.group(1) if m else ""
    if vid:
        if not re.fullmatch(r"[\w-]{6,20}", vid):
            raise HowtoError("That doesn't look like a YouTube video link.")
        return {"kind": "youtube", "embed": f"https://www.youtube-nocookie.com/embed/{vid}", "url": u}
    if host in ("vimeo.com", "player.vimeo.com"):
        m = re.search(r"/(\d{5,12})(?:$|[/?])", p.path + "/")
        if m:
            return {"kind": "vimeo", "embed": f"https://player.vimeo.com/video/{m.group(1)}", "url": u}
    return {"kind": "page", "embed": "", "url": u}


def _chapters(v) -> list[dict]:
    if not v:
        return []
    if not isinstance(v, list) or len(v) > MAX_CHAPTERS:
        raise HowtoError(f"Add up to {MAX_CHAPTERS} chapters.")
    out = []
    for c in v:
        if not isinstance(c, dict):
            raise HowtoError("Each chapter needs a time and a label.")
        label = _txt(c.get("label"), 80)
        if not label:
            raise HowtoError("Each chapter needs a label.")
        out.append({"t": parse_time(c.get("t")), "label": label})
    return sorted(out, key=lambda c: c["t"])


def _field(v) -> str:
    f = _txt(v, 60) or OTHER
    return f


def _view(r: dict) -> dict:
    out = {k: r.get(k) for k in ("id", "title", "field", "job_type", "kind", "url", "embed", "chapters", "notes", "watched", "rewatch", "added", "updated")}
    out["chapters"] = r.get("chapters") or []
    return out


def listing() -> dict:
    rows = _load()
    watched = sum(1 for r in rows if r.get("watched"))
    return {"videos": [_view(r) for r in rows], "fields": fields(), "watched": watched, "total": len(rows),
            "note": "Paste a YouTube or Vimeo link. The link opens in a new tab; no video is downloaded or stored here."}


def _get(vid: int) -> dict:
    for r in _load():
        if r["id"] == vid:
            return r
    raise HowtoError("That video is no longer in the library.", 404)


def _next_id(rows: list[dict]) -> int:
    return max((r["id"] for r in rows), default=0) + 1


def add_link(body: dict) -> dict:
    rows = _load()
    if len(rows) >= MAX_VIDEOS:
        raise HowtoError(f"The library holds {MAX_VIDEOS} videos. Remove one first.")
    info = classify(body.get("url"))
    title = _txt(body.get("title"), 120)
    if not title:
        raise HowtoError("Add a title.")
    r = {"id": _next_id(rows), "title": title, "field": _field(body.get("field")), "job_type": _txt(body.get("job_type"), 80),
         "kind": info["kind"], "url": info["url"], "embed": info["embed"], "chapters": _chapters(body.get("chapters")),
         "notes": _txt(body.get("notes"), 4000), "watched": False, "rewatch": False, "added": _now(), "updated": _now()}
    rows.append(r)
    _save(rows)
    state.audit("howto_add", title)
    return _view(r)


def update(vid: int, body: dict) -> dict:
    rows = _load()
    for r in rows:
        if r["id"] != vid:
            continue
        if "title" in body:
            t = _txt(body["title"], 120)
            if not t:
                raise HowtoError("Add a title.")
            r["title"] = t
        if "field" in body:
            r["field"] = _field(body["field"])
        if "job_type" in body:
            r["job_type"] = _txt(body["job_type"], 80)
        if "notes" in body:
            r["notes"] = _txt(body["notes"], 4000)
        if "chapters" in body:
            r["chapters"] = _chapters(body["chapters"])
        for k in ("watched", "rewatch"):
            if k in body:
                r[k] = bool(body[k])
        if "url" in body:
            info = classify(body["url"])
            r["url"], r["kind"], r["embed"] = info["url"], info["kind"], info["embed"]
        r["updated"] = _now()
        _save(rows)
        return _view(r)
    raise HowtoError("That video is no longer in the library.", 404)


def delete(vid: int) -> dict:
    rows = _load()
    keep = [r for r in rows if r["id"] != vid]
    if len(keep) == len(rows):
        raise HowtoError("That video is no longer in the library.", 404)
    gone = next(r for r in rows if r["id"] == vid)
    _save(keep)
    state.audit("howto_delete", gone["title"])
    return {"deleted": vid}


def for_job(job_id: int, limit: int = 5) -> dict:
    """Lessons that look related to a job: words from the job title (and the job type) matched against lesson titles, fields and job types."""
    found = next((j for j in clients._load()["jobs"] if j.get("id") == job_id), None)
    if found is None:
        raise HowtoError("No such job.", 404)
    words = {w for w in re.findall(r"[a-z0-9]{4,}", str(found.get("title", "")).lower())} - {"with", "from", "that", "this", "your", "setup", "fix"}
    scored = []
    for r in _load():
        hay = set(re.findall(r"[a-z0-9]{4,}", f"{r.get('title','')} {r.get('job_type','')} {r.get('field','')}".lower()))
        s = len(words & hay)
        if s:
            scored.append((s, not r.get("watched"), r["id"], r))
    scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
    return {"videos": [_view(x[3]) for x in scored[:limit]]}
