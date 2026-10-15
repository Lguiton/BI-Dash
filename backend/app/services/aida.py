"""Project AIDA link: lets the owner's operations dashboard (Project AIDA, on this same computer) see that the BI
dashboard is running, which requests failed unexpectedly, and a few counts. Off unless BOTH are set in backend/.env:

    AIDA_INTAKE_URL      http://127.0.0.1:8006/intake/errors
    AIDA_INTAKE_SECRET   the secret AIDA shows when the product "bi-dashboard" is added

Why the dashboard reports to AIDA instead of AIDA calling it: this app runs on Windows and AIDA runs inside Ubuntu (WSL),
where 127.0.0.1 is Ubuntu itself, so AIDA cannot reach http://127.0.0.1:8020/health. Instead the dashboard sends its
status once a minute (AIDA_HEARTBEAT_SECONDS). When the dashboard is closed the reports stop and AIDA shows it as Down
after a few minutes; that is expected for an app that is not always running.

What is sent, and nothing else. Your data never leaves: no table names, values, SQL, questions, file names or paths.

  status         "healthy" or "degraded" (the database did not answer), and the numbers below
  numbers        counts only: lessons completed, data sources and failed loads, failed pipeline runs and data-quality
                 checks in the last 24 hours, hours since the last Real-data backup; and today's AI questions, tokens and
                 (only if you set BI_PRICE_* prices) estimated cost
  error report   the exception CLASS NAME, the route template (for example /api/sql/run, never the query string),
                 the method, and the stack as project-relative file + line + function name.
                 The error MESSAGE is not sent: database errors can quote your data.

Everything is signed with HMAC-SHA256 over "<timestamp>.<body>". Only a loopback address (127.0.0.1, localhost) is
accepted for AIDA_INTAKE_URL; anything else leaves the link switched off. Redirects are refused. Every failure here is
swallowed: AIDA being down or missing changes nothing for the dashboard.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import threading
import time
import traceback
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TIMEOUT_SECONDS = 3.0
MAX_FRAMES = 15
REPEAT_SECONDS = 600          # the same error is reported at most once per 10 minutes
_LOOPBACK = ("127.0.0.1", "localhost", "::1")


def product_id() -> str:
    return os.environ.get("AIDA_PRODUCT_ID", "bi-dashboard")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def _local_url(value: str) -> bool:
    try:
        parsed = urlsplit(value or "")
        parsed.port
    except ValueError:
        return False
    return (parsed.scheme in ("http", "https") and parsed.hostname in _LOOPBACK
            and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment)


def intake_url() -> str:
    return os.environ.get("AIDA_INTAKE_URL", "")


def is_enabled() -> bool:
    return bool(os.environ.get("AIDA_INTAKE_SECRET")) and _local_url(intake_url())


def _sibling_url(name: str) -> str:
    base = intake_url().rstrip("/")
    return (base[:-len("/errors")] if base.endswith("/errors") else base) + "/" + name


def sign(body: bytes, secret: str, timestamp: str) -> str:
    return hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


def _signed_post(url: str, payload: dict) -> bool:
    """Blocking. True when AIDA accepted it. Never raises."""
    try:
        body = json.dumps(payload, separators=(",", ":"), default=str).encode()
        timestamp = str(int(time.time()))
        request = urllib.request.Request(url, data=body, method="POST", headers={
            "Content-Type": "application/json", "X-AIDA-Product": product_id(), "X-AIDA-Timestamp": timestamp,
            "X-AIDA-Signature": sign(body, os.environ["AIDA_INTAKE_SECRET"], timestamp)})
        with _opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            response.read(1024)
            return 200 <= response.status < 300
    except Exception as e:  # noqa: BLE001 - AIDA down, wrong URL, timeout: the dashboard carries on
        logger.debug("AIDA report not delivered: %s", type(e).__name__)
        return False


# ---- error reports ------------------------------------------------------------------------

def _frames(error: BaseException) -> list[dict]:
    frames = []
    for frame in traceback.extract_tb(error.__traceback__)[-MAX_FRAMES:]:
        try:
            relative = Path(frame.filename).resolve().relative_to(PROJECT_ROOT).as_posix()
            in_app = not any(part in ("site-packages", ".venv", "venv") for part in relative.split("/"))
        except (ValueError, OSError):
            relative, in_app = "library/" + Path(frame.filename).name, False
        # file, line and function only: never frame.line (the source text) or local variables
        frames.append({"file": relative, "line": frame.lineno, "function": frame.name, "in_app": in_app})
    return frames


def build_report(error: BaseException, method: str, route: str) -> dict:
    frames = _frames(error)
    error_type = type(error).__name__
    in_app = [f for f in frames if f["in_app"]]
    anchor = in_app[-1] if in_app else (frames[-1] if frames else {"file": "", "function": ""})
    method = method if method in ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TASK") else "other"
    return {
        "product": product_id(), "environment": os.environ.get("AIDA_ENVIRONMENT", "local"),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "error_type": error_type, "error_module": type(error).__module__,
        "message": "(not sent: the BI dashboard never shares error text, which can quote your data)",
        "method": method, "route": route, "status": 500,
        "request_id": None, "tenant_id": None, "frames": frames,
        "signature": hashlib.sha256(f"{error_type}|{route}|{anchor['file']}|{anchor['function']}".encode()).hexdigest()[:16],
    }


_last_sent: dict[str, float] = {}
_last_lock = threading.Lock()


def _first_in_a_while(signature: str) -> bool:
    now = time.monotonic()
    with _last_lock:
        if now - _last_sent.get(signature, -REPEAT_SECONDS) < REPEAT_SECONDS:
            return False
        _last_sent[signature] = now
        return True


def report_error(error: BaseException, method: str, route: str) -> None:
    """Returns at once; never raises. route is a route TEMPLATE ("/api/sql/run") or a task name ("scheduler")."""
    try:
        if not is_enabled():
            return
        report = build_report(error, method, route)
        if _first_in_a_while(report["signature"]):
            threading.Thread(target=_signed_post, args=(intake_url(), report), daemon=True).start()
    except Exception:  # noqa: BLE001
        pass


def route_template(request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", None) or "(no route)"


# ---- status and numbers ---------------------------------------------------------------------

def _since(hours: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")


def pulse() -> dict:
    """Counts only. A number that cannot be read is left out."""
    from app.services import backups, state
    out: dict[str, float] = {}

    def put(label, read):
        try:
            value = read()
            if type(value) in (int, float):
                out[label] = value
        except Exception:  # noqa: BLE001
            pass

    def count(sql, params=()):
        return int(state.one(sql, params)["n"])

    day_ago = _since(24)
    put("Lessons completed", lambda: count("SELECT count(*) AS n FROM study_progress"))
    put("Lessons completed (7 days)", lambda: count("SELECT count(*) AS n FROM study_progress WHERE done_at >= ?", (_since(24 * 7),)))
    put("Data sources", lambda: count("SELECT count(*) AS n FROM sources"))
    put("Failed source loads (24h)", lambda: count("SELECT count(*) AS n FROM source_runs WHERE ok = 0 AND at >= ?", (day_ago,)))
    put("Failed pipeline runs (24h)", lambda: count("SELECT count(*) AS n FROM pipeline_runs WHERE ok = 0 AND at >= ?", (day_ago,)))
    put("Failed data-quality checks (24h)", lambda: count("SELECT count(*) AS n FROM dq_runs WHERE failed > 0 AND at >= ?", (day_ago,)))

    def hours_since_backup():
        latest = backups.list_backups("real")
        if not latest:
            return None
        made = datetime.strptime(latest[0]["created_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return round((datetime.now(timezone.utc) - made).total_seconds() / 3600, 1)

    put("Hours since last Real backup", hours_since_backup)
    return out


def ai_usage() -> dict:
    """Today's and this month's AI questions from the AI log (UTC days). Cost only when BI_PRICE_* prices are set."""
    from app.services import state, usage
    now = datetime.now(timezone.utc)
    today, month = now.strftime("%Y-%m-%d 00:00:00"), now.strftime("%Y-%m-01 00:00:00")
    rows = state.rows("SELECT provider, created_at >= ? AS is_today, count(*) AS calls, "
                      "COALESCE(sum(input_tokens), 0) AS tin, COALESCE(sum(output_tokens), 0) AS tout "
                      "FROM ai_log WHERE created_at >= ? GROUP BY provider, is_today", (today, month))
    calls = tokens = 0
    cost_today = cost_month = 0.0
    priced = False
    for r in rows:
        cost = usage._cost(r["provider"], int(r["tin"]), int(r["tout"])) if r["provider"] in usage.PROVIDERS else None
        if cost is not None:
            priced = True
            cost_month += cost
        if r["is_today"]:
            calls += int(r["calls"])
            tokens += int(r["tin"]) + int(r["tout"])
            cost_today += cost or 0.0
    out = {"calls_today": calls, "tokens_today": tokens}
    if priced:
        out.update(cost_usd_today=round(cost_today, 4), cost_usd_month=round(cost_month, 4))
    return out


def status() -> dict:
    """The status document sent to AIDA. No data, names or paths are in it."""
    from app.services import db
    try:
        with db.get_cursor() as cur:
            cur.execute("SELECT 1").fetchone()
        reachable = True
    except Exception:  # noqa: BLE001
        reachable = False
    doc = {"status": "healthy" if reachable else "degraded", "engine": "DuckDB", "database_reachable": reachable,
           "checked_at": datetime.now(timezone.utc).isoformat(), "pulse": pulse()}
    if not reachable:
        doc["detail"] = "the dashboard's database did not answer"
    try:
        doc["ai_usage"] = ai_usage()
    except Exception:  # noqa: BLE001
        pass
    return doc


def send_status() -> bool:
    if not is_enabled():
        return False
    return _signed_post(_sibling_url("health"), {**status(), "product": product_id()})


def heartbeat_seconds() -> float:
    try:
        return max(15.0, float(os.environ.get("AIDA_HEARTBEAT_SECONDS", "60")))
    except ValueError:
        return 60.0


async def _loop() -> None:
    while True:
        try:
            if is_enabled():
                await asyncio.to_thread(send_status)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(heartbeat_seconds())


def start():
    """Called once at startup. Returns the background task, or None when the link is off."""
    if not is_enabled():
        return None
    try:
        return asyncio.get_running_loop().create_task(_loop())
    except Exception:  # noqa: BLE001
        return None


async def stop(task) -> None:
    if task is not None:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
