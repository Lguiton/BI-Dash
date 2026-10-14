"""Breach exposure checks that protect what you check.

Passwords use the Pwned Passwords range service with k-anonymity: only the first 5 characters of the password's SHA-1 hash leave this computer, never the password
and never the full hash. Email checks need the person's own Have I Been Pwned API key (a paid key); it is used for that one request and is never stored. Both are
deliberate, one-at-a-time actions that contact haveibeenpwned.com. A password not found is not proof it is safe; it only means it is not in that collection."""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request

UA = "BI-Dashboard-security-check"


class BreachError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _get(url: str, headers: dict, timeout: float = 8.0) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:     # noqa: S310  fixed https hosts only
            return r.status, r.read(3_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise BreachError(f"Couldn't reach the breach service: {getattr(e, 'reason', e)}. Check your internet connection.", 502) from None


def password_exposure(pw: str, fetch=_get) -> dict:
    if not pw:
        raise BreachError("Type a password to check.")
    if len(pw) > 200:
        raise BreachError("That password is too long to check.")
    h = hashlib.sha1(pw.encode("utf-8")).hexdigest().upper()      # noqa: S324  required by the service's range protocol
    prefix, suffix = h[:5], h[5:]
    status, text = fetch(f"https://api.pwnedpasswords.com/range/{prefix}", {"User-Agent": UA, "Add-Padding": "true"})
    if status != 200:
        raise BreachError(f"The breach service answered with status {status}. Try again later.", 502)
    count = 0
    for line in text.splitlines():
        s, _, n = line.partition(":")
        if s.strip().upper() == suffix:
            count = int(n.strip() or 0)
            break
    return {"found": count > 0, "times_seen": count, "sent": f"Only the first 5 characters of the hash ({prefix}) were sent.",
            "says": f"This password appears {count:,} times in known breaches. Do not use it anywhere." if count else "Not found in the known-breach collection. That does not prove it is strong; check its strength too.",
            "fix_id": "pwned-password" if count else None}


def email_exposure(email: str, api_key: str, fetch=_get) -> dict:
    email = (email or "").strip()
    if not email or "@" not in email or len(email) > 200:
        raise BreachError("Enter a valid email address.")
    if not (api_key or "").strip():
        raise BreachError("Email checks need your own Have I Been Pwned API key (it is a paid key). The password check needs no key.")
    status, text = fetch(f"https://haveibeenpwned.com/api/v3/breachedaccount/{urllib.parse.quote(email)}?truncateResponse=false", {"User-Agent": UA, "hibp-api-key": api_key.strip()})
    if status == 404:
        return {"found": False, "breaches": [], "says": "No breaches found for that address in the service's records. Not proof of safety.", "fix_id": None}
    if status in (401, 403):
        raise BreachError("The service rejected the API key.", 401)
    if status == 429:
        raise BreachError("The service says to slow down. Wait a moment and try again.", 429)
    if status != 200:
        raise BreachError(f"The breach service answered with status {status}.", 502)
    try:
        data = json.loads(text)
    except ValueError:
        raise BreachError("The breach service sent something unreadable.", 502) from None
    br = [{"name": b.get("Name", "?"), "date": b.get("BreachDate"), "exposed": b.get("DataClasses", [])[:8]} for b in data][:60]
    return {"found": True, "breaches": br, "says": f"{len(br)} breach(es) include this address. Change the passwords for those services, turn on 2FA, and use unique passwords.", "fix_id": "pwned-password"}
