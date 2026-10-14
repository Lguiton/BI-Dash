"""Security checkup report: one client-ready page that pulls the dashboard's defensive checks together and says what to fix first.

Inputs are things you already collected with the other Cybersecurity tools: the output of the read-only Windows script (one block per PC), public website
addresses (headers and certificate), a log you paste, and a short checklist of what only a person can see (2FA, backups, Wi-Fi). It scans nothing new on its own.
The rating is a band (needs attention now, fair, good), not a score, because a precise-looking number would claim more than these checks can know.
Every report states what was and was NOT checked. In Practice it is stamped SAMPLE."""
from __future__ import annotations

import html
from datetime import date

from app.services import endpoint_audit, sec_fixes, seclogs, security, workspaces

LEVELS = ("high", "medium", "low")
ANS = ("yes", "partial", "no", "unknown")

# id, title, severity if not in place, why it matters, the usual fix
CHECKLIST = [
    ("mfa_email", "Two-step sign-in on the owner's email", "high", "Whoever controls the email can reset every other password.", "Turn on an authenticator app (not text messages) for the email account."),
    ("mfa_money", "Two-step sign-in on bank, payment and accounting accounts", "high", "These are the accounts a thief wants first.", "Turn on app-based 2FA on each and save the recovery codes offline."),
    ("password_manager", "A password manager, with different passwords everywhere", "medium", "Reused passwords turn one leak into many break-ins.", "Set up a password manager and change the reused passwords starting with email and money."),
    ("backups_exist", "Business data is backed up automatically", "high", "Ransomware and failures are survivable only with a good backup.", "Back up to a second place on a schedule."),
    ("backups_tested", "A backup has been restored as a test", "medium", "An untested backup is a hope, not a plan.", "Restore one file or folder from the backup this month."),
    ("backups_offsite", "One backup copy is off-site or offline", "medium", "A backup that is always connected can be encrypted along with the PC.", "Keep a copy in the cloud or on a drive that is unplugged."),
    ("updates", "Windows and apps update automatically", "medium", "Most break-ins use holes that already have a fix.", "Turn on automatic updates and restart weekly."),
    ("antivirus", "Antivirus is on and up to date on every PC", "medium", "It stops common malware before it runs.", "Use Microsoft Defender or a trusted product, and check it is on."),
    ("disk_encryption", "Laptops have disk encryption (BitLocker or similar)", "medium", "A lost laptop should not mean lost customer data.", "Turn on BitLocker and keep the recovery key somewhere safe."),
    ("router_password", "The router's admin password and Wi-Fi password were changed from the defaults", "high", "Default passwords are public.", "Change both and turn off remote administration."),
    ("guest_wifi", "Guests and smart devices are on a separate Wi-Fi", "low", "Keeps a cheap camera or a visitor's phone away from business PCs.", "Turn on the guest network and move the devices to it."),
    ("standard_accounts", "Daily work is done on a standard account, not an administrator", "medium", "Malware that runs as admin can do much more damage.", "Make a separate admin account and use a standard one every day."),
    ("training", "Staff know how to spot phishing and who to tell", "low", "Most attacks start with one convincing email.", "Run a short awareness session and agree who to call."),
    ("incident_plan", "There is a written plan for 'we think we were hacked'", "medium", "Panic wastes the first hour, which matters most.", "Write a one-page plan with contacts and first steps."),
]
CL = {c[0]: c for c in CHECKLIST}
NOT_CHECKED = ["Anything on a computer you did not run the script on, and anything the script does not read.", "Malware: this is not an antivirus scan and can't see hidden malware.",
               "Your network from the inside, or other people's systems. Nothing was scanned or attacked.", "Compliance (HIPAA, PCI and similar): this is a readiness view, not an audit.",
               "Changes made since the checks were run."]


class ReportError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _sev_from_n(n: int) -> str:
    return "high" if n >= 3 else "medium" if n == 2 else "low"


def _down(s: str) -> str:
    return {"high": "medium", "medium": "low"}.get(s, "low")


def _endpoint(blocks: list[dict]) -> tuple[list[dict], list[dict]]:
    sections, items = [], []
    for b in blocks[:10]:
        label = str(b.get("label") or "PC")[:60]
        try:
            g = endpoint_audit.grade(str(b.get("text") or ""))
        except endpoint_audit.EndpointError as e:
            sections.append({"label": label, "error": e.message})
            continue
        sections.append({"label": label, "counts": g["counts"], "rows": [r for r in g["rows"] if r["status"] in ("fail", "warn")], "passed": g["counts"]["pass"]})
        for r in g["rows"]:
            if r["status"] in ("fail", "warn"):
                sev = _sev_from_n(r["severity"])
                items.append({"source": f"Windows PC: {label}", "severity": sev if r["status"] == "fail" else _down(sev), "title": r["title"], "why": r["why"], "fix": r["fix"], "ref": r["id"]})
    return sections, items


