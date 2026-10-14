"""Security study tools: JWT and certificate inspectors, CVSS 3.1 base score, STRIDE worksheet, code pattern scanner,
Sigma-style rule matcher and a playbook simulator. Everything runs on text you paste; nothing is sent or executed."""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import math
import re
from datetime import datetime, timezone

from app.services.security import SecError

MAXT = 200_000


def _now(now=None):
    return now or datetime.now(timezone.utc)


# ------------------------------------------------------------------ JWT
def _b64(part: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))
    except (binascii.Error, ValueError):
        raise SecError("That part of the token is not valid base64url.") from None


def jwt_inspect(token: str, secret: str | None = None, now: datetime | None = None) -> dict:
    t = (token or "").strip()
    if t.lower().startswith("bearer "):
        t = t[7:].strip()
    parts = t.split(".")
    if len(parts) not in (2, 3) or not all(p or i == 2 for i, p in enumerate(parts)):
        raise SecError("A JWT has three parts separated by dots: header.payload.signature.")
    try:
        head = json.loads(_b64(parts[0]))
        pay = json.loads(_b64(parts[1]))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise SecError("The header or payload is not JSON, so this is not a normal JWT.") from None
    if not isinstance(head, dict) or not isinstance(pay, dict):
        raise SecError("The header and payload must be JSON objects.")
    n = _now(now).timestamp()
    f = []

    def add(sev, msg):
        f.append({"severity": sev, "finding": msg})
    alg = str(head.get("alg", ""))
    if alg.lower() == "none" or len(parts) == 2 or not parts[2]:
        add("high", "The token is unsigned (alg none or no signature). A server that accepts it lets anyone make a token.")
    if alg.startswith("HS"):
        add("info", f"{alg} uses one shared secret for signing and checking. Anyone who can check it can also forge it; a weak secret can be guessed offline.")
    if "jku" in head or "x5u" in head or "jwk" in head:
        add("medium", "The header names where to fetch the key (jku, x5u or jwk). A server that trusts this can be pointed at an attacker's key.")
    if "kid" not in head and alg.startswith(("RS", "ES", "PS")):
        add("info", "No key id (kid): harder to rotate keys.")
    times = {}
    for k in ("exp", "nbf", "iat"):
        v = pay.get(k)
        if v is None:
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            add("medium", f"'{k}' should be a number of seconds since 1970.")
            continue
        times[k] = v
    if "exp" not in times:
        add("medium", "No expiry (exp). A stolen token would work forever.")
    else:
        if times["exp"] < n:
            add("info", f"Expired {int(n - times['exp'])} seconds ago.")
        if "iat" in times and times["exp"] - times["iat"] > 86400 * 30:
            add("low", "Lifetime is over 30 days. Long-lived tokens are valuable to thieves.")
    if "nbf" in times and times["nbf"] > n:
        add("info", "Not valid yet (nbf is in the future).")
    if "iat" in times and times["iat"] > n + 300:
        add("low", "Issued in the future: clock difference or a made-up token.")
    for k, why in (("iss", "who issued it"), ("aud", "who it is for"), ("sub", "who it is about")):
        if k not in pay:
            add("low" if k != "sub" else "info", f"No '{k}' claim ({why}). Checking issuer and audience stops a token for one service working on another.")
    for k in pay:
        if re.search(r"pass(word)?|secret|ssn|card", k, re.I):
            add("high", f"The claim '{k}' looks sensitive. The payload is only encoded, not encrypted; anyone holding the token can read it.")
    verified = None
    if secret:
        if alg in ("HS256", "HS384", "HS512") and len(parts) == 3:
            h = {"HS256": hashlib.sha256, "HS384": hashlib.sha384, "HS512": hashlib.sha512}[alg]
            sig = hmac.new(secret.encode(), f"{parts[0]}.{parts[1]}".encode(), h).digest()
            verified = hmac.compare_digest(sig, _b64(parts[2]))
        else:
            add("info", "Signature checking here only supports HS256, HS384 and HS512 with a secret.")
    dates = {k: datetime.fromtimestamp(v, timezone.utc).isoformat() for k, v in times.items() if abs(v) < 4e10}
    return {"header": head, "payload": pay, "dates": dates, "signature_checked": verified, "findings": f,
            "lesson": "A JWT payload is readable by anyone. The signature only proves it was not changed. Decoding is not verifying: the server must check the signature, the algorithm it expects, the expiry, the issuer and the audience."}


