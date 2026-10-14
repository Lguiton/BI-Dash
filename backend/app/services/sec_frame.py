"""Security frameworks lab: the five principles (and the anti-principle), a CIA classifier and a NIST CSF self-check.
Pure functions over text and answers you give. Nothing is scanned or contacted."""
from __future__ import annotations

import re


class FrameError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


PRINCIPLES = [
    {"id": "depth", "name": "Defense in depth", "meaning": "Several different layers, so one failure does not open everything. Each layer assumes the one before it failed.",
     "example": "Firewall, then network segments, then MFA, then least-privilege accounts, then encryption, then backups and monitoring.",
     "red_flag": "One control (usually the firewall) carries the whole design.", "ask": "If this control fails tonight, what stops the attacker next?"},
    {"id": "least", "name": "Least privilege", "meaning": "Only the access needed, for only as long as needed. Review it so it does not creep upward.",
     "example": "A helpdesk role can reset passwords but not read mailboxes; admin rights are requested for a task and expire.",
     "red_flag": "Everyone is a local admin 'to avoid tickets'; access is never removed after a role change.", "ask": "What is the least this account needs to do its job?"},
    {"id": "sod", "name": "Separation of duties", "meaning": "No single person controls a whole sensitive process. The one who requests is not the one who approves.",
     "example": "One person raises a payment, another approves it; code is merged only after someone else reviews it.",
     "red_flag": "The same account requests, approves and audits.", "ask": "Can one person complete this process alone, and who would notice?"},
    {"id": "design", "name": "Security by design", "meaning": "Security is in the requirements and the design from the start, and the default settings are the safe ones.",
     "example": "Threat-model the feature before building it; ship with secure defaults rather than a hardening guide.",
     "red_flag": "'We will add security before launch'.", "ask": "Which requirement here is a security requirement, and who signed it off?"},
    {"id": "kiss", "name": "Keep it simple (KISS)", "meaning": "Complexity hides mistakes and wears out the people who run it. Prefer the simple design that meets the need.",
     "example": "One central identity system instead of five separate password stores.",
     "red_flag": "Rules nobody can explain; exceptions on top of exceptions.", "ask": "Could a new team member explain and operate this in a day?"},
    {"id": "obscurity", "name": "Security by obscurity (the anti-principle)", "meaning": "Relying on the design being secret. Secrecy of the design is not security. Kerckhoffs's principle: a cryptosystem should stay secure even if everything except the key is public.",
     "example": "Hiding an admin page at an odd URL is not access control; an attacker only has to find it once.",
     "red_flag": "'Nobody knows our port number' or a home-made cipher.", "ask": "If the attacker knew exactly how this works, would it still hold?"},
]

# (principle id, regex, finding, fix)
_RULES = [
    ("obscurity", r"\b(hidden|secret)\s+(url|page|port|path|admin)|nobody (knows|will find)|security (through|by) obscurity|custom (cipher|encryption)|our own (cipher|encryption)|rolled our own|non-?standard port (so|to) ",
     "Relies on something staying secret about the design.", "Add real access control (authentication, authorisation) and use a standard, reviewed cipher. A changed port only cuts log noise."),
    ("least", r"\b(everyone|all (users|staff|employees)|domain users)\b[^.\n]{0,40}\b(admin|administrator|root|full (control|access))|\bshared (admin|root) (account|password)|\bpermanent admin|\bfull access (for|to) (all|everyone)|chmod\s+-?R?\s*777|\bnever (review|remove)",
     "Access broader or longer-lived than the job needs.", "Give roles only the rights they need, use time-boxed elevation and review access when people change roles."),
    ("sod", r"\b(same (person|user|account|admin)|one (person|admin|account))\b[^.\n]{0,50}\b(requests?|raises?|creates?|writes?)\b[^.\n]{0,50}\b(approv\w+|reviews?|merges?|signs?)|\bself[- ]approv\w+|\bapprov\w+ (their|his|her) own|\bno (second|other) (approver|reviewer|person)",
     "One person controls a whole sensitive process.", "Split request, approval and audit between different people or accounts; require a second reviewer."),
    ("depth", r"\b(only|just|relies? on|rely on)\s+(a |the |our )?(firewall|antivirus|perimeter|password)|\bsingle (layer|control|point of defen[cs]e)|\bwe (are|re) behind (a |the )?firewall so",
     "A single control is carrying the whole design.", "Add independent layers: segmentation, MFA, patching, least privilege, encryption, logging and backups."),
    ("design", r"\bsecurity (will|can) (be )?(add\w*|bolt\w*|handled?) (later|after|before launch|at the end)|\bwe(['’]ll| will) (add|do) security (later|after|before launch)|\bdefault (admin )?password (is )?(unchanged|left)|\bshipped? with (the )?default (password|credentials)",
     "Security is treated as a later step, or defaults are unsafe.", "Put security requirements in the design, threat-model first, and ship secure defaults."),
    ("kiss", r"\b(complicated|convoluted|byzantine|nobody understands)\b[^.\n]{0,40}\b(rules?|policy|policies|firewall|config|setup)|\b(hundreds|thousands) of (firewall )?rules|\bexceptions? (on top of|for) exceptions?|\bfive (different )?(password|identity|login) (stores?|systems?)",
     "Complexity that people cannot reason about.", "Consolidate and simplify; remove rules nobody can justify; write down why each remains."),
]


