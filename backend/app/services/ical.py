"""Read-only calendar import from an iCal feed (Google Calendar's "Secret address in iCal format", Outlook, Apple).

No sign-in or developer account: the private link itself is the key, so it is kept in an environment variable
(url_env) and never stored. Repeating events are expanded inside a window around today.
"""
import os
import re
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from dateutil.rrule import rrulestr

MAX_BYTES = 8_000_000
MAX_EVENTS = 20_000
MAX_PER_SERIES = 2_000
HEADER = ["title", "start", "end", "all_day", "hours", "location", "status", "repeats"]


class IcalError(Exception):
    pass


def _unfold(text: str) -> list[str]:
    out: list[str] = []
    for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if ln[:1] in (" ", "\t") and out:
            out[-1] += ln[1:]
        else:
            out.append(ln)
    return out


def _unescape(v: str) -> str:
    return re.sub(r"\\([nN,;\\])", lambda m: "\n" if m.group(1) in "nN" else m.group(1), v)


def _parse_props(lines: list[str]) -> list[dict]:
    events, cur = [], None
    for ln in lines:
        if ln == "BEGIN:VEVENT":
            cur = {}
        elif ln == "END:VEVENT":
            if cur is not None:
                events.append(cur)
            cur = None
        elif cur is not None and ":" in ln:
            head, _, val = ln.partition(":")
            name, *params = head.split(";")
            pd = dict(p.split("=", 1) for p in params if "=" in p)
            cur.setdefault(name.upper(), []).append((pd, val))
    return events


def _tz(name: str | None, default: ZoneInfo) -> ZoneInfo:
    if name:
        try:
            return ZoneInfo(name.strip('"'))
        except Exception:  # noqa: BLE001 - unknown tz names fall back
            return default
    return default