# ------------------------------------------------------------------ certificate
def cert_inspect(pem: str, now: datetime | None = None) -> dict:
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
    except ImportError:
        raise SecError("The 'cryptography' package is not installed (pip install cryptography).", 503) from None
    txt = (pem or "").strip()
    if "PRIVATE KEY" in txt:
        raise SecError("That is a private key. Never paste a private key into any tool. Paste the certificate (BEGIN CERTIFICATE) instead.")
    try:
        c = x509.load_pem_x509_certificate(txt.encode())
    except ValueError:
        raise SecError("Paste one certificate in PEM form, starting with -----BEGIN CERTIFICATE-----.") from None
    k = c.public_key()
    if isinstance(k, rsa.RSAPublicKey):
        ktype, bits = "RSA", k.key_size
    elif isinstance(k, ec.EllipticCurvePublicKey):
        ktype, bits = f"EC {k.curve.name}", k.key_size
    elif isinstance(k, ed25519.Ed25519PublicKey):
        ktype, bits = "Ed25519", 256
    else:
        ktype, bits = type(k).__name__, 0
    try:
        sans = c.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
    except x509.ExtensionNotFound:
        sans = []
    try:
        bc = c.extensions.get_extension_for_class(x509.BasicConstraints).value
        is_ca, path_len = bc.ca, bc.path_length
    except x509.ExtensionNotFound:
        is_ca, path_len = None, None
    nb, na = c.not_valid_before_utc, c.not_valid_after_utc
    n = _now(now)
    days = (na - n).days
    sig = c.signature_hash_algorithm.name if c.signature_hash_algorithm else "none"
    f = []

    def add(sev, msg):
        f.append({"severity": sev, "finding": msg})
    if n > na:
        add("high", f"Expired {-days} days ago.")
    elif n < nb:
        add("high", "Not valid yet.")
    elif days <= 30:
        add("medium", f"Expires in {days} days: renew soon.")
    if sig in ("md5", "sha1"):
        add("high", f"Signed with {sig.upper()}, which is broken for signatures; browsers reject it.")
    if ktype == "RSA" and bits < 2048:
        add("high", f"RSA key of {bits} bits is too small; use 2048 or more.")
    if not sans:
        add("medium", "No Subject Alternative Name. Browsers match the site name against SANs, not the old common name.")
    if (na - nb).days > 398 and is_ca is not True:
        add("low", f"Valid for {(na - nb).days} days. Public web certificates are limited to about 398 days, and shorter is the trend.")
    if c.issuer == c.subject:
        add("info", "Self-issued (issuer equals subject). Fine for a root or a lab, but clients need to be told to trust it.")
    return {"subject": c.subject.rfc4514_string(), "issuer": c.issuer.rfc4514_string(), "valid_from": nb.isoformat(), "valid_to": na.isoformat(), "days_left": days,
            "key": f"{ktype} {bits} bits", "signature_hash": sig, "names": sans, "is_ca": is_ca, "path_length": path_len, "sha256_fingerprint": c.fingerprint(hashes.SHA256()).hex(), "findings": f,
            "lesson": "A certificate binds names to a public key and is signed by an issuer. Check the names, the dates, the key strength and the signature algorithm, and remember that this tool cannot check the chain or revocation."}