def review(text: str) -> dict:
    t = (text or "").strip()
    if len(t) < 15:
        raise FrameError("Describe the design, policy or setup in a sentence or two (at least 15 characters).")
    if len(t) > 20_000:
        raise FrameError("Keep it under 20,000 characters.")
    found = []
    for pid, rx, finding, fix in _RULES:
        m = re.search(rx, t, re.I)
        if m:
            p = next(x for x in PRINCIPLES if x["id"] == pid)
            found.append({"principle": p["name"], "quote": m.group(0).strip()[:100], "finding": finding, "fix": fix, "ask": p["ask"]})
    return {"findings": found, "clean": not found, "checked": len(_RULES),
            "verdict": f"{len(found)} principle concern(s) found." if found else "No red flags matched. That is a keyword check, not a review: ask the five questions anyway.",
            "questions": [{"principle": p["name"], "ask": p["ask"]} for p in PRINCIPLES],
            "limit": "Pattern matching on your wording. It cannot see the real system."}


# ------------------------------------------------------------------ CIA
CIA = {
    "confidentiality": {"means": "Only authorised parties can read the data.", "attacks": "eavesdropping, data breach, phishing, shoulder surfing, stolen laptop",
                        "controls": "access control, encryption at rest and in transit, MFA, least privilege, data classification"},
    "integrity": {"means": "Data is complete, accurate and unaltered; you can tell if it was changed.", "attacks": "tampering, man-in-the-middle edits, malware, SQL injection, insider edits",
                  "controls": "hashing, digital signatures, message authentication codes (MAC), checksums, version control, audit logs"},
    "availability": {"means": "Authorised users can use the system when they need it.", "attacks": "DoS, DDoS, SYN flood, ransomware, hardware failure, power loss",
                     "controls": "redundancy, backups and tested restores, rate limiting, DDoS protection, failover, capacity planning"},
}
_CIA_WORDS = {
    "confidentiality": r"eavesdrop|sniff|leak|breach|exfiltrat|steal|stole|stolen|phish|read (the )?(data|files|emails?)|disclos|unauthori[sz]ed (access|view)|expos\w+|encrypt|privacy|secret|password|shoulder",
    "integrity": r"tamper|modif|alter|chang(e|ed|ing) (the )?(data|records?|files?)|corrupt|forg|spoof|inject|man[- ]in[- ]the[- ]middle|hash|signature|checksum|mac\b|unauthori[sz]ed (edit|change)",
    "availability": r"\bdos\b|ddos|denial|flood|syn|outage|downtime|ransomware|crash|unavailable|power (cut|loss)|fail(ed|ure)|backup|redundan|capacity|overload|can(no|')t (log ?in|access|reach)",
}


def classify(text: str) -> dict:
    t = (text or "").strip()
    if len(t) < 8:
        raise FrameError("Describe the incident or the control in a sentence (at least 8 characters).")
    if len(t) > 5_000:
        raise FrameError("Keep it under 5,000 characters.")
    hits = {k: sorted({m.group(0).lower() for m in re.finditer(rx, t, re.I)}) for k, rx in _CIA_WORDS.items()}
    ranked = sorted(((k, v) for k, v in hits.items() if v), key=lambda kv: -len(kv[1]))
    if not ranked:
        return {"affected": [], "verdict": "No clear confidentiality, integrity or availability words. Rephrase: what was read, changed or made unavailable?", "model": CIA}
    out = [{"property": k, "matched": v[:6], **CIA[k]} for k, v in ranked]
    return {"affected": out, "verdict": "Most likely: " + ", ".join(o["property"] for o in out) + ". Real incidents often touch more than one; a ransomware attack hits availability and, if data was stolen first, confidentiality too.",
            "model": CIA, "limit": "Keyword matching; confirm with the three questions: what was read, what was changed, what stopped working?"}