def _web(hosts: list[str]) -> tuple[list[dict], list[dict]]:
    sections, items = [], []
    for h in [str(x).strip() for x in hosts if str(x).strip()][:5]:
        sec = {"host": h}
        for kind, fn in (("headers", security.check_headers), ("cert", security.check_cert)):
            try:
                r = fn(h)
            except (security.SecError, ValueError) as e:
                sec[kind] = {"error": str(e)}
                continue
            sec["host"] = r.get("host", h)
            if r.get("error"):
                sec[kind] = {"error": r["error"]}
            else:
                sec[kind] = {"pct": r["score"]["pct"], "passed": r["score"]["passed"], "total": r["score"]["total"]}
            for f in r.get("findings", []):
                if f["level"] in ("warn", "fail"):
                    cert_bad = kind == "cert" and f["level"] == "fail"
                    items.append({"source": f"Website: {sec['host']}", "severity": "high" if cert_bad else "medium" if f["level"] == "fail" else "low", "title": f["title"], "why": f.get("detail") or ("Part of the website's basic protection." if kind == "headers" else "Visitors' browsers warn or refuse when the certificate is wrong."), "fix": f.get("fix") or "See the website check for details.", "ref": f.get("id", "")})
        sections.append(sec)
    return sections, items


def _logs(text: str) -> tuple[dict | None, list[dict]]:
    if not (text or "").strip():
        return None, []
    try:
        a = seclogs.analyze(text)
    except ValueError as e:
        return {"error": str(e)}, []
    items = [{"source": "Logs", "severity": "high" if f["severity"] in ("critical", "high") else "medium" if f["severity"] == "medium" else "low", "title": f["title"], "why": f.get("detail", ""), "fix": f.get("advice", ""), "ref": f["id"]} for f in a["findings"][:15]]
    return {"events": a["info"].get("events") if isinstance(a["info"], dict) else None, "range": a["range"], "findings": len(a["findings"])}, items


def _manual(answers: dict) -> tuple[dict, list[dict]]:
    items, tally = [], {"yes": 0, "partial": 0, "no": 0, "unknown": 0}
    for cid, title, sev, why, fix in CHECKLIST:
        a = str((answers or {}).get(cid) or "unknown").lower()
        if a not in ANS:
            raise ReportError(f"'{a}' isn't a valid answer for {cid}. Use yes, partial, no or unknown.")
        tally[a] += 1
        if a == "no":
            items.append({"source": "Checklist", "severity": sev, "title": f"Not in place: {title}", "why": why, "fix": fix, "ref": cid})
        elif a == "partial":
            items.append({"source": "Checklist", "severity": _down(sev), "title": f"Only partly in place: {title}", "why": why, "fix": fix, "ref": cid})
    return tally, items


def build(client: str = "", prepared_by: str = "", scope: str = "", endpoints: list[dict] | None = None, hosts: list[str] | None = None, logs: str = "", checklist: dict | None = None) -> dict:
    ep_sec, ep_items = _endpoint(endpoints or [])
    web_sec, web_items = _web(hosts or [])
    log_sec, log_items = _logs(logs)
    tally, man_items = _manual(checklist or {})
    used = bool(endpoints) + bool(hosts) + bool(logs and logs.strip()) + (tally["unknown"] < len(CHECKLIST))
    if not used:
        raise ReportError("Add at least one input: PC script output, a website, a log, or some checklist answers.")
    items = ep_items + web_items + log_items + man_items
    for i in items:
        i["fix_id"] = sec_fixes.for_ref(i.get("ref", ""), i["title"])
    order = {s: i for i, s in enumerate(LEVELS)}
    items.sort(key=lambda x: order[x["severity"]])
    counts = {s: sum(1 for i in items if i["severity"] == s) for s in LEVELS}
    band = "Needs attention now" if counts["high"] else "Fair, with things to tidy" if counts["medium"] else "Good on what was checked"
    checked = [x for x in (f"{len(ep_sec)} Windows PC(s)" if ep_sec else "", f"{len(web_sec)} website(s)" if web_sec else "", "a log file" if log_sec else "", f"{len(CHECKLIST) - tally['unknown']} checklist answer(s)" if tally["unknown"] < len(CHECKLIST) else "") if x]
    sample = workspaces.active() != "real"
    return {"client": (client or "")[:80], "prepared_by": (prepared_by or "")[:80], "scope": (scope or "")[:400], "generated": date.today().isoformat(), "sample": sample, "band": band, "counts": counts,
            "start_with": items[:5], "items": items, "endpoints": ep_sec, "websites": web_sec, "logs": log_sec, "checklist": tally, "checked": checked, "not_checked": NOT_CHECKED,
            "caveat": "This is a point-in-time view built from the checks listed above. A good result does not mean the business is safe, and a finding is a lead to confirm before you change anything."}


