"""IT admin lab: Microsoft 365 and Entra ID admin, email authentication checker (SPF, DKIM, DMARC), onboarding and offboarding runbooks,
script reviewer and snippet library, ITIL priority and SLA helpers, patch policy and change request templates.
Reference and local text checks only. Nothing here connects to a tenant, runs scripts or sends mail. Never paste passwords or real client secrets."""
from __future__ import annotations

import re

NOTE = "Reference and local checks. Product menus and policy names change, so confirm in the vendor's current admin portal and docs."


class AdminError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


# ------------------------------------------------------------------ email authentication
def _tags(rec: str) -> dict:
    out = {}
    for part in rec.split(";"):
        if "=" in part:
            k, _, v = part.partition("=")
            out[k.strip().lower()] = v.strip()
    return out


def email_auth(domain: str = "", spf: str = "", dmarc: str = "", dkim: str = "") -> dict:
    """Check pasted SPF, DMARC and DKIM TXT records. Nothing is looked up online: you paste what 'nslookup -type=txt' or your DNS host shows."""
    spf, dmarc, dkim = (spf or "").strip().strip('"'), (dmarc or "").strip().strip('"'), (dkim or "").strip().strip('"')
    if not (spf or dmarc or dkim):
        raise AdminError("Paste at least one record: SPF (starts v=spf1), DMARC (starts v=DMARC1) or DKIM (starts v=DKIM1).")
    if max(len(spf), len(dmarc), len(dkim)) > 4000:
        raise AdminError("A record that long is probably not a single TXT record. Paste one record at a time.")
    finds, ok = [], []

    def bad(sev, msg, fix):
        finds.append({"severity": sev, "problem": msg, "fix": fix})
    if spf:
        low = spf.lower()
        if not low.startswith("v=spf1"):
            bad("high", "The SPF record does not start with v=spf1.", "A valid SPF record begins exactly with v=spf1.")
        else:
            mechs = low.split()[1:]
            lookups = sum(1 for m in mechs if re.match(r"^[+\-~?]?(include:|a\b|mx\b|ptr\b|exists:|redirect=)", m))
            end = next((m for m in reversed(mechs) if re.match(r"^[+\-~?]?all$", m)), None)
            if end is None:
                bad("high", "No 'all' ending, so receivers have no instruction for other senders.", "End with -all (strict) or ~all (soft fail while you test).")
            elif end in ("+all", "all"):
                bad("high", "'+all' lets anyone send as your domain.", "Change it to -all or ~all.")
            elif end == "?all":
                bad("medium", "'?all' is neutral and gives almost no protection.", "Use ~all while testing, then -all.")
            elif end == "~all":
                ok.append("Ends in ~all (soft fail). Fine while testing; move to -all when every sender is listed.")
            else:
                ok.append("Ends in -all (strict).")
            if lookups > 10:
                bad("high", f"About {lookups} DNS lookups: SPF allows at most 10, and more makes it fail.", "Remove unused includes or use an SPF flattening service.")
            elif lookups >= 8:
                bad("low", f"About {lookups} DNS lookups, close to the limit of 10.", "Keep it under 10 when adding services.")
            if "ptr" in " ".join(mechs):
                bad("medium", "The 'ptr' mechanism is discouraged: slow and unreliable.", "Replace ptr with ip4, ip6 or include.")
            if len(re.findall(r"v=spf1", low)) > 1:
                bad("high", "Two SPF records. A domain must have only one.", "Merge them into one record.")
            ok.append("Known senders to confirm are listed: " + ", ".join(m for m in mechs if m.startswith(("include:", "ip4:", "ip6:", "a", "mx")))[:200])
    if dmarc:
        t = _tags(dmarc)
        if t.get("v", "").upper() != "DMARC1":
            bad("high", "The DMARC record does not start with v=DMARC1.", "A valid record begins v=DMARC1; p=...")
        pol = t.get("p", "").lower()
        if pol not in ("none", "quarantine", "reject"):
            bad("high", "Missing or invalid policy (p=).", "Set p=none to monitor, then quarantine, then reject.")
        elif pol == "none":
            bad("medium", "p=none only monitors. Spoofed mail is still delivered.", "Read the reports, fix the senders, then move to p=quarantine and p=reject.")
        else:
            ok.append(f"Policy p={pol}.")
        if "rua" not in t:
            bad("medium", "No rua= address for aggregate reports, so you cannot see who sends as your domain.", "Add rua=mailto:dmarc@yourdomain (or a report service address).")
        pct = t.get("pct")
        if pct and pct != "100" and pol in ("quarantine", "reject"):
            bad("low", f"pct={pct}: the policy applies to only part of the mail.", "Raise it to 100 when ready.")
        if t.get("sp", pol) == "none" and pol in ("quarantine", "reject"):
            bad("low", "Subdomains are not protected (sp=none).", "Remove sp or set it to match p.")
        if t.get("adkim", "r") == "r" and t.get("aspf", "r") == "r":
            ok.append("Relaxed alignment (the default), which suits most small businesses.")
    if dkim:
        t = _tags(dkim)
        if "p" not in t:
            bad("high", "No public key (p=). The DKIM record is incomplete.", "Copy the full value from your mail provider.")
        elif t["p"] == "":
            bad("high", "The public key is empty: this DKIM key is revoked.", "Publish the current key from your provider.")
        else:
            keylen = len(re.sub(r"\s", "", t["p"])) * 6 // 8
            if keylen < 200:
                bad("medium", "The key looks shorter than 1024 bits.", "Use a 2048-bit key if your provider supports it.")
            else:
                ok.append("A public key is present.")
        if t.get("k", "rsa").lower() not in ("rsa", "ed25519"):
            bad("low", "Unusual key type.", "Use rsa (or ed25519 if your provider supports it).")
    if not finds:
        ok.append("No problems found in what you pasted.")
    order = {"high": 0, "medium": 1, "low": 2}
    finds.sort(key=lambda f: order[f["severity"]])
    return {"domain": domain[:80], "findings": finds, "good": ok, "steps": ["Publish exactly one SPF record, DKIM keys from each sending service, and a DMARC record.", "Start DMARC at p=none with a reporting address, read reports for a few weeks, fix each legitimate sender, then move to quarantine and then reject.",
                                                                           "Test by sending to a mailbox you control and read the Authentication-Results header (spf, dkim and dmarc should say pass)."], "note": NOTE}