# ------------------------------------------------------------------ CVSS 3.1
_W = {"AV": {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}, "AC": {"L": 0.77, "H": 0.44}, "UI": {"N": 0.85, "R": 0.62}, "C": {"H": 0.56, "L": 0.22, "N": 0}, "I": {"H": 0.56, "L": 0.22, "N": 0}, "A": {"H": 0.56, "L": 0.22, "N": 0}}
_NAMES = {"AV": "Attack vector", "AC": "Attack complexity", "PR": "Privileges required", "UI": "User interaction", "S": "Scope", "C": "Confidentiality", "I": "Integrity", "A": "Availability"}
_VAL = {"AV": {"N": "Network", "A": "Adjacent", "L": "Local", "P": "Physical"}, "AC": {"L": "Low", "H": "High"}, "PR": {"N": "None", "L": "Low", "H": "High"}, "UI": {"N": "None", "R": "Required"},
        "S": {"U": "Unchanged", "C": "Changed"}, "C": {"H": "High", "L": "Low", "N": "None"}, "I": {"H": "High", "L": "Low", "N": "None"}, "A": {"H": "High", "L": "Low", "N": "None"}}


def _roundup(x: float) -> float:
    i = round(x * 100000)
    return i / 100000.0 if i % 10000 == 0 else (math.floor(i / 10000) + 1) / 10.0


def cvss31(vector: str) -> dict:
    v = (vector or "").strip()
    v = re.sub(r"^CVSS:3\.[01]/", "", v)
    try:
        m = dict(p.split(":") for p in v.split("/"))
    except ValueError:
        raise SecError("Use a vector like CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H.") from None
    for k, opts in _VAL.items():
        if m.get(k) not in opts:
            raise SecError(f"Metric {k} ({_NAMES[k]}) is missing or not one of {', '.join(opts)}.")
    changed = m["S"] == "C"
    pr = {"N": 0.85, "L": 0.68 if changed else 0.62, "H": 0.5 if changed else 0.27}[m["PR"]]
    iss = 1 - (1 - _W["C"][m["C"]]) * (1 - _W["I"][m["I"]]) * (1 - _W["A"][m["A"]])
    imp = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15 if changed else 6.42 * iss
    ex = 8.22 * _W["AV"][m["AV"]] * _W["AC"][m["AC"]] * pr * _W["UI"][m["UI"]]
    if imp <= 0:
        score = 0.0
    else:
        score = _roundup(min(1.08 * (imp + ex), 10)) if changed else _roundup(min(imp + ex, 10))
    sev = "None" if score == 0 else "Low" if score < 4 else "Medium" if score < 7 else "High" if score < 9 else "Critical"
    return {"vector": "CVSS:3.1/" + "/".join(f"{k}:{m[k]}" for k in _VAL), "base_score": score, "severity": sev, "impact_subscore": round(imp, 1), "exploitability_subscore": round(ex, 1),
            "metrics": [{"metric": _NAMES[k], "code": f"{k}:{m[k]}", "meaning": _VAL[k][m[k]]} for k in _VAL],
            "lesson": "CVSS base score rates how bad a flaw is in general, not how risky it is for you. Combine it with how exposed the system is, whether an exploit exists, and what the system is worth."}


# ------------------------------------------------------------------ STRIDE
_STRIDE = {"S": ("Spoofing", "Pretending to be someone or something else", "Strong authentication, no shared accounts, signed messages"),
           "T": ("Tampering", "Changing data or code without permission", "Integrity checks, signatures, least-privilege write access, input validation"),
           "R": ("Repudiation", "Denying an action with no way to prove it", "Tamper-resistant logs with who, what and when"),
           "I": ("Information disclosure", "Exposing data to someone who should not see it", "Encryption in transit and at rest, access control, minimal data"),
           "D": ("Denial of service", "Making the system unusable", "Rate limits, quotas, redundancy, timeouts"),
           "E": ("Elevation of privilege", "Gaining rights you should not have", "Least privilege, separate duties, validate every permission check")}
_APPLIES = {"external": "SR", "process": "STRIDE", "store": "TRID", "flow": "TID"}