def to_html(r: dict) -> str:
    e = html.escape
    tone = {"high": "#b3261e", "medium": "#a15c00", "low": "#555"}
    banner = "<p class=sample>SAMPLE: made in the Practice workspace, not a client deliverable.</p>" if r["sample"] else ""
    who = " · ".join(x for x in (f"For {e(r['client'])}" if r["client"] else "", f"Prepared by {e(r['prepared_by'])}" if r["prepared_by"] else "", e(r["generated"])) if x)
    first = "".join(f"<li><b>{e(i['title'])}</b> <span class=src>({e(i['source'])})</span><br>{e(i['fix'])}</li>" for i in r["start_with"]) or "<li>Nothing urgent was found in what was checked.</li>"
    rows = "".join(f"<tr><td style='color:{tone[i['severity']]};font-weight:600'>{e(i['severity'])}</td><td>{e(i['title'])}<br><span class=src>{e(i['source'])}</span></td><td>{e(i['why'])}</td><td>{e(i['fix'])}</td></tr>" for i in r["items"])
    pcs = "".join(f"<li>{e(p['label'])}: " + (e(p["error"]) if p.get("error") else f"{p['passed']} passed, {p['counts']['warn']} to improve, {p['counts']['fail']} to fix") + "</li>" for p in r["endpoints"])
    webs = "".join(f"<li>{e(w['host'])}: " + "; ".join(f"{k} " + (e(v["error"]) if v.get("error") else f"{v['passed']} of {v['total']} checks OK") for k, v in w.items() if k in ("headers", "cert")) + "</li>" for w in r["websites"])
    lg = ""
    if r["logs"]:
        lg = f"<li>Log file: {e(r['logs']['error'])}</li>" if r["logs"].get("error") else f"<li>Log file: {r['logs']['findings']} thing(s) worth a look</li>"
    ck = r["checklist"]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Security checkup</title>
<style>body{{font:15px/1.5 system-ui,Segoe UI,Arial,sans-serif;max-width:860px;margin:2rem auto;padding:0 1rem;color:#1b1f1d}}h2{{margin-top:1.6rem;border-bottom:2px solid #0f6b4a;padding-bottom:.2rem}}
table{{border-collapse:collapse;width:100%;font-size:.9rem}}td,th{{padding:.4rem .5rem;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}}.src{{color:#666;font-size:.8rem}}.sample{{background:#fff3cd;border:1px solid #e0b000;padding:.5rem;font-weight:600}}
.band{{font-size:1.3rem;font-weight:700}}.cav{{color:#555;font-size:.85rem;margin-top:2rem}}@media print{{body{{margin:0}}}}</style></head><body>{banner}
<h1>Security checkup</h1><p class=src>{who}</p>{('<p>' + e(r['scope']) + '</p>') if r['scope'] else ''}
<p class=band>Overall: {e(r['band'])}</p><p>{r['counts']['high']} to fix first, {r['counts']['medium']} to plan, {r['counts']['low']} to tidy when convenient.</p>
<h2>Start with these</h2><ol>{first}</ol>
<h2>What was checked</h2><ul>{pcs}{webs}{lg}<li>Checklist: {ck['yes']} in place, {ck['partial']} partly, {ck['no']} not in place, {ck['unknown']} not asked</li></ul>
<h2>All findings</h2>{('<table><tr><th>Priority</th><th>Finding</th><th>Why it matters</th><th>Suggested fix</th></tr>' + rows + '</table>') if rows else '<p>No findings.</p>'}
<h2>What this did not check</h2><ul>{''.join(f'<li>{e(x)}</li>' for x in r['not_checked'])}</ul><p class=cav>{e(r['caveat'])}</p></body></html>"""