# ------------------------------------------------------------------ NIST CSF
FUNCTIONS = [
    {"id": "govern", "name": "Govern", "added": "CSF 2.0 (2024)", "what": "Set the strategy, roles, policy and risk appetite; oversee supply chain risk.", "qs": [
        ("g1", "Is there a written security policy with a named owner?", "Write a short policy and name an owner (one page is a start)."),
        ("g2", "Are security roles and responsibilities written down, including who decides on risk?", "Assign who accepts risk and who runs response."),
        ("g3", "Do you check the security of vendors and suppliers who touch your data?", "Keep a vendor list and ask each for basic assurances.")]},
    {"id": "identify", "name": "Identify", "what": "Know what you have, what matters and what could go wrong.", "qs": [
        ("i1", "Is there an up-to-date list of devices, software and data?", "Build an asset inventory; you cannot protect what you do not know about."),
        ("i2", "Is data classified by sensitivity, with the crown jewels known?", "Classify data: public, internal, confidential, restricted."),
        ("i3", "Have you assessed risks and vulnerabilities in the last year?", "Run a risk assessment and a vulnerability scan of your own systems."),
        ("i4", "Is there a business impact analysis (what must come back first, and how fast)?", "Write down recovery priorities and targets for each system.")]},
    {"id": "protect", "name": "Protect", "what": "Safeguards that prevent or limit harm.", "qs": [
        ("p1", "Is MFA enabled on email, VPN and admin accounts?", "Turn on MFA, starting with email and admins."),
        ("p2", "Are systems patched on a schedule, with a deadline for critical fixes?", "Set a patch cadence and an emergency path."),
        ("p3", "Is access least-privilege, with reviews when people change roles or leave?", "Review access quarterly and remove it at offboarding."),
        ("p4", "Is data encrypted on laptops and in transit?", "Enable disk encryption and require TLS."),
        ("p5", "Are staff trained to spot phishing, with a way to report it?", "Run short regular training and add a report button.")]},
    {"id": "detect", "name": "Detect", "what": "Notice events as they happen.", "qs": [
        ("d1", "Are logs collected centrally and kept long enough to investigate?", "Send logs to one place and keep at least 90 days."),
        ("d2", "Does someone get alerted on suspicious sign-ins or malware?", "Set alerts for failed-login bursts, new admins and malware detections."),
        ("d3", "Is there endpoint protection on every computer, with a way to see its status?", "Deploy and monitor endpoint protection everywhere.")]},
    {"id": "respond", "name": "Respond", "what": "Act on an incident: contain, eradicate, communicate.", "qs": [
        ("r1", "Is there a written incident response plan with contacts?", "Write the plan: who declares an incident, who contacts whom."),
        ("r2", "Has the plan been rehearsed (a tabletop) in the last year?", "Run a one-hour tabletop exercise."),
        ("r3", "Do you know who to notify (customers, regulators, insurer) and by when?", "List notification duties and deadlines for your data.")]},
    {"id": "recover", "name": "Recover", "what": "Restore operations and learn.", "qs": [
        ("c1", "Are backups taken, kept offline or immutable, and restore-tested?", "Follow 3-2-1 and test a restore this quarter."),
        ("c2", "Is there a disaster recovery plan with recovery time and point targets?", "Set RTO and RPO per system and write the runbook."),
        ("c3", "After incidents, do you hold a review and change something because of it?", "Hold a blameless review within two weeks and track the fixes.")]},
]
_VAL = {"yes": 1.0, "partly": 0.5, "no": 0.0}


def csf_questions() -> dict:
    return {"functions": [{"id": f["id"], "name": f["name"], "what": f["what"], "added": f.get("added", ""), "questions": [{"id": q[0], "text": q[1]} for q in f["qs"]]} for f in FUNCTIONS],
            "options": list(_VAL)}