# ------------------------------------------------------------------ onboarding and offboarding
def lifecycle(kind: str, name: str = "", role: str = "", platform: str = "m365", extras: str = "") -> dict:
    kind = (kind or "").lower()
    if kind not in ("onboard", "offboard"):
        raise AdminError("Choose onboard or offboard.")
    who = (name or "the person").strip()[:60]
    plat = {"m365": "Microsoft 365 and Entra ID", "google": "Google Workspace"}.get(platform, "Microsoft 365 and Entra ID")
    if kind == "onboard":
        steps = [f"Get written approval and the start date for {who} ({role or 'role'}) from the owner or manager.", f"Create the user in {plat} with a unique username. Set a temporary password that must be changed, and share it by a separate channel.",
                 "Assign only the licenses the role needs and add to the right groups (shared mailboxes, teams, file shares).", "Require multi-factor authentication at first sign-in and record the method used.", "Set up the device: encryption on, updates on, antivirus on, local admin not given by default, name it by asset tag.",
                 "Install the role's apps and printers. Sign in to line-of-business apps with their own account, not a shared one.", "Add to the asset inventory and note serial numbers, warranty and who has it.", "Walk through password manager use, phishing reporting, and who to call for help.", "Confirm with the person that mail, files, calendar and printing work. Record the completion date."]
    else:
        steps = [f"Get written confirmation of the last day and who handles the data for {who}. Decide first whether any mail or files need to be kept.", "Reset the password and sign out all sessions and refresh tokens. Block sign-in at the planned time.",
                 "Remove from groups and revoke app access, OAuth grants and MFA methods. Disable or remove any remote access or VPN.", "Convert the mailbox to a shared mailbox or set forwarding and an auto-reply if the manager asks, and keep it for the retention period before deleting.",
                 "Transfer or back up the person's files (OneDrive or Drive) to the manager before the account is removed.", "Recover the device, accessories and keys. Wipe and reimage after the data is saved, and update the inventory.", "Remove or reassign licenses after the retention period to stop the cost.", "Update shared passwords the person knew, and rotate any keys or tokens they held.", "Record each step and the date. Do not delete anything before the owner approves."]
    if extras.strip():
        steps.append("Extra item noted by you: " + extras.strip()[:200])
    return {"kind": kind, "steps": steps, "platform": plat, "caution": "Keep audit notes (no passwords). Deleting mail and files cannot always be undone: keep them until the owner approves.", "note": NOTE}