def _when(entry, default: ZoneInfo) -> tuple[datetime, bool]:
    pd, val = entry
    val = val.strip()
    if pd.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", val):
        d = datetime.strptime(val[:8], "%Y%m%d")
        return d.replace(tzinfo=default), True
    if val.endswith("Z"):
        return datetime.strptime(val, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(default), False
    return datetime.strptime(val[:15], "%Y%m%dT%H%M%S").replace(tzinfo=_tz(pd.get("TZID"), default)).astimezone(default) if pd.get("TZID") else \
        datetime.strptime(val[:15], "%Y%m%dT%H%M%S").replace(tzinfo=default), False


def parse(text: str, now: datetime | None = None, past_days: int = 30, future_days: int = 180, tz_name: str | None = None) -> list[list]:
    if "BEGIN:VCALENDAR" not in text:
        raise IcalError("That doesn't look like a calendar feed. Use the 'Secret address in iCal format' link (it ends in .ics).")
    m = re.search(r"^X-WR-TIMEZONE:(.+)$", text, re.M)
    default = _tz(tz_name or (m.group(1).strip() if m else None) or "UTC", ZoneInfo("UTC"))
    now = (now or datetime.now(timezone.utc)).astimezone(default)
    lo, hi = now - timedelta(days=past_days), now + timedelta(days=future_days)
    props = _parse_props(_unfold(text))
    overrides = {(p["UID"][0][1], _when(p["RECURRENCE-ID"][0], default)[0]) for p in props if "RECURRENCE-ID" in p and "UID" in p}
    rows: list[tuple[datetime, list]] = []

    def add(p, s, e, all_day, repeats):
        status = (p.get("STATUS", [({}, "CONFIRMED")])[0][1]).title()
        if status == "Cancelled" or not (lo <= s <= hi or lo <= e <= hi or s <= lo <= hi <= e):
            return
        title = _unescape(p.get("SUMMARY", [({}, "(no title)")])[0][1]) or "(no title)"
        loc = _unescape(p.get("LOCATION", [({}, "")])[0][1])
        fmt = "%Y-%m-%d" if all_day else "%Y-%m-%d %H:%M"
        rows.append((s, [title, s.strftime(fmt), e.strftime(fmt), "yes" if all_day else "no",
                         "" if all_day else str(round((e - s).total_seconds() / 3600, 2)), loc, status, "yes" if repeats else "no"]))

    for p in props:
        if "DTSTART" not in p:
            continue
        try:
            s, all_day = _when(p["DTSTART"][0], default)
            e = _when(p["DTEND"][0], default)[0] if "DTEND" in p else (s + (timedelta(days=1) if all_day else timedelta(0)))
        except ValueError:
            continue
        if all_day and e <= s:
            e = s + timedelta(days=1)
        if "RRULE" in p and "RECURRENCE-ID" not in p:
            rule = p["RRULE"][0][1]
            if all_day:
                rule = re.sub(r"UNTIL=(\d{8})(T\d{6}Z?)?", r"UNTIL=\1", rule)
            elif re.search(r"UNTIL=\d{8}T\d{6}(?!Z)", rule):
                rule = re.sub(r"(UNTIL=\d{8}T\d{6})(?!Z)", r"\1Z", rule)
            elif re.search(r"UNTIL=\d{8}(?!T)", rule):
                rule = re.sub(r"(UNTIL=\d{8})(?!T)", r"\1T235959Z", rule)
            try:
                rr = rrulestr(rule, dtstart=s.replace(tzinfo=None) if all_day else s)
            except (ValueError, TypeError):
                add(p, s, e, all_day, False)
                continue
            skip = set()
            for _pd, v in p.get("EXDATE", []):
                for one in v.split(","):
                    try:
                        skip.add(_when((_pd, one), default)[0])
                    except ValueError:
                        pass
            dur = e - s
            uid = p.get("UID", [({}, "")])[0][1]
            n = 0
            for occ in rr.between(lo.replace(tzinfo=None) if all_day else lo - dur, hi.replace(tzinfo=None) if all_day else hi, inc=True):
                occ = occ.replace(tzinfo=default) if all_day else occ
                if occ in skip or (uid, occ) in overrides:
                    continue
                add(p, occ, occ + dur, all_day, True)
                n += 1
                if n >= MAX_PER_SERIES:
                    break
        else:
            add(p, s, e, all_day, "RECURRENCE-ID" in p)
        if len(rows) > MAX_EVENTS:
            raise IcalError("This calendar has too many events in the window. Shorten past_days/future_days.")
    rows.sort(key=lambda t: t[0])
    return [r for _, r in rows]


def _resolve_url(cfg: dict) -> str:
    env = str(cfg.get("url_env", ""))
    if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", env):
        raise IcalError("url_env must be the name of an environment variable, like GOOGLE_CAL_ICAL_URL. The private link itself is never typed or stored here.")
    url = os.environ.get(env, "").strip()
    if not url:
        raise IcalError(f"The environment variable {env} is not set. Put your calendar's iCal link in backend/.env as {env}=https://…")
    return url


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # a redirect could point at a private address, so refuse
        return None


def fetch(cfg: dict) -> tuple[list[str], list[list], str]:
    from app.services import webtable
    url = _resolve_url(cfg)
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    try:
        host, _ = webtable._target(url)
    except webtable.WebTableError as e:
        raise IcalError(e.message) from e
    req = urllib.request.Request(url, headers={"User-Agent": "bi-dashboard/2", "Accept": "text/calendar, */*"})
    try:
        with urllib.request.build_opener(_NoRedirect).open(req, timeout=30) as resp:
            raw = resp.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        raise IcalError(f"The calendar server answered {e.code}. Check that the link is the private iCal address and hasn't been reset.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise IcalError(f"Could not reach the calendar: {getattr(e, 'reason', e)}") from e
    if len(raw) > MAX_BYTES:
        raise IcalError("The calendar download is over the size limit.")
    rows = parse(raw.decode("utf-8", "replace"), past_days=int(cfg.get("past_days") or 30), future_days=int(cfg.get("future_days") or 180),
                 tz_name=cfg.get("timezone") or os.environ.get("BI_TZ"))
    return HEADER, rows, host
