"""Full-stack depth: tokens, API specs, containers, CI, migrations, web performance, accessibility, capacity maths."""
from __future__ import annotations

import base64
import json
import math
import re
import time

from app.services.prolab import ProError, lab, lines, num, r, ref, tool, txt

T = "fullstack"
lab(T, "Full-stack depth: auth, APIs, containers, CI, migrations, performance, accessibility and capacity")


def _b64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def jwt(a):
    tok = txt(a, "token", "a token", limit=8000).replace("Bearer ", "").strip()
    parts = tok.split(".")
    if len(parts) != 3:
        raise ProError("A JWT has three parts separated by dots.")
    try:
        head, pay = json.loads(_b64(parts[0])), json.loads(_b64(parts[1]))
    except Exception:  # noqa: BLE001
        raise ProError("The header or payload is not valid base64 JSON.") from None
    issues = []
    alg = str(head.get("alg", ""))
    if alg.lower() == "none":
        issues.append("alg is none: the token is unsigned. Servers must reject it.")
    if alg.startswith("HS"):
        issues.append("HMAC (HS) signing shares one secret between issuer and verifier: use RS256 or ES256 when other services only verify.")
    now = time.time()
    exp, iat, nbf = pay.get("exp"), pay.get("iat"), pay.get("nbf")
    if exp is None:
        issues.append("No exp claim: the token never expires.")
    elif isinstance(exp, (int, float)):
        if exp < now:
            issues.append(f"Expired {int((now - exp) // 60)} minutes ago.")
        elif iat and exp - iat > 86400:
            issues.append("Lifetime over 24 hours: prefer short access tokens plus a refresh token.")
    if nbf and isinstance(nbf, (int, float)) and nbf > now:
        issues.append("Not valid yet (nbf is in the future).")
    for c in ("iss", "aud", "sub"):
        if c not in pay:
            issues.append(f"No {c} claim: verify issuer, audience and subject on the server.")
    if any(k in pay for k in ("password", "secret", "ssn")):
        issues.append("Sensitive data in the payload: it is only encoded, anyone can read it.")
    return {"header": head, "payload": pay, "issues": issues or ["No obvious problems in the claims."], "signature_checked": False,
            "how": "This only decodes and checks the claims. The signature is never verified here: the server must verify it with the right key and reject alg changes."}