M365 = {
    "baseline": ["Turn on security defaults, or build Conditional Access policies if the license allows.", "Require MFA for all users, and phishing-resistant methods for admins where possible.", "Keep two emergency admin accounts excluded from Conditional Access, with long unique passwords stored offline.",
                 "Block legacy authentication (IMAP, POP and old protocols).", "Use separate admin accounts without mailboxes for admin work.", "Turn on audit logging and review sign-in risk and unusual sign-ins.", "Set mailbox auto-forwarding to external addresses to blocked.",
                 "Configure SPF, DKIM and DMARC (see the email authentication checker).", "Enable anti-phishing and safe attachments if the license includes them.", "Restrict who can create teams and groups and who can share files externally.", "Back up Microsoft 365 data with a third-party backup: retention in the tenant is not a backup."],
    "licensing": [{"plan": "Business Basic", "for": "Web and mobile apps, Exchange, Teams, 1 TB OneDrive", "note": "No desktop apps"}, {"plan": "Business Standard", "for": "Adds desktop Office apps", "note": "Most common for small offices"},
                  {"plan": "Business Premium", "for": "Adds Intune device management, Defender for Business, Conditional Access", "note": "Best fit when you need real security and managed devices"}, {"plan": "Exchange Online only", "for": "Just email", "note": "When files and Teams are elsewhere"}],
    "common_tasks": [{"task": "Reset a password", "how": "Admin center, Users, Active users, choose the user, Reset password. Require change at next sign-in."}, {"task": "Shared mailbox", "how": "Exchange admin center, Shared mailboxes, add members. No license needed under the size limit."},
                     {"task": "Mailbox full", "how": "Check size and archive. Enable the online archive if licensed or move old mail; do not delete without approval."}, {"task": "Add MFA method", "how": "User signs in at the security info page and adds an authenticator app. Admin can require re-registration."},
                     {"task": "Mail not arriving", "how": "Run message trace in the Exchange admin center, check quarantine, then SPF, DKIM and DMARC, then connectors and mail flow rules."}, {"task": "External sharing too open", "how": "SharePoint admin center sharing settings: set to existing guests or specific people."}],
    "intune": ["Enroll devices: Autopilot for new company PCs, user enrollment or company portal for existing ones.", "Create a baseline compliance policy: encryption, password or PIN, OS version, antivirus on.", "Require compliant devices in Conditional Access.", "Deploy apps and settings with assignments to device or user groups.",
               "Use update rings to stage Windows updates (a pilot group first, then everyone).", "Test remote wipe and retire on a spare device before you need it.", "Document which devices are personal (BYOD) versus company owned, since they get different controls."],
}