def csf_score(answers: dict) -> dict:
    if not isinstance(answers, dict):
        raise FrameError("Answers must be a map of question id to yes, partly or no.")
    known = {q[0] for f in FUNCTIONS for q in f["qs"]}
    for k, v in answers.items():
        if k not in known:
            raise FrameError(f"Unknown question '{k}'.")
        if v not in _VAL:
            raise FrameError(f"Answer for '{k}' must be yes, partly or no.")
    if not answers:
        raise FrameError("Answer at least one question.")
    rows, gaps = [], []
    for f in FUNCTIONS:
        given = [(q, answers[q[0]]) for q in f["qs"] if q[0] in answers]
        score = round(100 * sum(_VAL[a] for _, a in given) / len(given)) if given else None
        rows.append({"function": f["name"], "score": score, "answered": len(given), "of": len(f["qs"]),
                     "level": "not answered" if score is None else "strong" if score >= 80 else "developing" if score >= 40 else "weak"})
        gaps += [{"function": f["name"], "gap": q[1], "do": q[2], "severity": 2 if a == "no" else 1} for q, a in given if a != "yes"]
    gaps.sort(key=lambda g: (-g["severity"], g["function"]))
    scored = [r["score"] for r in rows if r["score"] is not None]
    return {"functions": rows, "overall": round(sum(scored) / len(scored)), "next_actions": gaps[:6], "all_gaps": len(gaps),
            "note": "The five (now six) functions are not steps to take in order. They run together, each feeding the others.",
            "limit": "A self-assessment is your own opinion, not an audit."}


SLIPS = [
    "NIST CSF reading: the Identify function is said to include 'developing incident response plans'. Those belong to Respond (and recovery plans to Recover). The same reading says Respond includes 'recovering impacted systems', which is Recover's job.",
    "NIST CSF reading: it describes five functions. CSF 2.0 (February 2024) added a sixth, Govern, for strategy, roles, policy and supply-chain risk.",
    "Principles video/reading: it counts five principles 'plus a sixth for anti-security'. Security by obscurity is an anti-pattern, not a principle. What Kerckhoffs actually argued: only the key should be secret, so published algorithms are fine and secret algorithms are a warning sign.",
    "SYN flood is said to flood a site 'until the server crashes'. It fills the half-open connection table so real clients cannot connect; the server often stays up and recovers when the flood stops. SYN cookies and rate limits are the usual defences.",
    "Password hashing reading: 'rainbow attacks use words from an original password hash to generate all other possible passwords' is garbled. A rainbow table is a precomputed table of hash chains used to look up the password for a hash. Salts (random per account) and slow hashes (bcrypt, scrypt, Argon2) defeat it. Also, one cracked hash only reveals other accounts' passwords when the hashes are unsalted.",
    "Linux run levels reading: run levels belong to SysV init. Most distributions now use systemd, where they map to targets (poweroff, rescue, multi-user, graphical, reboot) and 'init 5' is a compatibility shim; use systemctl isolate or set-default. Level 2 meaning 'multi-user without NFS' is a Red Hat convention; on Debian and Ubuntu levels 2 to 5 were identical.",
    "Windows Defender reading: under Quick Scan it lists 'System Files: scans all files and running programs on your hard disk, which can take several hours'. That describes a Full Scan. A Quick Scan checks the places malware usually lives. 'Real-Time Protection' is a heading over a list of scan types, which is a different feature. Offline scan restarts into the recovery environment; it is not a scan that runs 'before the OS loads' in the BIOS sense.",
    "Ports reading: 'a device can have up to 65,536 ports' (numbers 0 to 65535; port 0 is reserved) and 'port numbers do not change' (these are defaults and conventions; a service can listen on any port). SMB is given as ports 137 to 139, which are legacy NetBIOS over TCP/IP; modern SMB uses TCP 445. FTP uses 21 for control and 20 for data in active mode. SNMP agents listen on 161 and send traps to 162.",
    "Sockets: described as 'source IP, protocol, port, destination IP', which has one port. A socket is an IP address plus a port; a connection is identified by the five-tuple: source IP, source port, destination IP, destination port, protocol.",
    "Wireless standards: 802.20 and 802.22 are given as the standards for WWANs, WANETs and cellular. Cellular is defined by 3GPP, not the IEEE. 802.20 (mobile broadband wireless access) was never widely deployed and its working group was disbanded; 802.22 is for rural regional networks in TV white space. 802.11ax (Wi-Fi 6) is described as the latest; Wi-Fi 7 (802.11be) has followed. 'Ethernet 802.3d' should be 802.3.",
    "Cellular speeds (2G 64 kbps, 3G 2 Mbps, 4G 100 Mbps, 5G 1 Gbps) are headline targets; real 2G data was far slower and real speeds vary hugely by place and load.",
    "Protocol lesson includes a paragraph on a 'Crypto Classic protocol' for blockchain payments. That is not a network protocol in the sense of TCP, UDP, HTTP and the rest; treat it as off-topic filler.",
    "'If a switch or hub fails, it brings the entire network down' overstates: it takes down the devices that depend on it. That is why designs add redundant links and switches.",
]