def stride(elements: str) -> dict:
    out, seen = [], set()
    for ln in (elements or "").splitlines():
        ln = ln.split("#")[0].strip()
        if not ln:
            continue
        p = [x.strip() for x in ln.split("|")]
        if len(p) < 2 or p[1].lower() not in _APPLIES:
            raise SecError(f"Line '{ln}': use 'name | external|process|store|flow | optional note'.")
        if p[0].lower() in seen:
            raise SecError(f"'{p[0]}' is listed twice.")
        seen.add(p[0].lower())
        out.append({"element": p[0], "type": p[1].lower(), "note": p[2] if len(p) > 2 else "",
                    "threats": [{"letter": c, "threat": _STRIDE[c][0], "meaning": _STRIDE[c][1], "ask": f"How could someone cause '{_STRIDE[c][0].lower()}' at {p[0]}?", "common_defence": _STRIDE[c][2]} for c in _APPLIES[p[1].lower()]]})
    if not out or len(out) > 60:
        raise SecError("Give 1 to 60 elements of your data flow diagram.")
    return {"elements": out, "total_questions": sum(len(e["threats"]) for e in out),
            "lesson": "STRIDE is a checklist of six kinds of threat. Walk every element of a data flow diagram and ask each question that applies; write down what you decide to do about each answer."}


STRIDE_SAMPLE = "User | external\nWeb app | process\nOrders database | store\nUser to web app (HTTPS) | flow\nWeb app to database | flow"