SCRIPT_RULES = [
    ("high", r"(?i)\bRemove-Item\b[^\n]*-Recurse[^\n]*-Force|\brm\s+-rf\s+(/|~|\$HOME|\*)|\bdel\s+/s\s+/q|\bformat\s+[a-z]:", "Can delete a lot of data at once.", "Test on a copy, add -WhatIf (PowerShell) or echo first, and scope the path narrowly."),
    ("high", r"(?i)Set-ExecutionPolicy\s+(Bypass|Unrestricted)|-ExecutionPolicy\s+Bypass", "Turns off script safety checks.", "Sign your scripts or use RemoteSigned; do not leave Bypass in place."),
    ("high", r"(?i)(iex|Invoke-Expression)\s*\(?.*(DownloadString|Invoke-WebRequest|iwr|curl)|(curl|wget)[^\n|]*\|\s*(sudo\s+)?(ba)?sh", "Downloads and runs code without reading it.", "Download it, read it, check a hash, then run it."),
    ("high", r"(?i)(password|passwd|pwd|secret|token)\s*=\s*[\"'][^\"'$]{4,}[\"']|ConvertTo-SecureString\s+[\"'][^\"']+[\"']\s+-AsPlainText", "A password or secret is written in the script.", "Prompt for it, use a secret store or Get-Credential, and rotate the exposed one."),
    ("medium", r"(?i)Disable-(NetFirewall|WindowsOptionalFeature)|Set-MpPreference\s+-Disable|netsh\s+advfirewall\s+set\s+\w+\s+state\s+off", "Weakens a security control.", "Make sure this is intended, documented and reversible."),
    ("medium", r"(?i)Stop-Computer|Restart-Computer|shutdown\s+(/r|/s|-r|-h)|\breboot\b", "Restarts or shuts down machines.", "Run only in the agreed window and warn users."),
    ("medium", r"(?i)Get-ADUser[^\n]*\|[^\n]*(Remove|Disable|Set)-ADUser|Remove-ADUser|Remove-Mailbox|Remove-MsolUser", "Changes or removes accounts in bulk.", "Output the list first, review it, and use -WhatIf before the change."),
    ("low", r"(?i)-ErrorAction\s+SilentlyContinue|\|\|\s*true|2>/dev/null", "Errors are hidden, so failures may go unnoticed.", "Log errors and handle the ones you expect."),
]


def review_script(text: str) -> dict:
    text = text or ""
    if len(text.strip()) < 5:
        raise AdminError("Paste a PowerShell, Bash or batch script to review.")
    if len(text) > 20000:
        raise AdminError("Keep it under 20,000 characters.")
    finds = []
    for sev, pat, msg, fix in SCRIPT_RULES:
        for m in re.finditer(pat, text):
            line = text.count("\n", 0, m.start()) + 1
            snip = text.splitlines()[line - 1].strip()[:90]
            if re.search(r"(?i)password|secret|token|pwd", snip):
                snip = re.sub(r"([\"'])[^\"']{3,}([\"'])", r"\1[hidden]\2", snip)
            finds.append({"severity": sev, "line": line, "problem": msg, "fix": fix, "snippet": snip})
    order = {"high": 0, "medium": 1, "low": 2}
    finds.sort(key=lambda f: (order[f["severity"]], f["line"]))
    return {"findings": finds[:30], "counts": {k: sum(1 for f in finds if f["severity"] == k) for k in order},
            "habits": ["Run with -WhatIf (PowerShell) or a dry run first.", "Test on one practice machine, then one client machine, then the rest.", "Log what the script changes.", "Keep a rollback.", "Never run a script you do not understand on a client's machine."],
            "caveat": "Pattern matching on common risks. It cannot judge what the script really does. Read it yourself.", "note": NOTE}


SNIPPETS = [
    {"title": "List disk space on a Windows PC", "lang": "powershell", "text": "Get-PSDrive -PSProvider FileSystem | Select Name, @{n='UsedGB';e={[math]::Round($_.Used/1GB,1)}}, @{n='FreeGB';e={[math]::Round($_.Free/1GB,1)}}", "safe": "Read only"},
    {"title": "Show the last 20 critical or error events (System log)", "lang": "powershell", "text": "Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2} -MaxEvents 20 | Format-Table TimeCreated, Id, ProviderName, Message -Wrap", "safe": "Read only"},
    {"title": "List installed programs", "lang": "powershell", "text": "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*, HKLM:\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | Where DisplayName | Select DisplayName, DisplayVersion, Publisher | Sort DisplayName", "safe": "Read only"},
    {"title": "Check Windows update status and last install", "lang": "powershell", "text": "Get-HotFix | Sort InstalledOn -Descending | Select -First 10", "safe": "Read only"},
    {"title": "System file check and repair", "lang": "powershell", "text": "sfc /scannow\nDISM /Online /Cleanup-Image /RestoreHealth", "safe": "Changes system files: run from an elevated prompt, back up first"},
    {"title": "Reset the network stack", "lang": "powershell", "text": "ipconfig /flushdns\nnetsh winsock reset\nnetsh int ip reset\n# restart the PC afterwards", "safe": "Resets network settings: note static IP settings first"},
    {"title": "Find large files in a folder", "lang": "powershell", "text": "Get-ChildItem C:\\Users -Recurse -File -ErrorAction SilentlyContinue | Sort Length -Descending | Select -First 20 FullName, @{n='MB';e={[math]::Round($_.Length/1MB)}}", "safe": "Read only"},
    {"title": "Check which process is using a port", "lang": "powershell", "text": "Get-NetTCPConnection -LocalPort 443 | Select LocalAddress, LocalPort, State, OwningProcess, @{n='Name';e={(Get-Process -Id $_.OwningProcess).ProcessName}}", "safe": "Read only"},
    {"title": "Linux: disk, memory and top processes", "lang": "bash", "text": "df -h\nfree -h\nps aux --sort=-%mem | head -10", "safe": "Read only"},
    {"title": "Linux: recent login attempts", "lang": "bash", "text": "last -n 20\nsudo journalctl -u ssh --since '1 hour ago' | tail -50", "safe": "Read only"},
    {"title": "Bulk create users from a CSV (preview first)", "lang": "powershell", "text": "# users.csv columns: Name,UserPrincipalName\nImport-Csv users.csv | ForEach-Object { Write-Host \"Would create $($_.UserPrincipalName)\" }\n# Replace Write-Host with your real creation command only after reviewing the preview", "safe": "Preview only as written"},
]

