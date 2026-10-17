"""Advanced security lab: CVSS 3.1 scoring, risk assessment (ALE and matrix), authorization and scope templates, OWASP Top 10 reference,
forensic timeline builder, IDS rule explainer, MITRE ATT&CK quick reference, and assessment checklists (HIPAA security risk analysis, SOC 2 readiness, PCI self-assessment, business continuity).
Reference and local calculation only. Nothing here scans, attacks or connects to any system. Testing a system needs the owner's written authorization first."""
from __future__ import annotations

import math
import re
from datetime import datetime

NOTE = "Reference and local calculation. Standards change: check the official source (FIRST for CVSS, OWASP, MITRE, NIST, HHS) for the current version."


class SecError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


# ------------------------------------------------------------------ CVSS 3.1 base score
_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
_AC = {"L": 0.77, "H": 0.44}
_PR_U = {"N": 0.85, "L": 0.62, "H": 0.27}
_PR_C = {"N": 0.85, "L": 0.68, "H": 0.5}
_UI = {"N": 0.85, "R": 0.62}
_CIA = {"H": 0.56, "L": 0.22, "N": 0.0}
NAMES = {"AV": {"N": "Network", "A": "Adjacent", "L": "Local", "P": "Physical"}, "AC": {"L": "Low", "H": "High"}, "PR": {"N": "None", "L": "Low", "H": "High"}, "UI": {"N": "None", "R": "Required"},
         "S": {"U": "Unchanged", "C": "Changed"}, "C": {"H": "High", "L": "Low", "N": "None"}, "I": {"H": "High", "L": "Low", "N": "None"}, "A": {"H": "High", "L": "Low", "N": "None"}}


def _roundup(x: float) -> float:
    i = round(x * 100000)
    return i / 100000.0 if i % 10000 == 0 else (math.floor(i / 10000) + 1) / 10.0


def cvss(vector: str = "", **m) -> dict:
    if vector:
        parts = dict(p.split(":", 1) for p in vector.replace("CVSS:3.1/", "").replace("CVSS:3.0/", "").split("/") if ":" in p)
    else:
        parts = {k: str(v).upper() for k, v in m.items()}
    try:
        av, ac, pr, ui, sc = parts["AV"], parts["AC"], parts["PR"], parts["UI"], parts["S"]
        c, i, a = parts["C"], parts["I"], parts["A"]
        for k, v in (("AV", av), ("AC", ac), ("PR", pr), ("UI", ui), ("S", sc), ("C", c), ("I", i), ("A", a)):
            if v not in NAMES[k]:
                raise KeyError(k)
    except KeyError as e:
        raise SecError(f"Check the vector: a value for {e.args[0]} is missing or not valid. Example: AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") from None
    iss = 1 - (1 - _CIA[c]) * (1 - _CIA[i]) * (1 - _CIA[a])
    changed = sc == "C"
    impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15 if changed else 6.42 * iss
    expl = 8.22 * _AV[av] * _AC[ac] * (_PR_C if changed else _PR_U)[pr] * _UI[ui]
    score = 0.0 if impact <= 0 else _roundup(min((1.08 if changed else 1.0) * (impact + expl), 10))
    sev = "None" if score == 0 else "Low" if score < 4 else "Medium" if score < 7 else "High" if score < 9 else "Critical"
    vec = f"CVSS:3.1/AV:{av}/AC:{ac}/PR:{pr}/UI:{ui}/S:{sc}/C:{c}/I:{i}/A:{a}"
    return {"vector": vec, "score": score, "severity": sev, "exploitability": round(expl, 1), "impact": round(impact, 1), "plain": {k: NAMES[k][parts[k]] for k in NAMES},
            "triage": {"Critical": "Fix or mitigate within days. If it is exploited in the wild, treat as an emergency.", "High": "Fix within about 2 weeks, sooner if exposed to the internet.", "Medium": "Schedule within a month or two, bundled with routine patching.",
                       "Low": "Fix when convenient, or accept the risk and document it.", "None": "No impact scored."}[sev],
            "caveat": "The base score measures the flaw, not your risk. Raise or lower priority by exposure (internet facing?), data value, exploit availability and whether you have other protections.", "note": NOTE}