# ------------------------------------------------------------------ code scanner
_RULES = [
    ("secret", "high", r"AKIA[0-9A-Z]{16}", "An AWS access key id.", "Remove it, rotate the key, and load secrets from the environment or a secret store."),
    ("secret", "high", r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----", "A private key in the code.", "Remove it, treat it as stolen, issue a new one."),
    ("secret", "high", r"""(?i)\b(password|passwd|secret|api[_-]?key|token)\b\s*[:=]\s*['"][^'"\s]{6,}['"]""", "A hard-coded credential.", "Read it from an environment variable or secret store; rotate this one."),
    ("injection", "high", r"""(?i)\b(execute|query|raw)\s*\(\s*(f['"]|"[^"]*(select|insert|update|delete)[^"]*"\s*(\+|%|\.format)|'[^']*(select|insert|update|delete)[^']*'\s*(\+|%|\.format))""", "SQL built by joining strings.", "Use parameters: execute(sql, (value,))."),
    ("injection", "high", r"(?i)\bsubprocess\.\w+\([^)]*shell\s*=\s*True|\bos\.system\(", "A shell command, which is injectable if any part comes from a user.", "Pass a list of arguments with shell=False."),
    ("injection", "high", r"\beval\(|\bexec\(", "Running text as code.", "Parse the data instead (json, ast.literal_eval)."),
    ("deserialize", "high", r"\bpickle\.loads?\(|\byaml\.load\((?![^)]*SafeLoader)|\bmarshal\.loads?\(", "Loading untrusted data can run code.", "Use JSON or yaml.safe_load."),
    ("crypto", "medium", r"(?i)\b(md5|sha1)\b\s*\(|hashlib\.(md5|sha1)\(", "A weak hash.", "Use SHA-256 or better; for passwords use bcrypt, scrypt or argon2."),
    ("crypto", "medium", r"(?i)verify\s*=\s*False|rejectUnauthorized\s*:\s*false|InsecureSkipVerify\s*:\s*true", "Certificate checking is turned off.", "Leave verification on; trust a private CA properly instead."),
    ("crypto", "medium", r"\brandom\.(random|randint|choice)\(", "Not a secure random source (only a problem for tokens and keys).", "Use the secrets module for anything security-related."),
    ("web", "medium", r"(?i)\.innerHTML\s*=|dangerouslySetInnerHTML|document\.write\(", "Putting text into the page as HTML can allow script injection.", "Use textContent or a sanitiser."),
    ("config", "medium", r"(?i)\bdebug\s*=\s*True\b|app\.run\([^)]*debug\s*=\s*True", "Debug mode left on.", "Turn it off in production."),
    ("config", "low", r"(?i)http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0|example\.)[\w.-]+", "A plain-HTTP address.", "Use HTTPS."),
    ("config", "low", r"(?i)\bcors\(.*origin.*\*|Access-Control-Allow-Origin['\"]?\s*[:,]\s*['\"]\*", "Any website may call this API from a browser.", "List the origins you trust."),
]


def _mask(s: str) -> str:
    return s if len(s) < 14 else s[:6] + "..." + s[-2:]


def code_scan(text: str) -> dict:
    if not (text or "").strip():
        raise SecError("Paste some code first.")
    if len(text) > MAXT:
        raise SecError("Over 200 KB; paste a smaller piece.")
    res = []
    for i, ln in enumerate(text.splitlines(), 1):
        if len(ln) > 600:
            continue
        for cat, sev, pat, what, fix in _RULES:
            if m := re.search(pat, ln):
                res.append({"line": i, "category": cat, "severity": sev, "finding": what, "fix": fix, "code": _mask(ln.strip()) if cat == "secret" else ln.strip()[:160]})
    order = {"high": 0, "medium": 1, "low": 2}
    res.sort(key=lambda r: (order[r["severity"]], r["line"]))
    return {"findings": res, "lines": len(text.splitlines()),
            "limits": "A pattern scanner reads lines, not meaning. It misses what it has no pattern for and flags harmless code. It is a first pass before a review, not a replacement for tools such as Semgrep or CodeQL.",
            "lesson": "Most code weaknesses are a few recurring patterns: secrets in code, strings joined into commands or queries, unsafe loading, weak crypto, and switches left off."}


CODE_SAMPLE = 'import hashlib, subprocess\npassword = "hunter2hunter2"\ncur.execute("SELECT * FROM users WHERE name = \'" + name + "\'")\nsubprocess.run(cmd, shell=True)\nh = hashlib.md5(data)\nr = requests.get(url, verify=False)\n'


# ------------------------------------------------------------------ Sigma-style rules
def _sigma_val(ev: dict, key: str, want) -> bool:
    field, *mods = key.split("|")
    have = ev.get(field)
    if have is None:
        return False
    vals = want if isinstance(want, list) else [want]
    allm = "all" in mods
    op = next((m for m in mods if m in ("contains", "startswith", "endswith", "re")), "equals")
    h = str(have)

    def one(w):
        if w is None:
            return False
        w = str(w)
        if op == "contains":
            return w.lower() in h.lower()
        if op == "startswith":
            return h.lower().startswith(w.lower())
        if op == "endswith":
            return h.lower().endswith(w.lower())
        if op == "re":
            return re.search(w, h) is not None
        return h.lower() == w.lower()
    return all(one(w) for w in vals) if allm else any(one(w) for w in vals)


def _sel(ev: dict, sel) -> bool:
    if isinstance(sel, list):
        return any(_sel(ev, s) for s in sel)
    if not isinstance(sel, dict):
        raise SecError("A selection must be a map of field to value (or a list of maps).")
    return all(_sigma_val(ev, k, v) for k, v in sel.items())


def _cond(expr: str, sels: dict, ev: dict) -> bool:
    toks = re.findall(r"\(|\)|[\w*]+", expr)
    pos = 0

    def peek():
        return toks[pos] if pos < len(toks) else None

    def nxt():
        nonlocal pos
        pos += 1
        return toks[pos - 1]

    def names(pat):
        rx = re.compile("^" + re.escape(pat).replace(r"\*", ".*") + "$")
        got = [n for n in sels if rx.match(n)]
        if not got:
            raise SecError(f"The condition names '{pat}', which is not defined under detection.")
        return got

    def atom():
        t = nxt()
        if t == "(":
            v = orx()
            if nxt() != ")":
                raise SecError("Missing ) in the condition.")
            return v
        if t == "not":
            return not atom()
        if t in ("1", "all") and peek() == "of":
            nxt()
            g = names(nxt())
            r = [_sel(ev, sels[n]) for n in g]
            return any(r) if t == "1" else all(r)
        return _sel(ev, sels[names(t)[0]]) if t in sels else _bad(t)

    def _bad(t):
        raise SecError(f"The condition names '{t}', which is not defined under detection.")

    def andx():
        v = atom()
        while peek() == "and":
            nxt()
            r = atom()
            v = v and r
        return v

    def orx():
        v = andx()
        while peek() == "or":
            nxt()
            r = andx()
            v = v or r
        return v
    try:
        out = orx()
    except IndexError:
        raise SecError("The condition ended too early.") from None
    if pos != len(toks):
        raise SecError(f"Could not read the condition near '{toks[pos]}'.")
    return out


def sigma(rule: str, events: str) -> dict:
    try:
        import yaml
    except ImportError:
        raise SecError("PyYAML is not installed (pip install pyyaml).", 503) from None
    if len(rule or "") > 20000 or len(events or "") > MAXT:
        raise SecError("Rule or events too large.")
    try:
        r = yaml.safe_load(rule)
    except yaml.YAMLError:
        raise SecError("The rule is not valid YAML.") from None
    det = r.get("detection") if isinstance(r, dict) else None
    if not isinstance(det, dict) or "condition" not in det:
        raise SecError("The rule needs a 'detection:' section with a 'condition:'.")
    cond = str(det["condition"])
    sels = {k: v for k, v in det.items() if k != "condition"}
    evs = []
    for i, ln in enumerate((events or "").splitlines(), 1):
        if ln.strip():
            try:
                e = json.loads(ln)
            except json.JSONDecodeError:
                raise SecError(f"Event line {i} is not JSON. Use one JSON object per line.") from None
            if not isinstance(e, dict):
                raise SecError(f"Event line {i} must be a JSON object.")
            evs.append((i, e))
    if not evs or len(evs) > 5000:
        raise SecError("Give 1 to 5000 events, one JSON object per line.")
    hits = [{"line": i, "event": e} for i, e in evs if _cond(cond, sels, e)]
    return {"title": r.get("title"), "level": r.get("level"), "condition": cond, "events": len(evs), "matches": len(hits), "hits": hits[:50],
            "lesson": "A detection rule is a filter written as data. Test it against events that should match and events that should not; a rule that has never been shown a normal event will be noisy.",
            "limits": "This is a small subset of Sigma (field modifiers contains, startswith, endswith, re, all; and/or/not; '1 of x*' and 'all of x*'). It does not convert rules to a SIEM query."}


SIGMA_SAMPLE = {"rule": "title: Encoded PowerShell\nlevel: high\ndetection:\n  selection:\n    Image|endswith: '\\powershell.exe'\n    CommandLine|contains:\n      - ' -enc '\n      - ' -EncodedCommand '\n  filter:\n    ParentImage|endswith: '\\ccmexec.exe'\n  condition: selection and not filter",
                "events": '{"Image": "C:\\\\Windows\\\\System32\\\\powershell.exe", "CommandLine": "powershell -enc SQBFAFgA", "ParentImage": "C:\\\\x\\\\winword.exe"}\n{"Image": "C:\\\\Windows\\\\System32\\\\powershell.exe", "CommandLine": "powershell -enc AAAA", "ParentImage": "C:\\\\x\\\\ccmexec.exe"}\n{"Image": "C:\\\\Windows\\\\System32\\\\cmd.exe", "CommandLine": "dir"}'}

# ------------------------------------------------------------------ playbook simulator
_ACTIONS = {"notify": ("Send a message to the on-call person", False), "enrich_ip": ("Look up the address in threat intelligence", False), "open_ticket": ("Open a ticket", False),
            "block_ip": ("Add the address to the firewall block list", True), "isolate_host": ("Cut the host off the network", True), "disable_account": ("Disable the user account", True), "reset_password": ("Force a password reset", True), "collect_logs": ("Collect logs from the host", False)}
_OPS = {">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, "<": lambda a, b: a < b, "==": lambda a, b: a == b, "!=": lambda a, b: a != b, "contains": lambda a, b: str(b).lower() in str(a).lower()}
_SEV = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def _val(x: str):
    x = x.strip().strip("'\"")
    if x.lower() in _SEV:
        return _SEV[x.lower()]
    try:
        return float(x)
    except ValueError:
        return x


def playbook(rules: str, alert: str) -> dict:
    try:
        a = json.loads(alert)
    except (json.JSONDecodeError, TypeError):
        raise SecError("The alert must be one JSON object.") from None
    if not isinstance(a, dict):
        raise SecError("The alert must be one JSON object.")
    av = {k: (_SEV.get(v.lower(), v) if isinstance(v, str) and k == "severity" else v) for k, v in a.items()}
    log = []
    for ln in (rules or "").splitlines():
        ln = ln.split("#")[0].strip()
        if not ln:
            continue
        if "->" not in ln or not ln.lower().startswith("when "):
            raise SecError(f"Line '{ln}': use 'when field op value [and ...] -> action, action'.")
        cond, acts = ln[5:].split("->", 1)
        acts = [x.strip() for x in acts.split(",") if x.strip()]
        for x in acts:
            if x not in _ACTIONS:
                raise SecError(f"Unknown action '{x}'. Choose from: {', '.join(_ACTIONS)}.")
        ok, why = True, []
        for c in re.split(r"\s+and\s+", cond.strip()):
            m = re.match(r"^(\w+)\s*(>=|<=|==|!=|>|<|contains)\s*(.+)$", c.strip())
            if not m:
                raise SecError(f"Could not read the condition '{c}'. Use field op value, with op one of {', '.join(_OPS)}.")
            f, op, v = m.groups()
            have = av.get(f)
            if have is None:
                ok = False
                why.append(f"{f} is not in the alert")
                continue
            try:
                r = _OPS[op](have, _val(v)) if op == "contains" or isinstance(have, (int, float)) else _OPS[op](str(have), str(_val(v)))
            except TypeError:
                r = False
            ok = ok and r
            why.append(f"{f} {have} {op} {v.strip()} is {'true' if r else 'false'}")
        log.append({"rule": ln, "matched": ok, "checks": why, "actions": [{"action": x, "does": _ACTIONS[x][0], "needs_human_approval": _ACTIONS[x][1], "status": ("waiting for approval (not run)" if _ACTIONS[x][1] else "simulated") if ok else "skipped"} for x in acts]})
    if not log:
        raise SecError("Give at least one rule.")
    return {"alert": a, "log": log, "fired": sum(1 for r in log if r["matched"]),
            "lesson": "Automation is fast, and so are its mistakes. Let a playbook gather facts and notify freely, but put a person in front of any step that cuts off a user or a machine. This simulator runs nothing; it shows what would happen.",
            "limits": "Nothing is blocked, isolated or sent. Real orchestration tools connect to your firewall, directory and tickets."}


PLAYBOOK_SAMPLE = {"rules": "when severity >= high and category contains malware -> enrich_ip, collect_logs, isolate_host\nwhen severity >= medium -> open_ticket, notify\nwhen failed_logins > 20 -> notify, disable_account",
                   "alert": '{"severity": "high", "category": "malware beacon", "host": "WS-114", "src_ip": "203.0.113.9", "failed_logins": 0}'}

SLIPS = ["JWT guides call a token 'encrypted' or 'secure' because of its signature. A signed JWT is readable by anyone; only a JWE is encrypted.",
         "CVSS is often used as a risk score. It is a severity score for the flaw in general; risk also needs exposure, exploitability and asset value.",
         "Sigma and SOAR tutorials show automated isolation and blocking with no approval step; a wrong match then takes a real system offline.",
         "Some STRIDE examples apply every letter to every shape. Spoofing and repudiation apply to actors and processes; data flows face tampering, disclosure and denial."]
NOT_BUILT = ["Checking a certificate chain, revocation or a live site's certificate here (the Web checks tab does the live part).", "Offensive tools: exploit frameworks, password crackers, scanners against other people's systems.", "Full static analysis (Semgrep, CodeQL) or converting Sigma rules to a SIEM query.", "A real SOAR connection to firewalls or directories."]


def reference() -> dict:
    return {"samples": {"stride": STRIDE_SAMPLE, "code": CODE_SAMPLE, "sigma": SIGMA_SAMPLE, "playbook": PLAYBOOK_SAMPLE, "cvss": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}, "slips": SLIPS, "not_built": NOT_BUILT, "actions": {k: {"does": v[0], "needs_human_approval": v[1]} for k, v in _ACTIONS.items()}}