# ------------------------------------------------------------------ ITIL helpers
PRIORITY = {("high", "high"): "P1", ("high", "medium"): "P2", ("medium", "high"): "P2", ("high", "low"): "P3", ("medium", "medium"): "P3", ("low", "high"): "P3", ("medium", "low"): "P4", ("low", "medium"): "P4", ("low", "low"): "P5"}
TARGETS = {"P1": ("15 minutes", "4 hours"), "P2": ("1 hour", "8 hours"), "P3": ("4 hours", "2 business days"), "P4": ("1 business day", "5 business days"), "P5": ("2 business days", "10 business days")}


def priority(impact: str, urgency: str) -> dict:
    i, u = (impact or "").lower(), (urgency or "").lower()
    if i not in ("high", "medium", "low") or u not in ("high", "medium", "low"):
        raise AdminError("Impact and urgency must each be high, medium or low.")
    p = PRIORITY[(i, u)]
    r, s = TARGETS[p]
    return {"priority": p, "respond_within": r, "resolve_within": s, "how": "Impact is how many people or how much money is affected. Urgency is how soon it must be fixed. Priority comes from both. These targets are examples: set your own in the client's agreement.", "note": NOTE}


def sla(available_pct, window_days=30) -> dict:
    try:
        a, d = float(available_pct), float(window_days)
    except (TypeError, ValueError):
        raise AdminError("Availability and days must be numbers.") from None
    if not 0 < a <= 100 or not 0 < d <= 3650:
        raise AdminError("Availability must be above 0 and at most 100, and days from 1 to 3650.")
    mins = d * 24 * 60 * (1 - a / 100)
    return {"allowed_downtime_minutes": round(mins, 1), "allowed_downtime_hours": round(mins / 60, 2), "note": "Planned maintenance is often excluded. Say in writing what counts as downtime and how it is measured."}


CHANGE_TEMPLATE = """CHANGE REQUEST
Client / system:
Requested by / approved by (name, date):
Type: standard (pre-approved) / normal / emergency
Reason and benefit:
Risk if we do it / if we do not:
Impact (who, how long):
Backup or snapshot taken (where, tested?):
Steps:
1.
Test plan (how we confirm it worked):
Rollback plan (exact steps, time needed):
Window agreed:
Result and notes after:
"""

PATCH_POLICY = [
    "Inventory first: you cannot patch what you do not know about.", "Test group first: patch one or two machines, wait a day or two, then roll out.", "Set the schedule: monthly for routine updates, and within days for critical or actively exploited vulnerabilities.",
    "Keep a rollback: restore point or snapshot, and a backup before big feature updates.", "Cover everything: operating systems, browsers, Office, PDF readers, drivers, firmware and network gear.", "Pause on known-bad updates and note why.", "Record what was patched, when, and which machines failed.", "Retire machines that can no longer be patched or isolate them."]