# ------------------------------------------------------------------ risk
def ale(asset_value, exposure_pct, incidents_per_year, control_cost_per_year=0.0, risk_reduction_pct=0.0) -> dict:
    try:
        v, e, r, cc, rr = float(asset_value), float(exposure_pct), float(incidents_per_year), float(control_cost_per_year or 0), float(risk_reduction_pct or 0)
    except (TypeError, ValueError):
        raise SecError("All values must be numbers.") from None
    if v <= 0 or not 0 < e <= 100 or r < 0 or not 0 <= rr <= 100 or cc < 0:
        raise SecError("Value must be above 0, exposure from 1 to 100 percent, incidents 0 or more, reduction 0 to 100 percent.")
    sle = v * e / 100
    base = sle * r
    after = base * (1 - rr / 100)
    saving = base - after
    return {"single_loss": round(sle, 2), "annual_loss_expectancy": round(base, 2), "ale_after_control": round(after, 2), "annual_saving": round(saving, 2), "control_cost_per_year": cc,
            "net_benefit_per_year": round(saving - cc, 2), "worth_it": saving > cc,
            "how": "Single loss = value x exposure. Annual loss = single loss x incidents per year. A control is worth it when the yearly loss it prevents is more than its yearly cost. The inputs are estimates: state your assumptions and give ranges to the client.", "note": NOTE}


LEVELS = {"rare": 1, "unlikely": 2, "possible": 3, "likely": 4, "almost certain": 5}
IMPACTS = {"minor": 1, "moderate": 2, "significant": 3, "major": 4, "severe": 5}


def risk_matrix(likelihood: str, impact: str) -> dict:
    l, i = LEVELS.get((likelihood or "").lower().strip()), IMPACTS.get((impact or "").lower().strip())
    if not l or not i:
        raise SecError("Likelihood: " + ", ".join(LEVELS) + ". Impact: " + ", ".join(IMPACTS) + ".")
    s = l * i
    lvl = "Low" if s <= 4 else "Medium" if s <= 9 else "High" if s <= 16 else "Extreme"
    return {"score": s, "level": lvl, "treat": {"Low": "Accept or monitor.", "Medium": "Reduce with reasonable controls; review regularly.", "High": "Reduce soon: assign an owner and a date.", "Extreme": "Act now: reduce, avoid or transfer the risk before continuing."}[lvl],
            "options": ["Reduce (add controls)", "Avoid (stop the activity)", "Transfer (insurance or contract)", "Accept (a written decision by the owner)"], "note": NOTE}


REGISTER_TEMPLATE = """RISK REGISTER
ID | Risk (what could happen) | Asset | Likelihood | Impact | Score | Treatment | Owner | Due | Status
1  |                          |       |            |        |       |           |       |     |
Method: likelihood x impact on a 1-5 scale. Review monthly. Record accepted risks with the owner's name and date.
"""

# ------------------------------------------------------------------ authorization and scope
def scope(client: str = "", systems: str = "", start: str = "", end: str = "", testing: str = "", exclusions: str = "") -> dict:
    cl = (client or "[client name]").strip()[:80]
    text = f"""PENETRATION TEST AUTHORIZATION AND SCOPE (template, have a lawyer review before use)
Client (system owner): {cl}
Tester: [your name or business]
Testing window: {start or '[start date and time]'} to {end or '[end date and time]'} (Pacific time)
Systems in scope (exact IPs, hostnames, apps, accounts):
{systems or '[list each one]'}
Testing allowed:
{testing or '[for example: external scan, authenticated web app testing, phishing simulation with approval]'}
Out of scope and not allowed:
{exclusions or '[for example: denial of service, production data deletion, social engineering of staff not named, third-party systems, anything not listed above]'}
Rules: stop and notify immediately if sensitive data (health, financial, personal) is reached or a system fails. Do not copy or keep client data beyond what is needed as evidence. Use only the agreed tools and accounts.
Contacts: client emergency contact [name, phone], tester [phone].
Data handling: findings reports shared only with [names]. Evidence stored encrypted and destroyed on [date].
Authorization: I confirm I own or am authorized to approve testing of the systems above.
Signed (client): ______________ Date: ______   Signed (tester): ______________ Date: ______
"""
    return {"text": text, "checks": ["Written, signed authorization exists before ANY testing, even a scan.", "The signer really owns the systems (cloud and hosting providers have their own testing rules).", "Scope lists exact targets, not 'the network'.",
                                     "Third-party systems (email host, payment processor) are excluded unless the provider approves.", "Both sides have emergency contacts for the window.", "Ask a lawyer to review the agreement and confirm your insurance covers this work."],
            "warning": "Unauthorized access to computers is illegal (see CFAA in Settings, Legal and compliance). This tool never tests anything. Practice only on your own lab or intentionally vulnerable practice systems.", "note": NOTE}


