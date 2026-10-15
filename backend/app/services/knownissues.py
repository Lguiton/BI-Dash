"""Known issues and support dates from two free public sources, with no key and nothing about your clients sent out.

* CISA Known Exploited Vulnerabilities (KEV): the list is downloaded whole (about once a day) and searched here, so what you type never leaves this computer.
* endoflife.date: only the product name (like "windows") is sent, to ask when each version stops getting updates.

Both are passive reads of public data. A match is a prompt to check the vendor's own advisory, not proof that a client's machine is affected, and no match is not proof
it is safe. If a site cannot be reached, the last saved copy is shown with its date."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import date, datetime, timezone

from app.services import state

UA = "BI-Dashboard-known-issues"
KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
EOL_V1 = "https://endoflife.date/api/v1/products/{p}/"
EOL_OLD = "https://endoflife.date/api/{p}.json"
KEEP_SECS = 24 * 3600
# Product names the site uses (the box also accepts any other name you type).
PRODUCTS = ["windows", "windows-server", "macos", "ios", "android", "ubuntu", "debian", "office", "python", "nodejs", "php", "mysql", "postgresql", "wordpress", "firefox"]
_SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,59}$")


class IssueError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _get(url: str, timeout: float = 15.0) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:     # noqa: S310  fixed https hosts only
            return r.status, r.read(6_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, OSError, TimeoutError):
        return 0, ""


def _now() -> float:
    return datetime.now(timezone.utc).timestamp()


def _cached(key: str):
    raw = state.kv_get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def _save(key: str, data) -> dict:
    box = {"at": _now(), "data": data}
    state.kv_set(key, json.dumps(box))
    return box


def _age_note(box: dict) -> str:
    return datetime.fromtimestamp(box["at"], timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------- CISA KEV

def _kev_rows(text: str) -> tuple[list[dict], str]:
    j = json.loads(text)
    rows = []
    for v in j.get("vulnerabilities", []):
        rows.append({"cve": v.get("cveID", ""), "vendor": v.get("vendorProject", ""), "product": v.get("product", ""), "name": v.get("vulnerabilityName", ""),
                     "added": v.get("dateAdded", ""), "what": v.get("shortDescription", ""), "action": v.get("requiredAction", ""), "due": v.get("dueDate", ""),
                     "ransomware": v.get("knownRansomwareCampaignUse", "") == "Known"})
    return rows, str(j.get("catalogVersion", ""))


def _kev(fetch=None) -> tuple[dict, str]:
    fetch = fetch or _get
    box = _cached("known_issues:kev")
    if box and _now() - box["at"] < KEEP_SECS:
        return box, ""
    status, text = fetch(KEV_URL)
    if status == 200 and text:
        try:
            rows, ver = _kev_rows(text)
            if rows:
                return _save("known_issues:kev", {"rows": rows, "version": ver}), ""
        except ValueError:
            pass
    if box:
        return box, f"CISA could not be reached, so this is the copy saved on {_age_note(box)}."
    raise IssueError("Could not reach CISA and there is no saved copy yet. Check your internet connection and try again.", 502)


def kev_search(q: str = "", limit: int = 25, fetch=None) -> dict:
    box, warn = _kev(fetch)
    rows = box["data"]["rows"]
    words = [w for w in re.split(r"\s+", (q or "").strip().lower()) if w][:6]
    if words:
        hits = [r for r in rows if all(w in (r["cve"] + " " + r["vendor"] + " " + r["product"] + " " + r["name"]).lower() for w in words)]
    else:
        hits = sorted(rows, key=lambda r: r["added"], reverse=True)
    hits.sort(key=lambda r: r["added"], reverse=True)
    limit = max(1, min(int(limit or 25), 100))
    return {"query": q.strip(), "total": len(hits), "shown": min(limit, len(hits)), "catalog_total": len(rows), "results": hits[:limit], "saved_on": _age_note(box), "warning": warn,
            "note": "These are flaws attackers are known to be using. A match means check the vendor's fix for that product and version; no match does not prove a machine is safe. Your search words stayed on this computer."}


# ---------------------------------------------------------------- endoflife.date

def _norm_release(r: dict) -> dict:
    """Both the current and the older response shapes."""
    cycle = str(r.get("name", r.get("cycle", "")))
    eol = r.get("eolFrom", r.get("eol"))
    eol = eol if isinstance(eol, str) and re.match(r"^\d{4}-\d{2}-\d{2}", eol) else ("" if eol in (None, False, "") else ("ended" if eol is True else ""))
    latest = r.get("latest")
    latest = latest.get("name", "") if isinstance(latest, dict) else (str(latest) if latest else "")
    return {"cycle": cycle, "label": str(r.get("label") or cycle), "released": str(r.get("releaseDate") or ""), "eol": eol[:10] if eol != "ended" else "ended", "latest": latest,
            "lts": bool(r.get("isLts", r.get("lts")) not in (None, False, ""))}


def _status(eol: str, today: date) -> tuple[str, str]:
    if not eol:
        return "supported", "Supported (no end date announced)"
    if eol == "ended":
        return "ended", "Support has ended"
    try:
        d = date.fromisoformat(eol)
    except ValueError:
        return "supported", "Supported (no end date announced)"
    if d <= today:
        return "ended", f"Support ended {eol}"
    left = (d - today).days
    return ("soon" if left <= 180 else "supported"), f"Supported until {eol} ({left} days)"


def eol_lookup(product: str, cycle: str = "", fetch=None, today: date | None = None) -> dict:
    fetch = fetch or _get
    p = (product or "").strip().lower().replace(" ", "-")
    if not _SLUG.match(p):
        raise IssueError("Type a product name like windows, ubuntu or macos.")
    key = f"known_issues:eol:{p}"
    box = _cached(key)
    warn = ""
    if not box or _now() - box["at"] >= KEEP_SECS:
        rels, notfound = None, False
        for url in (EOL_V1.format(p=p), EOL_OLD.format(p=p)):
            status, text = fetch(url)
            if status == 404:
                notfound = True
                continue
            if status == 200 and text:
                try:
                    j = json.loads(text)
                    raw = j["result"]["releases"] if isinstance(j, dict) and "result" in j else j
                    if isinstance(raw, list) and raw:
                        rels = [_norm_release(x) for x in raw if isinstance(x, dict)]
                        break
                except (ValueError, KeyError, TypeError):
                    continue
        if rels:
            box = _save(key, rels)
        elif box:
            warn = f"endoflife.date could not be reached, so this is the copy saved on {_age_note(box)}."
        elif notfound:
            raise IssueError(f"endoflife.date has no product called '{p}'. Try a name from the list, or check the exact name on endoflife.date.", 404)
        else:
            raise IssueError("Could not reach endoflife.date and there is no saved copy yet. Check your internet connection and try again.", 502)
    t = today or date.today()
    out = []
    for r in box["data"]:
        s, say = _status(r["eol"], t)
        out.append({**r, "status": s, "says": say})
    c = (cycle or "").strip().lower()
    if c:
        out = [r for r in out if r["cycle"].lower() == c or r["cycle"].lower().startswith(c + ".") or c in r["label"].lower()]
    return {"product": p, "cycle": cycle.strip(), "releases": out[:40], "saved_on": _age_note(box), "warning": warn,
            "note": "Dates come from endoflife.date, which collects them from each vendor. Check the vendor's page before telling a client, since dates can change. Only the product name was sent."}
