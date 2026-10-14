"""Windows endpoint hardening audit.  The app never touches a computer.  It writes a READ-ONLY PowerShell script
(Get- commands and registry reads only), you run it on a PC you own, paste the output back, and it grades each line
against a baseline with the reason and the usual fix.  Fixes are text to read and test first; nothing here changes a setting."""
import re


class EndpointError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


MAX_CHARS = 100_000

REG = lambda path, name: f"(Get-ItemProperty -Path '{path}' -Name '{name}' -ErrorAction SilentlyContinue).'{name}'"
LSA = r"HKLM:\SYSTEM\CurrentControlSet\Control\Lsa"
DNSP = r"HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient"
TS = r"HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server"
SCH = r"HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols"


def _tls(ver: str) -> str:
    p = rf"{SCH}\{ver}\Server"
    return f"$v={REG(p, 'Enabled')}; if ($null -eq $v) {{'default'}} elseif ($v -eq 0) {{'disabled'}} else {{'enabled'}}"


# id, title, severity (3 high, 2 medium, 1 low), PowerShell expression, rule key, why, fix, needs_admin
CHECKS = [
    ("smb1", "SMB version 1 is off", 3, "(Get-SmbServerConfiguration).EnableSMB1Protocol", "false", "SMB1 is the protocol behind WannaCry and NotPetya. Nothing modern needs it.", "Disable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol (find what still uses it first: Set-SmbServerConfiguration -AuditSmb1Access $true).", True),
    ("ps2", "Windows PowerShell 2.0 is off", 2, "(Get-WindowsOptionalFeature -Online -FeatureName MicrosoftWindowsPowerShellV2Root).State", "disabled", "PowerShell 2.0 lacks modern logging and script-scanning, so attackers downgrade to it to avoid detection.", "Disable-WindowsOptionalFeature -Online -FeatureName MicrosoftWindowsPowerShellV2Root", True),
    ("tls10", "TLS 1.0 server is off", 2, _tls("TLS 1.0"), "disabled_or_default", "TLS 1.0 and 1.1 are deprecated and weak. 'default' means no explicit setting, so the Windows version decides.", "Set Enabled=0 and DisabledByDefault=1 under the SCHANNEL TLS 1.0 Server key, or use Group Policy. Test web and line-of-business apps first.", False),
    ("tls11", "TLS 1.1 server is off", 2, _tls("TLS 1.1"), "disabled_or_default", "As for TLS 1.0.", "As for TLS 1.0, using the TLS 1.1 key.", False),
    ("lmlevel", "LAN Manager authentication level is 5 (NTLMv2 only, refuse LM and NTLM v1)", 3, REG(LSA, "LmCompatibilityLevel"), "lm5", "Levels below 3 send weak LM or NTLMv1 hashes that crack in minutes. Level 5 still allows NTLMv2; it does not turn NTLM off.", "Group Policy: Network security: LAN Manager authentication level = Send NTLMv2 response only, refuse LM and NTLM. Audit old devices and NAS boxes first.", False),
    ("wdigest", "WDigest does not keep clear-text passwords in memory", 3, REG(r"HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\WDigest", "UseLogonCredential"), "wdigest", "With UseLogonCredential=1 tools like Mimikatz read plain passwords from memory. Current Windows defaults to off; attackers flip it on.", "Set UseLogonCredential to 0 (or remove the value) and alert if it changes.", False),
    ("secureboot", "Secure Boot is on", 2, "try { Confirm-SecureBootUEFI } catch { 'unsupported' }", "true", "Secure Boot stops unsigned boot code (bootkits). 'unsupported' means legacy BIOS or no admin rights.", "Enable UEFI and Secure Boot in firmware; convert MBR disks with mbr2gpt first on supported builds.", True),
    ("bitlocker", "System drive is encrypted (BitLocker)", 2, "try { (Get-BitLockerVolume -MountPoint $env:SystemDrive).ProtectionStatus } catch { 'unsupported' }", "bitlocker", "A lost laptop without disk encryption is a data breach.", "Turn on BitLocker and store the recovery key in a directory service, not on the PC.", True),
    ("fw_domain", "Firewall is on for the Domain profile", 3, "(Get-NetFirewallProfile -Name Domain).Enabled", "true", "The host firewall is the last control between a compromised neighbour and this machine.", "Set-NetFirewallProfile -Profile Domain -Enabled True (Group Policy for fleets).", False),
    ("fw_private", "Firewall is on for the Private profile", 3, "(Get-NetFirewallProfile -Name Private).Enabled", "true", "As above, for home and trusted networks.", "Set-NetFirewallProfile -Profile Private -Enabled True", False),
    ("fw_public", "Firewall is on for the Public profile", 3, "(Get-NetFirewallProfile -Name Public).Enabled", "true", "Public Wi-Fi is the profile that matters most.", "Set-NetFirewallProfile -Profile Public -Enabled True", False),
    ("rdp", "Remote Desktop is off (or deliberately on)", 3, REG(TS, "fDenyTSConnections"), "rdp", "Exposed RDP is a common ransomware entry. 1 = off. If it must be on, require NLA, MFA and a VPN or gateway; never forward port 3389 to the internet.", "System Properties > Remote: turn off, or restrict with firewall scope and a gateway.", False),
    ("nla", "Remote Desktop requires Network Level Authentication", 2, REG(TS + r"\WinStations\RDP-Tcp", "UserAuthentication"), "one", "NLA makes the user authenticate before a session is created, which blocks several attacks.", "Require NLA in the Remote tab or by policy.", False),
    ("llmnr", "LLMNR name resolution is off", 2, REG(DNSP, "EnableMulticast"), "zero", "LLMNR lets any host on the segment answer name lookups, so an attacker can capture hashes (Responder). Absent means enabled. (mDNS is a separate, similar service.)", "Policy: Computer Configuration > Administrative Templates > Network > DNS Client > Turn off multicast name resolution = Enabled.", False),
    ("netbios", "NetBIOS over TCP/IP is off on active adapters", 2, "(Get-CimInstance Win32_NetworkAdapterConfiguration -Filter 'IPEnabled=true').TcpipNetbiosOptions -join ','", "netbios", "NetBIOS name service is another poisoning target. 2 = disabled, 0 = taken from DHCP, 1 = enabled.", "Adapter properties > IPv4 > Advanced > WINS > Disable NetBIOS, or a DHCP option 001 for fleets.", False),
    ("smnr", "Smart multi-homed name resolution is off", 1, REG(DNSP, "DisableSmartNameResolution"), "one", "Without it the PC sends DNS queries out of every adapter, which can leak internal names to a VPN or public network.", "Policy: DNS Client > Turn off smart multi-homed name resolution = Enabled.", False),
    ("uac", "User Account Control is on", 3, REG(r"HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "EnableLUA"), "one", "UAC is what separates an admin's normal work from elevated work.", "Turn it on and keep the default prompt level.", False),
    ("admins", "Local Administrators group is small", 2, "try { (Get-LocalGroupMember -Group Administrators | ForEach-Object { $_.Name }) -join ';' } catch { 'unknown' }", "admins", "Every extra local admin is an account whose theft ends in full control. List them and remove anyone who does not need it.", "Remove daily-use accounts from Administrators; give a separate admin account, and use LAPS to rotate the built-in administrator password.", True),
    ("credguard", "Credential Guard is running", 2, "try { ((Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\\Microsoft\\Windows\\DeviceGuard).SecurityServicesRunning -contains 1) } catch { 'unsupported' }", "true", "Credential Guard isolates domain credential hashes in a virtualised enclave, which defeats most pass-the-hash theft.", "Enable via Group Policy (Device Guard) on supported hardware; test with your drivers and VPN client.", True),
    ("defender_rt", "Microsoft Defender real-time protection is on", 3, "try { (Get-MpComputerStatus).RealTimeProtectionEnabled } catch { 'unsupported' }", "true", "'unsupported' appears when another antivirus has taken over; make sure that product is running and updated.", "Turn real-time protection on in Windows Security, or confirm your other endpoint product is active.", False),
    ("asr", "Attack surface reduction rules are configured", 2, "try { @((Get-MpPreference).AttackSurfaceReductionRules_Ids).Count } catch { 'unsupported' }", "asr", "ASR rules block common malware behaviours such as Office launching scripts. The number of rules shown is how many are configured.", "Start every rule in Audit mode, review the events, then move to Block. Microsoft's ASR rules reference lists each rule.", True),
    ("patch_age", "Last installed update is recent", 3, "try { [int]((Get-Date) - (Get-HotFix | Where-Object InstalledOn | Sort-Object InstalledOn -Descending | Select-Object -First 1).InstalledOn).TotalDays } catch { 'unknown' }", "patch", "Unpatched Exchange, VPN and Office flaws drive many headline breaches. This is days since the newest update Get-HotFix lists, which can miss some cumulative updates, so confirm in Windows Update history.", "Patch on a schedule: pilot group, then everyone, with a backout plan.", False),
    ("seclog", "Security event log is at least 192 MB", 1, "try { [int]((Get-WinEvent -ListLog Security).MaximumSizeInBytes / 1MB) } catch { 'unknown' }", "seclog", "The default 20 MB log overwrites in hours on a busy machine, erasing evidence. 192 MB is a common baseline.", "wevtutil sl Security /ms:201326592 (or Group Policy), and forward important events off the machine.", True),
    ("excel_macros", "Excel blocks macros from files downloaded from the internet", 2, REG(r"HKCU:\Software\Policies\Microsoft\Office\16.0\Excel\Security", "blockcontentexecutionfrominternet"), "macro", "Malicious spreadsheets are a classic first step. Current Microsoft 365 blocks internet macros by default; the policy makes it deliberate. Absent means 'default'.", "Policy: Block macros from running in Office files from the Internet = Enabled.", False),
]

IDS = [c[0] for c in CHECKS]


def script() -> str:
    lines = [
        "# Read-only endpoint hardening check. It reads settings and prints ID=VALUE lines. It changes nothing.",
        "# Run in Windows PowerShell on a PC you own. Right-click > Run as administrator gives the fullest results.",
        "# Paste the whole output back into the Endpoint hardening tab.",
        "$ErrorActionPreference = 'SilentlyContinue'",
        "function Out-Check($id, [scriptblock]$s) { try { $v = & $s; if ($null -eq $v -or \"$v\" -eq '') { $v = 'unset' }; Write-Output (\"$id=\" + \"$v\") } catch { Write-Output \"$id=error\" } }",
    ]
    for cid, _t, _s, expr, *_ in CHECKS:
        lines.append(f"Out-Check '{cid}' {{ {expr} }}")
    return "\n".join(lines) + "\n"


def _int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _judge(rule: str, v: str):
    """-> (status, note). status: pass, warn, fail, unknown"""
    low = v.strip().lower()
    if low in ("error", "unknown", "unsupported"):
        return "unknown", "The script could not read this (run as administrator, or this PC doesn't support it)."
    n = _int(v)
    if rule == "false":
        return ("pass", "off") if low == "false" else (("fail", "still enabled") if low == "true" else ("unknown", f"unexpected value '{v}'"))
    if rule == "true":
        return ("pass", "on") if low == "true" else (("fail", "off") if low == "false" else ("unknown", f"unexpected value '{v}'"))
    if rule == "disabled":
        return ("pass", "disabled") if low == "disabled" else (("fail", "feature is enabled") if low == "enabled" else ("unknown", f"state '{v}'"))
    if rule == "disabled_or_default":
        return {"disabled": ("pass", "explicitly disabled"), "default": ("warn", "no explicit setting: depends on the Windows version; set it deliberately"), "enabled": ("fail", "enabled")}.get(low, ("unknown", f"value '{v}'"))
    if rule == "lm5":
        if low == "unset":
            return "warn", "no value set, so the Windows default applies (often 3). Set 5 deliberately."
        return ("pass", "level 5") if n is not None and n >= 5 else (("warn", f"level {n}: NTLMv2 preferred but weaker responses are still accepted") if n in (3, 4) else ("fail", f"level {n}: sends weak LM or NTLMv1"))
    if rule == "wdigest":
        return ("pass", "off or default (off)") if low in ("unset", "0") else (("fail", "clear-text credentials cached in memory") if n == 1 else ("unknown", f"value '{v}'"))
    if rule == "bitlocker":
        return ("pass", "protection on") if low in ("on", "1") else (("fail", "protection off") if low in ("off", "0") else ("unknown", f"status '{v}'"))
    if rule == "rdp":
        return ("pass", "RDP off") if n == 1 else (("warn", "RDP is on: needs NLA, MFA and no direct internet exposure") if n == 0 else ("unknown", f"value '{v}'"))
    if rule == "one":
        return ("pass", "set") if n == 1 else (("warn", "not set; the default applies") if low == "unset" else ("fail", f"value {v}"))
    if rule == "zero":
        return ("pass", "off") if n == 0 else (("fail", "not turned off (absent means on)") if low == "unset" else ("fail", f"value {v}"))
    if rule == "netbios":
        vals = [x.strip() for x in v.split(",") if x.strip()]
        if not vals or low == "unset":
            return "unknown", "no active adapters were read"
        return ("pass", "disabled on every active adapter") if all(x == "2" for x in vals) else ("warn", "enabled or DHCP-controlled on at least one adapter (0 = DHCP, 1 = on, 2 = off)")
    if rule == "admins":
        names = [x for x in v.split(";") if x]
        if not names:
            return "unknown", "no members read"
        return ("pass", f"{len(names)} member(s): {', '.join(names)}") if len(names) <= 2 else ("warn", f"{len(names)} members: {', '.join(names)}. Does everyone here need it?")
    if rule == "asr":
        return ("pass", f"{n} rule(s) configured") if n and n > 0 else (("fail", "no rules configured") if n == 0 else ("unknown", f"value '{v}'"))
    if rule == "patch":
        if n is None:
            return "unknown", "no update date read"
        return ("pass", f"{n} days ago") if n <= 45 else (("warn", f"{n} days ago") if n <= 90 else ("fail", f"{n} days ago: well behind"))
    if rule == "seclog":
        return ("pass", f"{n} MB") if n is not None and n >= 192 else (("warn", f"{n} MB: small") if n is not None else ("unknown", f"value '{v}'"))
    if rule == "macro":
        return ("pass", "blocked by policy") if n == 1 else (("warn", "no policy set: relies on the product default") if low == "unset" else ("fail", "macros from the internet are allowed"))
    return "unknown", "no rule"


def grade(text: str) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise EndpointError("Paste the output of the script first.")
    if len(text) > MAX_CHARS:
        raise EndpointError("That is over 100,000 characters; paste only the script's output.", 413)
    found, ignored = {}, 0
    for raw in text.splitlines():
        m = re.match(r"^\s*([a-z0-9_]+)\s*[=:]\s*(.*?)\s*$", raw, re.I)
        if not m:
            continue
        k = m.group(1).lower()
        if k in IDS:
            found[k] = m.group(2)
        else:
            ignored += 1
    if not found:
        raise EndpointError("I found no result lines. The script prints lines like smb1=False; paste its output as it appeared.")
    rows, got, total = [], 0, 0
    for cid, title, sevr, _e, rule, why, fix, admin in CHECKS:
        if cid not in found:
            rows.append({"id": cid, "title": title, "severity": sevr, "status": "missing", "value": None, "note": "Not in the pasted output.", "why": why, "fix": fix})
            continue
        status, note = _judge(rule, found[cid])
        if status != "unknown":
            total += sevr
            got += sevr if status == "pass" else (sevr * 0.5 if status == "warn" else 0)
        rows.append({"id": cid, "title": title, "severity": sevr, "status": status, "value": found[cid], "note": note, "why": why, "fix": fix})
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in ("pass", "warn", "fail", "unknown", "missing")}
    order = {"fail": 0, "warn": 1, "unknown": 2, "missing": 3, "pass": 4}
    todo = sorted((r for r in rows if r["status"] in ("fail", "warn")), key=lambda r: (order[r["status"]], -r["severity"]))[:5]
    return {"score_pct": round(100 * got / total) if total else None, "counts": counts, "rows": rows, "ignored_lines": ignored,
            "start_with": [{"id": r["id"], "title": r["title"], "status": r["status"], "fix": r["fix"]} for r in todo],
            "lesson": "Hardening means removing what attackers rely on: old protocols, weak authentication, open remote access, excess admin rights and missed patches. Fix the high-severity failures first, one at a time, on a test machine, with a way back.",
            "limit": "Reads one Windows PC from a script you ran. It does not scan a network, see Group Policy that has not yet applied, check MFA, backups or your other security tools, and a pass is not a guarantee. Some checks need administrator rights; 'unknown' means the setting could not be read."}


SLIPS = [
    "The guide opens with industry-size figures ('$166B, more than double by 2028') but cites no source; treat the number as marketing.",
    "'The $50M ransomware attack on Acer' mixes up two things: $50 million was the ransom the REvil group demanded in 2021, not what the attack cost. The reported entry point was unpatched Microsoft Exchange, which the guide states correctly.",
    "The LockBit 'five-month access to a U.S. government agency via exposed RDP' line is given without a link or date, so I couldn't verify it; check the original advisory before repeating it.",
    "The Colonial Pipeline summary ('inactive account without MFA') is shorthand: the reported entry was a leftover VPN account with a leaked password and no MFA.",
    "'LanMan authentication level must be NTLMv2 only, and refuse LM and NTLM' reads as if all NTLM were blocked. Level 5 refuses LM and NTLMv1 responses; NTLMv2 is still allowed.",
    "'Disable DNS Multicast' means LLMNR only. mDNS is a separate multicast name service worth a look on current Windows.",
    "SmartScreen and 'Application Guard' advice is dated: Microsoft deprecated Defender Application Guard for Edge, so check its current status before building a plan on it.",
    "'InfoSec Twitter (start here)' as a first resource is dated (the platform is now X and the community has scattered). The list also repeats SimplyCyber as both a community and a PowerShell 2.0 reference.",
    "It's titled a checklist but has no pass or fail criteria, owners or order; every item is a link to read. The audit tab here turns the technical items into checks with a verdict.",
    "Gaps for an 'essentials' list: no mention of MFA on every account, disk encryption, backups you have tested, an endpoint detection product, LAPS for local admin passwords, or application allow-listing (WDAC or AppLocker).",
    "The closing section is a vendor advertisement (NinjaOne). Nothing from it is copied here.",
]
NOT_BUILT = ["Running anything on your PC or reading it remotely; you run the script yourself.", "Group Policy or Intune deployment, fleet reporting, an RMM product.", "macOS and Linux baselines (CIS benchmarks) beyond a note in the agent notes."]


def reference() -> dict:
    return {"checks": [{"id": c[0], "title": c[1], "severity": c[2], "why": c[5], "fix": c[6], "needs_admin": c[7]} for c in CHECKS],
            "process": ["Identify the risk", "Judge likelihood and impact", "Write the configuration change", "Test it on one machine and verify", "Deploy in phases with a backout plan", "Document the change and the exceptions", "Monitor that it holds"],
            "slips": SLIPS, "not_built": NOT_BUILT, "sample": SAMPLE}


SAMPLE = """smb1=False
ps2=Enabled
tls10=default
tls11=disabled
lmlevel=3
wdigest=unset
secureboot=True
bitlocker=Off
fw_domain=True
fw_private=True
fw_public=False
rdp=0
nla=1
llmnr=unset
netbios=0
smnr=unset
uac=1
admins=PC\\Administrator;PC\\Sam;PC\\Pat;PC\\Lee
credguard=False
defender_rt=True
asr=0
patch_age=63
seclog=20
excel_macros=unset
"""