OWASP = [
    {"id": "A01", "name": "Broken access control", "what": "Users can reach data or actions they should not.", "test": "Change IDs in URLs, try admin pages as a normal user, check API permissions per object.", "fix": "Check permission on the server for every request, deny by default, use object-level checks."},
    {"id": "A02", "name": "Security misconfiguration", "what": "Default accounts, open storage, verbose errors, missing headers.", "test": "Review settings, scan for default credentials in a lab, look at error pages and headers.", "fix": "Harden by baseline, remove defaults, automate and review configuration."},
    {"id": "A03", "name": "Software supply chain failures", "what": "Vulnerable or malicious dependencies, builds and updates.", "test": "List dependencies and versions, check for known vulnerabilities, review the build pipeline access.", "fix": "Pin and scan dependencies, verify sources, restrict pipeline credentials, keep an inventory (SBOM)."},
    {"id": "A04", "name": "Cryptographic failures", "what": "Sensitive data exposed by weak or missing encryption.", "test": "Check HTTPS everywhere, old protocols, how passwords are stored.", "fix": "Use TLS, modern algorithms, strong password hashing (Argon2, bcrypt), and protect keys."},
    {"id": "A05", "name": "Injection", "what": "Untrusted input is run as a command or query (SQL, command, script).", "test": "In a lab, try quote characters and script tags in inputs and watch for errors or echoed code.", "fix": "Parameterized queries, input validation, output encoding, least privilege for the database account."},
    {"id": "A06", "name": "Insecure design", "what": "The design itself lacks protection (no rate limits, trusting the client).", "test": "Threat model the flow: what can an abuser do repeatedly or out of order?", "fix": "Threat modeling early, abuse cases, rate limits, secure design patterns."},
    {"id": "A07", "name": "Authentication failures", "what": "Weak login, session or recovery process.", "test": "Check password rules, lockout, multi-factor, session expiry, password reset flow.", "fix": "Multi-factor, rate limiting, secure session handling, safe recovery."},
    {"id": "A08", "name": "Software or data integrity failures", "what": "Code or data accepted without verifying it was not altered.", "test": "Check update and plugin sources, signatures, and unsafe deserialization.", "fix": "Sign and verify updates, avoid unsafe deserialization, protect the pipeline."},
    {"id": "A09", "name": "Logging and alerting failures", "what": "Attacks go unseen because nothing is logged or watched.", "test": "Fail a login on purpose in a lab: is it logged and does anyone see it?", "fix": "Log important events without secrets, centralize, alert on abuse, test the response."},
    {"id": "A10", "name": "Mishandling of exceptional conditions", "what": "Errors and edge cases leak data or fail open.", "test": "Send unexpected input and break flows: does it fail safely and hide details?", "fix": "Fail closed, handle errors centrally, show generic messages, log the details privately."},
]
OWASP_NOTE = "Based on the OWASP Top 10 (2025 edition lists these categories). Check owasp.org for the current list and the testing guide."

ATTACK = [
    {"tactic": "Initial access", "ex": "Phishing, exposed remote desktop, stolen credentials, vulnerable public app", "defend": "Email filtering, MFA, patching, closing exposed services"},
    {"tactic": "Execution", "ex": "Malicious macros, PowerShell, scripts", "defend": "Block macros from the internet, constrain PowerShell, allowlisting"},
    {"tactic": "Persistence", "ex": "Scheduled tasks, startup items, new accounts", "defend": "Monitor new accounts and tasks, audit startup items"},
    {"tactic": "Privilege escalation", "ex": "Local exploits, misconfigured services, stolen admin tokens", "defend": "Least privilege, separate admin accounts, patching"},
    {"tactic": "Defense evasion", "ex": "Disabling antivirus, clearing logs", "defend": "Tamper protection, forward logs off the machine"},
    {"tactic": "Credential access", "ex": "Password spraying, keyloggers, dumping memory", "defend": "MFA, lockout policy, credential guard, password manager"},
    {"tactic": "Discovery and lateral movement", "ex": "Network scans, remote services, shared admin passwords", "defend": "Segmentation, unique local admin passwords, restrict remote access"},
    {"tactic": "Collection and exfiltration", "ex": "Archiving files, uploading to cloud storage", "defend": "Data loss prevention, egress monitoring, access reviews"},
    {"tactic": "Impact", "ex": "Ransomware, data destruction, service denial", "defend": "Offline backups, tested recovery, network isolation"},
]