tool(T, "jwt_check", "JWT decoder and checker", "Decode a token and flag weak claims.", [("token", "Paste a JWT", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjMiLCJuYW1lIjoiVGVzdCJ9.sig", "area")], jwt)


def openapi(a):
    raw = txt(a, "spec", "an OpenAPI spec (JSON)", limit=60000)
    try:
        d = json.loads(raw)
    except ValueError:
        raise ProError("Paste the spec as JSON (convert YAML first).") from None
    paths = d.get("paths") or {}
    if not paths:
        raise ProError("No paths found in the spec.")
    issues, ops = [], 0
    if not (d.get("info") or {}).get("version"):
        issues.append("info.version is missing.")
    if not d.get("servers"):
        issues.append("No servers listed.")
    sec = bool(d.get("security") or (d.get("components") or {}).get("securitySchemes"))
    for p, item in paths.items():
        if re.search(r"[A-Z]", p.split("{")[0]):
            issues.append(f"{p}: use lowercase, hyphenated paths.")
        if re.search(r"/(get|create|delete|update)[A-Z/]", p):
            issues.append(f"{p}: verbs belong in the HTTP method, not the path.")
        for m, op in (item or {}).items():
            if m not in ("get", "post", "put", "patch", "delete", "head", "options"):
                continue
            ops += 1
            tag = f"{m.upper()} {p}"
            if not op.get("operationId"):
                issues.append(f"{tag}: no operationId (clients are generated from it).")
            if not op.get("summary") and not op.get("description"):
                issues.append(f"{tag}: no summary.")
            rs = op.get("responses") or {}
            if not any(str(k).startswith("2") for k in rs):
                issues.append(f"{tag}: no 2xx response documented.")
            if not any(str(k).startswith("4") or k == "default" for k in rs):
                issues.append(f"{tag}: no error response documented.")
            if m == "get" and op.get("requestBody"):
                issues.append(f"{tag}: GET should not have a body.")
            if m == "post" and "201" not in rs and not any(str(k) == "200" for k in rs) and "202" not in rs:
                issues.append(f"{tag}: POST usually returns 201, 200 or 202.")
    if not sec:
        issues.append("No security scheme defined: say how callers authenticate.")
    return {"paths": len(paths), "operations": ops, "issues": issues or ["No lint findings."], "tips": ["Version the API (in the path or a header) before clients depend on it.", "Document pagination, rate limits and error body shape once, and reuse it.", "Lint in CI so the spec cannot drift from the code."]}


tool(T, "openapi_lint", "OpenAPI lint", "Check a JSON OpenAPI spec for common gaps.", [("spec", "Paste OpenAPI JSON", '{"openapi":"3.0.0","info":{"title":"Shop","version":"1"},"paths":{"/getOrders":{"get":{"responses":{"200":{"description":"ok"}}}}}}', "area")], openapi)


def docker(a):
    txt_ = txt(a, "dockerfile", "a Dockerfile")
    ls = [x.strip() for x in txt_.splitlines() if x.strip() and not x.strip().startswith("#")]
    out = []
    frm = [x for x in ls if x.upper().startswith("FROM ")]
    if not frm:
        out.append("No FROM line.")
    for f in frm:
        img = f.split()[1]
        if img.endswith(":latest") or ":" not in img and "@" not in img and img != "scratch":
            out.append(f"{img}: pin a version (or digest) instead of latest so builds repeat.")
        if not re.search(r"slim|alpine|distroless|scratch", img):
            out.append(f"{img}: consider a slim, alpine or distroless base for size and attack surface.")
    if not any(x.upper().startswith("USER ") for x in ls):
        out.append("No USER line: the container runs as root. Add a non-root user.")
    if any(re.search(r"(password|secret|api_key|token)\s*=", x, re.I) for x in ls if x.upper().startswith(("ENV", "ARG"))):
        out.append("A secret in ENV or ARG is baked into the image layers. Pass secrets at run time.")
    if any(re.match(r"ADD\s+https?://", x, re.I) for x in ls):
        out.append("ADD from a URL is unverified: use curl with a checksum, or COPY.")
    cp = [i for i, x in enumerate(ls) if re.match(r"COPY\s+\.\s", x, re.I)]
    inst = [i for i, x in enumerate(ls) if re.search(r"(pip install|npm (ci|install)|apt-get install|yarn install)", x)]
    if cp and inst and min(cp) < min(inst):
        out.append("COPY . comes before the dependency install: any code change reruns the install. Copy the manifest first, install, then copy the code.")
    for x in ls:
        if "apt-get install" in x and "--no-install-recommends" not in x:
            out.append("apt-get install without --no-install-recommends adds extra packages.")
            break
    if any("apt-get update" in x for x in ls) and not any("rm -rf /var/lib/apt/lists" in x for x in ls):
        out.append("Clean /var/lib/apt/lists in the same RUN to keep the layer small.")
    if sum(1 for x in frm) < 2 and any(re.search(r"(gcc|build-essential|npm run build)", x) for x in ls):
        out.append("Build tools in the final image: use a multi-stage build and copy only the result.")
    if not any(x.upper().startswith("HEALTHCHECK") for x in ls):
        out.append("No HEALTHCHECK (optional: an orchestrator may do it instead).")
    return {"findings": out or ["No findings."], "lines_read": len(ls), "also": ["Add a .dockerignore (node_modules, .git, .env).", "Scan the image for known vulnerabilities in CI."]}


tool(T, "dockerfile_review", "Dockerfile review", "Spot root users, unpinned bases, secrets and cache problems.", [("dockerfile", "Paste a Dockerfile", "FROM python:latest\nCOPY . /app\nRUN pip install -r requirements.txt\nENV API_KEY=abc123\nCMD python app.py", "area")], docker)


def gha(a):
    lang = txt(a, "language").lower()
    cfg = {"python": ("actions/setup-python@v5", "python-version: '3.12'", "pip install -r requirements.txt", "pytest -q", "pip"),
           "node": ("actions/setup-node@v4", "node-version: 20", "npm ci", "npm test", "npm"),
           "go": ("actions/setup-go@v5", "go-version: '1.22'", "go mod download", "go test ./...", None)}.get(lang)
    if not cfg:
        raise ProError("Language must be python, node or go.")
    branch = txt(a, "branch", required=False) or "main"
    act, ver, inst, test, cache = cfg
    y = [f"name: CI", "on:", "  push:", f"    branches: [{branch}]", "  pull_request:", "permissions:", "  contents: read", "jobs:", "  test:", "    runs-on: ubuntu-latest", "    steps:", "      - uses: actions/checkout@v4", f"      - uses: {act}", "        with:", f"          {ver}"]
    if cache:
        y.append(f"          cache: {cache}")
    y += [f"      - run: {inst}", f"      - run: {test}"]
    return {"workflow_yaml": "\n".join(y), "tips": ["Save as .github/workflows/ci.yml.", "Permissions are read-only by default here: widen only what a job needs.", "Pin third-party actions to a commit hash for supply-chain safety.", "Add a lint and type check step, and run the build for web apps."]}


tool(T, "ci_workflow", "GitHub Actions starter", "A safe CI workflow file for your language.", [("language", "python, node or go", "python"), ("branch", "Branch", "main")], gha)


def migration(a):
    sql = txt(a, "sql", "migration SQL")
    low = re.sub(r"--.*", "", sql).lower()
    out = []
    checks = [(r"drop\s+table", "DROP TABLE destroys data: take a backup and ship it in a later release after code stops using it."),
              (r"drop\s+column", "DROP COLUMN breaks old code still running during deploy: remove usage first, drop later."),
              (r"alter\s+table\s+\w+\s+add\s+column\s+\w+\s+\w+[^;]*not\s+null(?![^;]*default)", "Adding a NOT NULL column with no default fails on existing rows (or rewrites the table)."),
              (r"alter\s+column\s+\w+\s+(set\s+data\s+)?type", "Changing a column type can rewrite and lock the table."),
              (r"rename\s+(column|to)", "Renaming breaks code that is still running: add the new name, copy, switch, then drop."),
              (r"create\s+index(?!\s+concurrently)(?![^;]*if\s+not)", "On PostgreSQL use CREATE INDEX CONCURRENTLY on big tables to avoid blocking writes."),
              (r"truncate", "TRUNCATE removes all rows: confirm this is intended."),
              (r"delete\s+from\s+\w+\s*;", "DELETE without WHERE removes every row."),
              (r"update\s+\w+\s+set[^;]*;(?!.*where)", "UPDATE with no WHERE changes every row; on big tables do it in batches.")]
    for pat, msg in checks:
        if re.search(pat, low, re.S):
            out.append(msg)
    if "begin" not in low and low.count(";") > 1:
        out.append("Several statements and no explicit transaction: a failure part way leaves a half-applied change (some engines auto-wrap).")
    return {"findings": out or ["No risky patterns found."], "safe_pattern": ["Expand: add the new column or table (nullable or with a default).", "Deploy code that writes both and reads the new one.", "Backfill old rows in batches.", "Contract: drop the old column in a later release."], "tips": ["Test the migration on a copy of production data and time it.", "Write the down (rollback) step, or note why it is one-way."]}


tool(T, "migration_lint", "Migration SQL lint", "Flag locking, data-loss and compatibility risks.", [("sql", "Paste migration SQL", "ALTER TABLE users ADD COLUMN plan text NOT NULL;\nDROP TABLE old_logs;\nCREATE INDEX idx_users_plan ON users(plan);", "area")], migration)


def cwv(a):
    lcp, inp, cls = num(a, "lcp_s", lo=0), num(a, "inp_ms", lo=0), num(a, "cls", lo=0)
    g = lambda v, good, poor: "good" if v <= good else ("needs improvement" if v <= poor else "poor")  # noqa: E731
    res = {"LCP": g(lcp, 2.5, 4), "INP": g(inp, 200, 500), "CLS": g(cls, 0.1, 0.25)}
    fixes = []
    if res["LCP"] != "good":
        fixes.append("LCP: compress and size the hero image, preload it, use a CDN, cut server response time, remove render-blocking scripts.")
    if res["INP"] != "good":
        fixes.append("INP: split long JavaScript tasks, defer non-critical scripts, avoid heavy work in click handlers.")
    if res["CLS"] != "good":
        fixes.append("CLS: set width and height on images and embeds, reserve space for ads and banners, avoid inserting content above existing content.")
    return {"scores": res, "passes_all": all(v == "good" for v in res.values()), "fixes": fixes or ["All three are in the good range."], "targets": "Good: LCP 2.5 s or less, INP 200 ms or less, CLS 0.1 or less, at the 75th percentile of real users."}


tool(T, "web_vitals", "Core Web Vitals grader", "Grade LCP, INP and CLS and get fixes.", [("lcp_s", "Largest Contentful Paint (s)", 3.1), ("inp_ms", "Interaction to Next Paint (ms)", 250), ("cls", "Cumulative Layout Shift", 0.05)], cwv)


def _lum(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        raise ProError("Colors must be hex like #1a2b3c.")
    ch = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    ch = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]


def contrast(a):
    f, b = _lum(txt(a, "text_color")), _lum(txt(a, "background"))
    hi, lo = max(f, b), min(f, b)
    c = (hi + 0.05) / (lo + 0.05)
    return {"ratio": r(c, 2), "normal_text_aa": c >= 4.5, "large_text_aa": c >= 3, "normal_text_aaa": c >= 7, "ui_components_aa": c >= 3,
            "verdict": "Passes WCAG AA for normal text." if c >= 4.5 else "Fails AA for normal text" + (" (large text is OK)." if c >= 3 else "."), "note2": "Large text is 18 pt, or 14 pt bold."}


tool(T, "contrast", "Color contrast (WCAG)", "Contrast ratio of text on a background.", [("text_color", "Text color (hex)", "#767676"), ("background", "Background (hex)", "#ffffff")], contrast)


def a11y(a):
    h = txt(a, "html", "HTML", limit=60000)
    out = []
    for m in re.finditer(r"<img\b[^>]*>", h, re.I):
        if not re.search(r"\balt\s*=", m.group(0), re.I):
            out.append("An <img> has no alt text (use alt=\"\" for decoration).")
    if not re.search(r"<html[^>]*\blang=", h, re.I) and "<html" in h.lower():
        out.append("<html> has no lang attribute.")
    if "<title" not in h.lower() and "<html" in h.lower():
        out.append("No <title>.")
    for m in re.finditer(r"<a\b[^>]*>(.*?)</a>", h, re.I | re.S):
        t = re.sub(r"<[^>]+>", "", m.group(1)).strip().lower()
        if t in ("click here", "here", "read more", "more", "link"):
            out.append(f"Vague link text \"{t}\": say where it goes.")
        if not t and "aria-label" not in m.group(0).lower() and "<img" not in m.group(1).lower():
            out.append("A link has no text or label.")
    for m in re.finditer(r"<input\b[^>]*>", h, re.I):
        tag = m.group(0)
        if re.search(r'type\s*=\s*"?(hidden|submit|button)', tag, re.I):
            continue
        idm = re.search(r'\bid\s*=\s*"([^"]+)"', tag)
        if not ((idm and re.search(rf'for\s*=\s*"{re.escape(idm.group(1))}"', h)) or "aria-label" in tag.lower()):
            out.append("An <input> has no label (use <label for> or aria-label).")
    for m in re.finditer(r"<(div|span)\b[^>]*onclick", h, re.I):
        out.append("A clickable <div>/<span>: use a <button> so keyboard and screen-reader users can use it.")
    hs = [int(x) for x in re.findall(r"<h([1-6])", h, re.I)]
    if hs and hs[0] != 1:
        out.append("The first heading is not an h1.")
    if any(b - a_ > 1 for a_, b in zip(hs, hs[1:])):
        out.append("A heading level is skipped (for example h2 to h4).")
    if re.search(r"tabindex\s*=\s*\"?[1-9]", h):
        out.append("Positive tabindex breaks the natural tab order.")
    out = list(dict.fromkeys(out))
    return {"findings": out or ["No problems found by these checks."], "limits": "A pattern check finds only some problems. Also test with the keyboard alone, zoom to 200%, and a screen reader, and run an axe or Lighthouse audit."}


tool(T, "a11y_html", "Accessibility HTML check", "Spot missing alt text, labels and heading problems.", [("html", "Paste HTML", '<html><body><h2>Shop</h2><img src="a.png"><a href="/x">click here</a><input id="e" type="text"><div onclick="go()">Buy</div></body></html>', "area")], a11y)


def cache(a):
    h, tc, to, rps = num(a, "hit_rate_pct", lo=0, hi=100) / 100, num(a, "cache_ms", lo=0), num(a, "origin_ms", lo=0), num(a, "requests_per_s", lo=0)
    avg = h * tc + (1 - h) * to
    return {"average_ms": r(avg, 2), "origin_requests_per_s": r(rps * (1 - h), 1), "origin_load_cut_pct": r(h * 100, 1), "speedup": r(to / avg, 2) if avg else None,
            "tips": ["Raising the hit rate from 90% to 99% cuts origin load 10 times.", "Set a time-to-live that matches how stale the data may be, and plan invalidation.", "Guard against a stampede when a hot key expires (locking or early refresh)."]}


tool(T, "cache_math", "Cache hit rate and latency", "Average latency and origin load.", [("hit_rate_pct", "Hit rate (%)", 90), ("cache_ms", "Cache latency (ms)", 2), ("origin_ms", "Origin latency (ms)", 120), ("requests_per_s", "Requests per second", 500)], cache)


def little(a):
    lam, w, svc, workers = num(a, "arrival_per_s", lo=0), num(a, "time_in_system_s", lo=0), num(a, "service_s", lo=0, strict=True), int(num(a, "workers", lo=1))
    inflight = lam * w
    cap = workers / svc
    util = lam / cap
    return {"in_flight_items": r(inflight, 2), "capacity_per_s": r(cap, 2), "utilization_pct": r(util * 100, 1), "workers_for_70pct": math.ceil(lam * svc / 0.7),
            "verdict": "Overloaded: the queue grows without limit." if util >= 1 else "Heavily loaded: waits climb quickly above 80%." if util > 0.8 else "Healthy headroom.",
            "how": "Little's law: items in the system = arrival rate x time each spends there. Utilization = arrivals x service time / workers."}


tool(T, "queue_sizing", "Queue and worker sizing", "Little's law and worker count.", [("arrival_per_s", "Arrivals per second", 40), ("time_in_system_s", "Average time in system (s)", 0.5), ("service_s", "Service time per item (s)", 0.2), ("workers", "Workers", 10)], little)


def hashcost(a):
    rate, pw = num(a, "guesses_per_s", lo=1), num(a, "charset_size", lo=2)
    ln = int(num(a, "length", lo=1, hi=64))
    space = pw ** ln
    secs = space / 2 / rate
    yrs = secs / 31557600
    return {"combinations": f"{space:.3e}", "bits": r(ln * math.log2(pw), 1), "average_crack_time": f"{yrs:.3g} years" if yrs >= 1 else f"{secs:.3g} seconds",
            "tips": ["Use a slow password hash (argon2id, bcrypt or scrypt), never plain SHA or MD5.", "A guess rate of 1e10 per second is plausible for a fast hash on a GPU rack; a good slow hash is thousands of times lower.", "Length beats complexity; check passwords against breach lists."]}


tool(T, "hash_cost", "Password hash crack time", "How long guessing takes at a given rate.", [("guesses_per_s", "Guesses per second", 10000000000), ("charset_size", "Characters possible (26, 62, 95)", 62), ("length", "Password length", 8)], hashcost)

ref(T, "auth", "Auth: OAuth, OIDC, JWT and sessions", [
    {"title": "Pick the right tool", "head": ["Need", "Use", "Why"], "rows": [["Log users into your web app", "Server session cookie (HttpOnly, Secure, SameSite)", "Easy to revoke, safe from script theft"], ["Sign in with Google or Microsoft", "OpenID Connect (OIDC) with the authorization code flow and PKCE", "Identity from a provider you trust"], ["Let an app act for a user on another service", "OAuth 2.0 authorization code with PKCE", "Scoped, revocable access"], ["Service to service", "Client credentials or mutual TLS", "No user involved"], ["Mobile or single-page app", "Code flow with PKCE, short access tokens, refresh rotation", "No secret can be stored safely in the client"]]},
    {"title": "Habits", "items": ["Never put tokens in URLs or local storage when a cookie will do.", "Check issuer, audience, expiry and signature on every request.", "Hash passwords with argon2id or bcrypt; add rate limits and multi-factor authentication.", "Rotate refresh tokens and detect reuse.", "Authorization is separate: check what this user may do on each request, on the server."]}])
ref(T, "testing", "Testing pyramid", [
    {"title": "Mix", "items": ["Many fast unit tests for logic.", "Fewer integration tests with a real database and real HTTP handlers.", "A handful of end-to-end tests for the money paths (sign in, buy, pay).", "Contract tests where teams or services meet.", "Test the failure paths: timeouts, bad input, duplicate requests."]},
    {"title": "Keep tests healthy", "items": ["A flaky test is a bug: fix or delete it, never ignore it.", "Make tests independent and repeatable: fresh data each run, fixed clocks.", "Run them in CI on every pull request.", "Coverage shows what is not tested, not that the rest is good."]}])
ref(T, "observe", "Observability", [
    {"title": "Three signals", "items": ["Logs: structured JSON with request id, user id (hashed if needed) and error details; never log secrets.", "Metrics: rate, errors, duration (RED) for services; utilization, saturation, errors (USE) for resources.", "Traces: follow one request across services to find the slow hop."]},
    {"title": "Alerting", "items": ["Alert on symptoms users feel (errors, slowness), not every cause.", "Every alert needs an owner and a runbook.", "Set service level objectives (for example 99.9% of requests succeed) and track the error budget.", "Test that the alert fires."]}])
ref(T, "apidesign", "API design", [
    {"title": "Rules of thumb", "items": ["Nouns in paths, verbs as methods: GET /orders/42, not /getOrder.", "Return the right status: 201 created, 204 no content, 400 bad input, 401 not signed in, 403 not allowed, 404 missing, 409 conflict, 429 slow down.", "Use one error shape everywhere with a code and a message.", "Paginate lists (cursor pagination scales better than offset).", "Make writes safe to retry with an idempotency key.", "Version before breaking anyone and deprecate with notice."]}])
ref(T, "git", "Git workflow", [
    {"title": "Team habits", "items": ["Small branches, short-lived, merged by pull request with review.", "Write messages that say why, in the imperative: \"Fix double charge on retry\".", "Protect the main branch: required checks, no force pushes.", "Rebase to keep your branch current, or merge: pick one and stay consistent.", "Never commit secrets; if you do, rotate them (deleting the commit is not enough).", "Tag releases and keep a changelog."]}])
ref(T, "design", "System design exercises", [
    {"title": "Method", "items": ["Clarify: users, features, scale, read/write ratio, latency and consistency needs.", "Estimate: requests per second, storage per year, bandwidth.", "Sketch: client, load balancer, stateless app servers, database, cache, queue, object storage.", "Go deep on the hardest part: data model, hot keys, ordering, failure.", "State trade-offs and what you would monitor."]},
    {"title": "Practice prompts", "items": ["A URL shortener", "A chat app with online status", "A feed that shows friends' posts", "A rate limiter", "A file upload service with virus scanning", "A booking system that prevents double booking"]}])