def reference() -> dict:
    return {"m365": M365, "snippets": SNIPPETS, "change_template": CHANGE_TEMPLATE, "patch_policy": PATCH_POLICY, "targets": TARGETS, "note": NOTE}


STOP = {
    "IRQL_NOT_LESS_OR_EQUAL": ("A driver or hardware touched memory it should not.", "Recent driver or software, bad RAM", "Boot to Safe Mode, remove the newest driver, test RAM, update drivers"),
    "PAGE_FAULT_IN_NONPAGED_AREA": ("Windows looked for data in memory that was not there.", "Bad RAM, faulty driver, damaged system files", "Test RAM, update or roll back drivers, run sfc and DISM"),
    "SYSTEM_SERVICE_EXCEPTION": ("A system service hit an error, often caused by a driver.", "Graphics or antivirus driver, corrupt files", "Update or remove the named driver, run sfc, check the dump"),
    "KERNEL_DATA_INPAGE_ERROR": ("Windows could not read data from the drive into memory.", "Failing drive, loose cable, bad controller", "Back up now, check drive health, reseat the cable, test another drive"),
    "UNEXPECTED_STORE_EXCEPTION": ("A storage component failed unexpectedly.", "Failing SSD or drive, antivirus conflict", "Check drive health and firmware, update storage driver"),
    "CRITICAL_PROCESS_DIED": ("A core Windows process stopped.", "Corrupt system files, bad driver or drive", "Run sfc and DISM, check the drive, uninstall recent updates"),
    "MEMORY_MANAGEMENT": ("Windows memory management found a problem.", "Bad RAM or overclocking", "Run a memory test, reseat RAM, reset XMP and BIOS defaults"),
    "INACCESSIBLE_BOOT_DEVICE": ("Windows could not reach the drive it boots from.", "Storage driver change, BIOS mode change (AHCI/RAID), failing drive, corrupt boot files", "Check BIOS drive mode, repair boot files, test the drive"),
    "DRIVER_IRQL_NOT_LESS_OR_EQUAL": ("A named driver misbehaved.", "Network, graphics or antivirus driver", "Note the .sys file, update or remove that driver"),
    "WHEA_UNCORRECTABLE_ERROR": ("The hardware reported a serious fault.", "CPU or RAM instability, overheating, failing hardware, overclock", "Reset overclocks, check temperatures, test RAM, update BIOS"),
    "CLOCK_WATCHDOG_TIMEOUT": ("A CPU core stopped responding.", "Overclock, BIOS or CPU problem", "Reset BIOS defaults, update BIOS, check cooling"),
    "NTFS_FILE_SYSTEM": ("The file system hit an error.", "Disk errors, corruption", "Run chkdsk, check drive health, back up"),
    "BAD_POOL_HEADER": ("Memory pool is corrupt.", "Driver bug or bad RAM", "Update drivers, test RAM"),
    "VIDEO_TDR_FAILURE": ("The graphics driver stopped responding and could not recover.", "Graphics driver, overheating GPU, power", "Clean install the graphics driver, check temperatures and power supply"),
    "DPC_WATCHDOG_VIOLATION": ("A driver took too long to respond.", "Storage or network driver, firmware", "Update SSD firmware and storage driver, switch controller driver"),
    "SYSTEM_THREAD_EXCEPTION_NOT_HANDLED": ("A system thread failed, usually because of a driver.", "Graphics or other drivers", "Note the driver file, update or remove it"),
}


def stop_code(code: str) -> dict:
    q = re.sub(r"[^A-Z_]", "", (code or "").upper().replace(" ", "_"))
    if len(q) < 4:
        raise AdminError("Type a stop code such as IRQL_NOT_LESS_OR_EQUAL or a part of it.")
    hits = [k for k in STOP if q in k or k in q]
    if not hits:
        return {"matches": [], "advice": "Not in the short list. Search the exact stop code from the blue screen, note any .sys file named, and check the System log in Event Viewer around the crash time.", "note": NOTE}
    return {"matches": [{"code": k, "meaning": STOP[k][0], "usual_causes": STOP[k][1], "first_steps": STOP[k][2]} for k in hits[:4]],
            "advice": "Change one thing at a time and keep the minidump files. A stop code points to a family of causes, not one certain cause.", "note": NOTE}