def timeline(text: str, year: int = 2026) -> dict:
    """Sort pasted log lines by time. Understands ISO style (2026-10-16 14:03:22 or 2026-10-16T14:03:22) and syslog style (Oct 16 14:03:22)."""
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    if len(lines) < 2:
        raise SecError("Paste at least two log lines with timestamps.")
    if len(lines) > 3000:
        raise SecError("Keep it under 3,000 lines.")
    rows, skipped = [], 0
    for ln in lines:
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})", ln)
        t = None
        try:
            if m:
                t = datetime(*map(int, m.groups()))
            else:
                m2 = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})", ln)
                if m2:
                    t = datetime.strptime(f"{year} {m2.group(1)} {m2.group(2)} {m2.group(3)}:{m2.group(4)}:{m2.group(5)}", "%Y %b %d %H:%M:%S")
        except ValueError:
            t = None
        if t:
            rows.append((t, ln.strip()[:200]))
        else:
            skipped += 1
    if len(rows) < 2:
        raise SecError("Could not read timestamps. Use 2026-10-16 14:03:22 or Oct 16 14:03:22 formats.")
    rows.sort(key=lambda r: r[0])
    out, prev, big = [], None, []
    for t, ln in rows[:500]:
        gap = (t - prev).total_seconds() if prev else 0
        out.append({"time": t.isoformat(sep=" "), "gap_s": int(gap), "line": ln})
        if gap >= 3600:
            big.append(f"{int(gap // 60)} minutes of silence before {t.isoformat(sep=' ')}")
        prev = t
    span = (rows[-1][0] - rows[0][0]).total_seconds()
    return {"events": out, "count": len(rows), "skipped_lines": skipped, "span_minutes": round(span / 60, 1), "gaps": big[:10],
            "reminders": ["Work on copies of logs, never the originals.", "Record who collected each log, when, and how (chain of custody).", "Check the clocks: different devices may be minutes apart. Note the offset.", "Timelines show what happened and when: do not guess who did it from a log alone."], "note": NOTE}


_RULE_KEYS = {"msg": "Alert text shown to the analyst", "sid": "Unique rule ID", "rev": "Rule revision", "content": "Looks for this text or bytes in the traffic", "flow": "Direction and connection state", "classtype": "Category of the attack",
              "threshold": "Limits how often it alerts", "pcre": "A pattern (regular expression) match", "http.uri": "Searches the web request address", "http.method": "Searches the web request method", "nocase": "Ignore upper and lower case", "reference": "Link to more information", "dsize": "Packet payload size test"}


def explain_rule(rule: str) -> dict:
    r = (rule or "").strip()
    m = re.match(r"^(alert|drop|reject|pass|log)\s+(\w+)\s+(\S+)\s+(\S+)\s+(->|<>)\s+(\S+)\s+(\S+)\s*\((.*)\)\s*$", r, re.S)
    if not m:
        raise SecError("Paste one Suricata or Snort rule, like: alert tcp $HOME_NET any -> $EXTERNAL_NET 443 (msg:\"Example\"; sid:1000001; rev:1;)")
    act, proto, src, sp, arrow, dst, dp, opts = m.groups()
    options = []
    for part in re.split(r";\s*(?=(?:[a-zA-Z_.]+)\s*(?::|;|$))", opts.strip().rstrip(";")):
        if not part.strip():
            continue
        k, _, v = part.partition(":")
        k = k.strip()
        options.append({"keyword": k, "value": v.strip().strip('"')[:120], "means": _RULE_KEYS.get(k, "Rule option (check the Suricata docs)")})
    verdict = {"alert": "Raises an alert only.", "drop": "Blocks the packet (in IPS mode) and alerts.", "reject": "Blocks and sends a reset.", "pass": "Ignores matching traffic.", "log": "Logs the packet."}[act]
    warn = []
    if sp == "any" and dp == "any" and src == "any" and dst == "any":
        warn.append("Matches all traffic: likely noisy.")
    if not any(o["keyword"] == "sid" for o in options):
        warn.append("No sid: rules need a unique ID.")
    if not any(o["keyword"] == "content" or o["keyword"] == "pcre" for o in options) and proto in ("tcp", "udp", "http"):
        warn.append("No content or pattern match: it may alert too often.")
    return {"summary": f"{act.upper()} {proto.upper()} from {src}:{sp} {arrow} {dst}:{dp}. {verdict}", "action": act, "protocol": proto, "options": options, "warnings": warn, "tuning": ["Test new rules in alert-only mode first.", "Read a few hits to check for false positives.", "Use thresholds to avoid floods."], "note": NOTE}


def checklist(kind: str) -> dict:
    items = CHECKLISTS.get((kind or "").lower())
    if not items:
        raise SecError("Choose one of: " + ", ".join(CHECKLISTS) + ".")
    return {"kind": kind, "title": items["title"], "sections": items["sections"], "caveat": items["caveat"], "note": NOTE}


CHECKLISTS = {
    "hipaa": {"title": "HIPAA security risk analysis starter (for a small practice or its contractor)", "caveat": "This is a starter list for gathering information. A formal HIPAA risk analysis has specific required elements: use HHS guidance and the client's compliance lead, and do not tell a client they are 'HIPAA compliant'.",
              "sections": [{"h": "Scope", "items": ["List every system, device, app and vendor that creates, stores or sends patient information.", "Record where patient data lives (EHR, email, scans, backups, phones, paper).", "Identify who has access and why."]},
                           {"h": "Administrative safeguards", "items": ["Named security officer and written policies.", "Workforce training and sanctions policy.", "Access approval and removal when staff leave.", "Business associate agreements with each vendor that touches patient data.", "Incident and breach response plan, and a tested contact list."]},
                           {"h": "Physical safeguards", "items": ["Locked server and network areas, screens not visible to the public.", "Device and media inventory with secure disposal (wipe or destroy).", "Workstation and laptop protection."]},
                           {"h": "Technical safeguards", "items": ["Unique user IDs, strong passwords with multi-factor.", "Automatic logoff and access logging.", "Encryption of laptops, phones and backups; encrypted email for patient data.", "Patching, anti-malware and a tested, off-site backup.", "Network segmentation, firewall, secure Wi-Fi."]},
                           {"h": "Risk rating", "items": ["For each gap, rate likelihood and impact and write the fix, owner and date.", "Keep the analysis and update it at least yearly and after big changes."]}]},
    "soc2": {"title": "SOC 2 readiness starter", "caveat": "SOC 2 is an audit by a licensed CPA firm. This list only helps a small company prepare.",
             "sections": [{"h": "Security (common criteria)", "items": ["Written security policies approved by management.", "Risk assessment performed and tracked.", "Access control, MFA, and quarterly access reviews.", "Change management with approvals and testing.", "Vulnerability scanning and patching.", "Logging, monitoring and incident response with a tested plan.", "Vendor management and security reviews.", "Employee onboarding, training and offboarding evidence."]},
                          {"h": "Evidence habits", "items": ["Keep screenshots and exports with dates.", "Track who approved each change.", "Keep a list of systems and data flows."]}]},
    "pci": {"title": "PCI DSS small merchant starter (card payments)", "caveat": "Which questionnaire applies depends on how the merchant takes cards. Use the processor's guidance and the PCI Security Standards Council site.",
            "sections": [{"h": "Reduce scope", "items": ["Use a hosted payment page or terminal so card numbers never touch your systems.", "Never store card verification codes or full magnetic stripe data."]},
                         {"h": "Basics", "items": ["Firewall and secure network, no default passwords.", "Patching and anti-malware.", "Restrict who can access payment systems and use unique logins with MFA.", "Log and review access.", "Written security policy and staff training.", "Quarterly external vulnerability scans if required by the questionnaire."]}]},
    "continuity": {"title": "Business continuity and disaster recovery starter", "caveat": "Plans only work if they are tested. Test a restore and a call tree at least yearly.",
                   "sections": [{"h": "Know what matters", "items": ["List critical systems and how long the business can be without each (RTO) and how much data it can lose (RPO).", "Identify key people and vendors and their contact details offline."]},
                                {"h": "Protect", "items": ["3-2-1 backups: three copies, two media types, one off-site and one offline or immutable.", "Document how to restore, in order.", "Power protection and a second internet option for critical offices."]},
                                {"h": "Respond and test", "items": ["Write simple runbooks for outage, ransomware and lost building.", "Run a tabletop exercise and a real restore test, then fix what failed.", "Review after any incident."]}]},
}


def reference() -> dict:
    return {"owasp": OWASP, "owasp_note": OWASP_NOTE, "attack": ATTACK, "register": REGISTER_TEMPLATE, "checklists": {k: v["title"] for k, v in CHECKLISTS.items()}, "note": NOTE}
