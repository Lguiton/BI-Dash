"""The fixed catalogue of things computer control can do on Windows, as PowerShell scripts.

Safety rules baked in here:
* Nothing is ever built from free text. Every script is a constant; the only inputs are validated parameters, passed as
  environment variables (BI_P_<name>) and read with $env:, never pasted into the script text, so they cannot become code.
* Anything that changes state may have a `capture` script (records the prior state) and a `restore` script (puts it back),
  which is how Undo, the auto-revert timer and "undo everything" work.
* Dangerous services and the account you are signed in with are refused.

These scripts were written without a Windows machine to run them on. That is why every action can be previewed (the exact
text is shown before it runs) and why Practice mode only simulates.
"""
from __future__ import annotations

import ipaddress
import re

PRE = "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'\n"
J = "| ConvertTo-Json -Compress -Depth 5"

NAME_RE = re.compile(r"^[A-Za-z0-9_.()\- ]{1,64}$")
HOST_RE = re.compile(r"^(?=.{1,253}$)[A-Za-z0-9]([A-Za-z0-9.\-]*[A-Za-z0-9])?$")
WINGET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-+_]{1,100}$")
PROTECTED_SERVICES = {
    "rpcss", "dcomlaunch", "lsm", "samss", "eventlog", "windefend", "wdnissvc", "sense", "mpssvc", "bfe", "winmgmt", "cryptsvc",
    "trustedinstaller", "power", "profsvc", "schedule", "plugplay", "brokerinfrastructure", "systemeventsbroker", "coremessagingregistrar",
    "wscsvc", "securityhealthservice", "lanmanworkstation", "dnscache", "nsi", "netprofm", "nlasvc", "gpsvc", "keyiso", "lsass",
}
POWER_PLANS = {"balanced": "381b4222-f694-41f0-9685-ff5bb260df2e", "high": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", "saver": "a1841308-3541-4fab-bc81-f71556f20b4a"}


class ParamError(ValueError):
    pass


def _name(v: str, label: str) -> str:
    v = (v or "").strip()
    if not NAME_RE.match(v):
        raise ParamError(f"{label}: use letters, numbers, spaces and . _ - ( ) only, up to 64 characters.")
    return v


def validate(spec: dict, raw) -> str:
    """Return the cleaned string for one parameter or raise ParamError."""
    kind, label = spec["kind"], spec["label"]
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        if spec.get("required", True):
            raise ParamError(f"{label} is required.")
        return ""
    v = str(raw).strip()
    if kind == "name":
        return _name(v, label)
    if kind == "service":
        _name(v, label)
        if v.lower() in PROTECTED_SERVICES:
            raise ParamError(f"{label}: '{v}' is a protected Windows service and can't be changed here.")
        return v
    if kind == "enum":
        if v not in spec["options"]:
            raise ParamError(f"{label} must be one of: {', '.join(spec['options'])}.")
        return v
    if kind == "ip":
        try:
            return str(ipaddress.ip_address(v))
        except ValueError:
            raise ParamError(f"{label} must be an IP address like 192.168.1.1.") from None
    if kind == "iplist":
        parts = [p.strip() for p in v.replace(" ", ",").split(",") if p.strip()]
        if not 1 <= len(parts) <= 3:
            raise ParamError(f"{label}: give one to three IP addresses.")
        try:
            return ",".join(str(ipaddress.ip_address(p)) for p in parts)
        except ValueError:
            raise ParamError(f"{label} must be IP addresses separated by commas.") from None
    if kind == "hostname":
        if not HOST_RE.match(v) or v.lower() == "localhost":
            raise ParamError(f"{label} must be a host name like example.com.")
        return v.lower()
    if kind == "winget":
        if not WINGET_RE.match(v):
            raise ParamError(f"{label} must look like Publisher.App (for example 7zip.7zip).")
        return v
    if kind == "password":
        if not 8 <= len(v) <= 128 or any(ord(c) < 32 for c in v):
            raise ParamError(f"{label} must be 8 to 128 printable characters.")
        return v
    raise ParamError(f"Unknown parameter kind {kind}.")


def P(name, label, kind, **kw):
    return {"name": name, "label": label, "kind": kind, **kw}


def A(id_, cat, title, what, risk, script, *, read=False, params=(), admin=False, capture=None, restore=None, revert_after=None,
      typed=False, timeout=120, restore_point=False, note="", scan=False):
    return {"id": id_, "cat": cat, "title": title, "what": what, "risk": risk, "read": read, "params": list(params), "admin": admin,
            "script": PRE + script, "capture": (PRE + capture) if capture else None, "restore": (PRE + restore) if restore else None,
            "revert_after": revert_after, "typed": typed, "timeout": timeout, "restore_point": restore_point, "note": note, "scan": scan}


SVC = P("name", "Service name", "service")
ADAPTER = P("adapter", "Network adapter name", "name")
USER = P("name", "User name", "name")
SVC_CAPTURE = '$s=Get-Service -Name $env:BI_P_name; @{name=$s.Name; status="$($s.Status)"; start="$($s.StartType)"} ' + J
SVC_RESTORE = """$u=$env:BI_UNDO | ConvertFrom-Json
if ($u.start -in 'Automatic','Manual','Disabled') { Set-Service -Name $u.name -StartupType $u.start }
if ($u.status -eq 'Running') { Start-Service -Name $u.name } elseif ($u.status -eq 'Stopped') { Stop-Service -Name $u.name -Force }
"Restored $($u.name)."
"""
RUNKEY = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
HOSTS = '"$env:SystemRoot\\System32\\drivers\\etc\\hosts"'

ACTIONS: list[dict] = [
    # ------------------------------------------------------------ maintenance
    A("system_summary", "maintenance", "System summary", "Windows version, uptime, memory and disk space.", "low", """
$os=Get-CimInstance Win32_OperatingSystem; $cs=Get-CimInstance Win32_ComputerSystem
$disks=@(Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object { @{drive=$_.DeviceID; size_gb=[math]::Round($_.Size/1GB,1); free_gb=[math]::Round($_.FreeSpace/1GB,1)} })
@{computer=$env:COMPUTERNAME; user=$env:USERNAME; os=$os.Caption; version=$os.Version; booted=$os.LastBootUpTime.ToString('s'); ram_gb=[math]::Round($cs.TotalPhysicalMemory/1GB,1); free_ram_gb=[math]::Round($os.FreePhysicalMemory/1MB,1); disks=$disks} """ + J, read=True),
    A("hotfixes", "maintenance", "Recent Windows updates", "The 15 most recently installed updates.", "low",
      "Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 15 HotFixID,Description,@{n='InstalledOn';e={\"$($_.InstalledOn)\"}} " + J, read=True),
    A("temp_size", "maintenance", "How much is in the temp folder", "Counts files and size in your Windows temp folder. Nothing is deleted.", "low", """
$f=@(Get-ChildItem $env:TEMP -Recurse -File -Force -ErrorAction SilentlyContinue)
@{path=$env:TEMP; files=$f.Count; mb=[math]::Round((($f | Measure-Object Length -Sum).Sum)/1MB,1)} """ + J, read=True),
    A("clear_temp", "maintenance", "Clear old temp files", "Deletes files in your temp folder that are over 2 days old. Files in use are skipped. Can't be undone.", "medium", """
$old=@(Get-ChildItem $env:TEMP -Recurse -File -Force -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-2) })
$mb=[math]::Round((($old | Measure-Object Length -Sum).Sum)/1MB,1)
$old | Remove-Item -Force -ErrorAction SilentlyContinue
"Tried to remove $($old.Count) files ($mb MB)."
""", note="Irreversible."),
    A("empty_recycle", "maintenance", "Empty the Recycle Bin", "Permanently deletes what is in the Recycle Bin. Can't be undone.", "medium",
      "Clear-RecycleBin -Force -ErrorAction SilentlyContinue; 'Recycle Bin emptied.'", note="Irreversible."),
    A("flush_dns", "maintenance", "Flush the DNS cache", "Forgets cached name lookups. Fixes stale-name problems. Harmless.", "low", "Clear-DnsClientCache; 'DNS cache cleared.'"),
    A("restart_spooler", "maintenance", "Restart the print spooler", "Clears most stuck print queues.", "low", "Restart-Service -Name Spooler -Force; (Get-Service Spooler).Status.ToString()", admin=True),
    A("sfc_verify", "maintenance", "Check system files (read only)", "sfc /verifyonly: looks for damaged Windows files and repairs nothing. Takes several minutes.", "low",
      "sfc /verifyonly | Out-String", read=True, admin=True, timeout=1500),
    A("dism_check", "maintenance", "Check the Windows image", "DISM /CheckHealth: quick check for corruption. Repairs nothing.", "low",
      "DISM /Online /Cleanup-Image /CheckHealth | Out-String", read=True, admin=True, timeout=600),
    A("disk_scan", "maintenance", "Scan the C: drive for errors", "Repair-Volume -Scan: an online read-only scan.", "low",
      "Repair-Volume -DriveLetter C -Scan | Out-String", read=True, admin=True, timeout=1800),
    A("restore_point", "maintenance", "Create a Windows restore point", "Saves a system restore point you can roll back to from Windows. Needs System Protection turned on, and Windows allows one every 24 hours.", "low",
      "Checkpoint-Computer -Description 'BI Dashboard restore point' -RestorePointType MODIFY_SETTINGS; 'Restore point requested.'", admin=True, timeout=300),
    # ------------------------------------------------------------ settings and services
    A("service_list", "settings", "List services", "Running services and anything set to start automatically.", "low",
      "Get-Service | Where-Object { $_.Status -eq 'Running' -or $_.StartType -eq 'Automatic' } | Select-Object Name,DisplayName,@{n='Status';e={\"$($_.Status)\"}},@{n='StartType';e={\"$($_.StartType)\"}} " + J, read=True),
    A("service_start", "settings", "Start a service", "Starts one Windows service. Critical system services are refused.", "medium",
      "$s=Get-Service -Name $env:BI_P_name; Start-Service -InputObject $s; (Get-Service -Name $env:BI_P_name).Status.ToString()", params=[SVC], admin=True, capture=SVC_CAPTURE, restore=SVC_RESTORE),
    A("service_stop", "settings", "Stop a service", "Stops one Windows service. Critical system services are refused.", "medium",
      "$s=Get-Service -Name $env:BI_P_name; Stop-Service -InputObject $s -Force; (Get-Service -Name $env:BI_P_name).Status.ToString()", params=[SVC], admin=True, capture=SVC_CAPTURE, restore=SVC_RESTORE),
    A("service_restart", "settings", "Restart a service", "Stops then starts one service.", "medium",
      "$s=Get-Service -Name $env:BI_P_name; Restart-Service -InputObject $s -Force; (Get-Service -Name $env:BI_P_name).Status.ToString()", params=[SVC], admin=True, capture=SVC_CAPTURE, restore=SVC_RESTORE),
    A("service_startup", "settings", "Change when a service starts", "Automatic, Manual or Disabled.", "medium",
      "Set-Service -Name $env:BI_P_name -StartupType $env:BI_P_type; (Get-Service -Name $env:BI_P_name).StartType.ToString()",
      params=[SVC, P("type", "Start type", "enum", options=["Automatic", "Manual", "Disabled"])], admin=True, capture=SVC_CAPTURE, restore=SVC_RESTORE),
    A("firewall_status", "settings", "Firewall status", "Whether the Domain, Private and Public profiles are on.", "low",
      "Get-NetFirewallProfile | ForEach-Object { @{Name=$_.Name; Enabled=\"$($_.Enabled)\"} } " + J, read=True),
    A("firewall_set", "settings", "Turn the firewall on or off", "Changes Windows Firewall for one profile or all. Turning it off auto-reverts after 5 minutes unless you keep it.", "high",
      """$p = if ($env:BI_P_profile -eq 'All') { 'Domain','Private','Public' } else { $env:BI_P_profile }
Set-NetFirewallProfile -Profile $p -Enabled $(if ($env:BI_P_state -eq 'on') { 'True' } else { 'False' })
Get-NetFirewallProfile | ForEach-Object { "$($_.Name): $($_.Enabled)" }""",
      params=[P("profile", "Profile", "enum", options=["All", "Domain", "Private", "Public"]), P("state", "State", "enum", options=["on", "off"])], admin=True, typed=True,
      capture="Get-NetFirewallProfile | ForEach-Object { @{Name=$_.Name; Enabled=\"$($_.Enabled)\"} } " + J,
      restore="$u=$env:BI_UNDO | ConvertFrom-Json\nforeach ($x in @($u)) { Set-NetFirewallProfile -Profile $x.Name -Enabled $x.Enabled }\n'Firewall restored.'", revert_after=300, restore_point=True),
    A("power_plan", "settings", "Switch the power plan", "Balanced, High performance or Power saver.", "low",
      "powercfg /setactive $env:BI_P_plan_guid; powercfg /getactivescheme",
      params=[P("plan_guid", "Plan", "enum", options=list(POWER_PLANS.values()), labels=dict((v, k) for k, v in POWER_PLANS.items()))],
      capture="$m=[regex]::Match((powercfg /getactivescheme | Out-String),'[0-9a-fA-F-]{36}'); @{guid=$m.Value} " + J,
      restore="$u=$env:BI_UNDO | ConvertFrom-Json\nif ($u.guid -match '^[0-9a-fA-F-]{36}$') { powercfg /setactive $u.guid }\n'Power plan restored.'"),
    A("startup_list", "settings", "List startup programs", "Programs that start with Windows (your Run key and the Startup folders).", "low",
      "Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run','HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -ErrorAction SilentlyContinue | "
      "ForEach-Object { $_.PSObject.Properties | Where-Object { $_.Name -notlike 'PS*' } | ForEach-Object { @{name=$_.Name; command=[string]$_.Value} } } " + J, read=True),
    A("startup_disable", "settings", "Stop a startup program (your account)", "Removes one entry from your own Run key. The command is saved so Undo puts it back.", "medium",
      f"Remove-ItemProperty -Path '{RUNKEY}' -Name $env:BI_P_name; 'Removed.'", params=[P("name", "Entry name", "name")],
      capture=f"$k=$env:BI_P_name; @{{name=$k; value=[string](Get-ItemProperty -Path '{RUNKEY}' -Name $k).$k}} " + J,
      restore=f"$u=$env:BI_UNDO | ConvertFrom-Json\nSet-ItemProperty -Path '{RUNKEY}' -Name $u.name -Value $u.value\n'Entry restored.'"),
    # ------------------------------------------------------------ network
    A("adapters_list", "network", "List network adapters", "Adapters, state, speed and MAC address.", "low",
      "Get-NetAdapter | Select-Object Name,InterfaceDescription,@{n='Status';e={\"$($_.Status)\"}},LinkSpeed,MacAddress " + J, read=True),
    A("ip_config", "network", "Show IP settings", "Address, gateway and DNS servers for each connected adapter.", "low",
      "Get-NetIPConfiguration | ForEach-Object { @{alias=$_.InterfaceAlias; ipv4=@($_.IPv4Address.IPAddress); gateway=@($_.IPv4DefaultGateway.NextHop); dns=@($_.DNSServer.ServerAddresses)} } " + J, read=True),
    A("ip_renew", "network", "Release and renew the IP address", "Drops your DHCP address and asks for a new one. The connection blips for a few seconds.", "medium",
      "ipconfig /release | Out-Null; ipconfig /renew | Out-String", admin=True, timeout=120),
    A("dns_set", "network", "Set DNS servers on an adapter", "For example 1.1.1.1,1.0.0.1. Auto-reverts after 3 minutes unless you keep it, so a wrong DNS can't strand you.", "medium",
      "Set-DnsClientServerAddress -InterfaceAlias $env:BI_P_adapter -ServerAddresses ($env:BI_P_servers -split ','); 'DNS set.'",
      params=[ADAPTER, P("servers", "DNS servers", "iplist")], admin=True, revert_after=180,
      capture="@{adapter=$env:BI_P_adapter; servers=@((Get-DnsClientServerAddress -InterfaceAlias $env:BI_P_adapter -AddressFamily IPv4).ServerAddresses)} " + J,
      restore="$u=$env:BI_UNDO | ConvertFrom-Json\nif (@($u.servers).Count -eq 0) { Set-DnsClientServerAddress -InterfaceAlias $u.adapter -ResetServerAddresses } else { Set-DnsClientServerAddress -InterfaceAlias $u.adapter -ServerAddresses @($u.servers) }\n'DNS restored.'"),
    A("dns_auto", "network", "Set DNS back to automatic", "Lets the router hand out DNS again.", "low",
      "Set-DnsClientServerAddress -InterfaceAlias $env:BI_P_adapter -ResetServerAddresses; 'DNS is automatic.'", params=[ADAPTER], admin=True,
      capture="@{adapter=$env:BI_P_adapter; servers=@((Get-DnsClientServerAddress -InterfaceAlias $env:BI_P_adapter -AddressFamily IPv4).ServerAddresses)} " + J,
      restore="$u=$env:BI_UNDO | ConvertFrom-Json\nif (@($u.servers).Count -eq 0) { Set-DnsClientServerAddress -InterfaceAlias $u.adapter -ResetServerAddresses } else { Set-DnsClientServerAddress -InterfaceAlias $u.adapter -ServerAddresses @($u.servers) }\n'DNS restored.'"),
    A("adapter_disable", "network", "Disable a network adapter", "Turns an adapter off. Auto-reverts after 2 minutes unless you keep it.", "high",
      "Disable-NetAdapter -Name $env:BI_P_adapter -Confirm:$false; 'Disabled.'", params=[ADAPTER], admin=True, typed=True, revert_after=120,
      capture="@{adapter=$env:BI_P_adapter; status=\"$((Get-NetAdapter -Name $env:BI_P_adapter).Status)\"} " + J,
      restore="$u=$env:BI_UNDO | ConvertFrom-Json\nif ($u.status -eq 'Up') { Enable-NetAdapter -Name $u.adapter -Confirm:$false } else { Disable-NetAdapter -Name $u.adapter -Confirm:$false }\n'Adapter restored.'"),
    A("adapter_enable", "network", "Enable a network adapter", "Turns an adapter back on.", "low",
      "Enable-NetAdapter -Name $env:BI_P_adapter -Confirm:$false; 'Enabled.'", params=[ADAPTER], admin=True,
      capture="@{adapter=$env:BI_P_adapter; status=\"$((Get-NetAdapter -Name $env:BI_P_adapter).Status)\"} " + J,
      restore="$u=$env:BI_UNDO | ConvertFrom-Json\nif ($u.status -eq 'Up') { Enable-NetAdapter -Name $u.adapter -Confirm:$false } else { Disable-NetAdapter -Name $u.adapter -Confirm:$false }\n'Adapter restored.'"),
    A("hosts_view", "network", "Show the hosts file", "The local name overrides. Unexpected lines can redirect websites.", "low", f"Get-Content {HOSTS} -Raw", read=True),
    A("hosts_add", "network", "Add a hosts file entry", "Maps a name to an address on this computer (for example to block a site with 0.0.0.0). The whole file is saved first so Undo restores it.", "medium",
      f"$f={HOSTS}; Add-Content -Path $f -Value (\"{{0}}`t{{1}}\" -f $env:BI_P_ip,$env:BI_P_hostname) -Encoding ASCII; 'Added.'",
      params=[P("ip", "Address", "ip"), P("hostname", "Host name", "hostname")], admin=True,
      capture=f"$f={HOSTS}; @{{content=[Convert]::ToBase64String([IO.File]::ReadAllBytes($f))}} " + J,
      restore=f"$u=$env:BI_UNDO | ConvertFrom-Json\n$f={HOSTS}; [IO.File]::WriteAllBytes($f,[Convert]::FromBase64String($u.content)); 'Hosts file restored.'"),
    A("hosts_remove", "network", "Remove a hosts file entry", "Removes lines mapping a host name. Comments are never touched. The file is saved first.", "medium",
      f"$f={HOSTS}; $keep=Get-Content $f | Where-Object {{ $_ -match '^\\s*#' -or $_ -notmatch ('\\s' + [regex]::Escape($env:BI_P_hostname) + '(\\s|$)') }}; Set-Content -Path $f -Value $keep -Encoding ASCII; 'Removed.'",
      params=[P("hostname", "Host name", "hostname")], admin=True,
      capture=f"$f={HOSTS}; @{{content=[Convert]::ToBase64String([IO.File]::ReadAllBytes($f))}} " + J,
      restore=f"$u=$env:BI_UNDO | ConvertFrom-Json\n$f={HOSTS}; [IO.File]::WriteAllBytes($f,[Convert]::FromBase64String($u.content)); 'Hosts file restored.'"),
    A("reset_stack", "network", "Reset the network stack", "netsh winsock reset and netsh int ip reset. Fixes deep network corruption. Needs a restart and can't be undone.", "high",
      "netsh winsock reset | Out-String; netsh int ip reset | Out-String; 'Restart the computer to finish.'", admin=True, typed=True, restore_point=True, note="Irreversible."),
    # ------------------------------------------------------------ accounts and software
    A("users_list", "accounts", "List local users", "Local accounts and whether they are enabled.", "low",
      "Get-LocalUser | Select-Object Name,Enabled,PasswordRequired,@{n='LastLogon';e={\"$($_.LastLogon)\"}},@{n='PasswordLastSet';e={\"$($_.PasswordLastSet)\"}} " + J, read=True),
    A("admins_list", "accounts", "List administrators", "Who is in the local Administrators group.", "low",
      "Get-LocalGroupMember -SID S-1-5-32-544 | Select-Object Name,@{n='ObjectClass';e={\"$($_.ObjectClass)\"}},@{n='Source';e={\"$($_.PrincipalSource)\"}} " + J, read=True),
    A("user_disable", "accounts", "Disable a local user", "Turns an account off without deleting it. You can't disable the account you are signed in with.", "medium",
      "if ($env:BI_P_name -eq $env:USERNAME) { throw 'Refusing to disable the account you are signed in with.' }; Disable-LocalUser -Name $env:BI_P_name; 'Disabled.'",
      params=[USER], admin=True, capture="$u=Get-LocalUser -Name $env:BI_P_name; @{name=$u.Name; enabled=[bool]$u.Enabled} " + J,
      restore="$u=$env:BI_UNDO | ConvertFrom-Json\nif ($u.enabled) { Enable-LocalUser -Name $u.name } else { Disable-LocalUser -Name $u.name }\n'Account restored.'"),
    A("user_enable", "accounts", "Enable a local user", "Turns a disabled account back on.", "medium",
      "Enable-LocalUser -Name $env:BI_P_name; 'Enabled.'", params=[USER], admin=True,
      capture="$u=Get-LocalUser -Name $env:BI_P_name; @{name=$u.Name; enabled=[bool]$u.Enabled} " + J,
      restore="$u=$env:BI_UNDO | ConvertFrom-Json\nif ($u.enabled) { Enable-LocalUser -Name $u.name } else { Disable-LocalUser -Name $u.name }\n'Account restored.'"),
    A("user_create", "accounts", "Create a standard local user", "Makes a normal (not administrator) account. The password goes straight to Windows and is never saved or logged.", "high",
      "$pw=ConvertTo-SecureString $env:BI_P_password -AsPlainText -Force; New-LocalUser -Name $env:BI_P_name -Password $pw -AccountNeverExpires | Out-Null; Add-LocalGroupMember -SID S-1-5-32-545 -Member $env:BI_P_name; 'Created standard user.'",
      params=[USER, P("password", "Password", "password", secret=True)], admin=True, typed=True,
      capture="@{name=$env:BI_P_name} " + J, restore="$u=$env:BI_UNDO | ConvertFrom-Json\nRemove-LocalUser -Name $u.name\n'User removed.'"),
    A("winget_list", "accounts", "List installed software", "Programs winget knows about.", "low", "winget list --accept-source-agreements | Out-String", read=True, timeout=300),
    A("winget_install", "accounts", "Install a program with winget", "winget install by ID, silently. Undo uninstalls it again.", "high",
      "winget install --id $env:BI_P_id -e --silent --accept-package-agreements --accept-source-agreements | Out-String", params=[P("id", "winget ID", "winget")], admin=True, typed=True, timeout=1800,
      capture="@{id=$env:BI_P_id} " + J, restore="$u=$env:BI_UNDO | ConvertFrom-Json\nwinget uninstall --id $u.id -e --silent | Out-String"),
    A("winget_uninstall", "accounts", "Uninstall a program with winget", "winget uninstall by ID. Can't be undone here (reinstall it with winget).", "high",
      "winget uninstall --id $env:BI_P_id -e --silent | Out-String", params=[P("id", "winget ID", "winget")], admin=True, typed=True, timeout=1800, restore_point=True, note="Not undoable here."),
    A("winget_upgrade_all", "accounts", "Update every program", "winget upgrade --all, silently. Can't be undone here.", "high",
      "winget upgrade --all --silent --accept-package-agreements --accept-source-agreements | Out-String", admin=True, typed=True, timeout=3600, restore_point=True, note="Not undoable here."),
]


# ---------------------------------------------------------------- security scans (read only; analysed in sysscan.py)
SIG = """function Get-Sig($c) {
  $c=[Environment]::ExpandEnvironmentVariables([string]$c)
  if ($c -match '^\\s*"([^"]+)"') { $exe=$matches[1] } else { $exe=($c -split '\\s+')[0] }
  if (-not $exe -or -not (Test-Path -LiteralPath $exe -PathType Leaf -ErrorAction SilentlyContinue)) { return @{exe=$exe; sig='Missing'; publisher=''} }
  try { $s=Get-AuthenticodeSignature -LiteralPath $exe; $pub=''; if ($s.SignerCertificate) { $pub=$s.SignerCertificate.Subject }; return @{exe=$exe; sig="$($s.Status)"; publisher=$pub} } catch { return @{exe=$exe; sig='UnknownError'; publisher=''} }
}
"""
ACTIONS += [
    A("scan_startup", "security", "Scan startup items", "Run keys, Startup folders and non-Microsoft scheduled tasks, each checked for a digital signature.", "low", SIG + """
$out=New-Object System.Collections.ArrayList
foreach ($k in 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run','HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run','HKLM:\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Run') {
  if (Test-Path $k) { $p=Get-ItemProperty $k; foreach ($n in ($p.PSObject.Properties | Where-Object { $_.Name -notlike 'PS*' })) { [void]$out.Add(@{where=$k; name=$n.Name; command=[string]$n.Value}) } } }
foreach ($d in "$env:APPDATA\\Microsoft\\Windows\\Start Menu\\Programs\\Startup","$env:ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\StartUp") {
  if (Test-Path $d) { Get-ChildItem $d -File -ErrorAction SilentlyContinue | ForEach-Object { [void]$out.Add(@{where=$d; name=$_.Name; command=$_.FullName}) } } }
Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.State -ne 'Disabled' -and $_.TaskPath -notlike '\\Microsoft\\*' } | ForEach-Object {
  $a=$_.Actions | Select-Object -First 1; if ($a) { [void]$out.Add(@{where='scheduled task'; name=($_.TaskPath + $_.TaskName); command=(("$($a.Execute) $($a.Arguments)").Trim())}) } }
$res=foreach ($i in $out) { $g=Get-Sig $i.command; @{where=$i.where; name=$i.name; command=$i.command; exe=$g.exe; sig=$g.sig; publisher=$g.publisher} }
@($res) """ + J, read=True, scan=True, timeout=300),
    A("scan_processes", "security", "Scan running programs", "Every running program with a file path, checked for a digital signature (one line per file).", "low", SIG + """
$seen=@{}; $res=@()
foreach ($p in (Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path } | Sort-Object Path)) {
  if ($seen.ContainsKey($p.Path)) { $seen[$p.Path].count++; continue }
  $g=Get-Sig ('"' + $p.Path + '"'); $o=@{name=$p.Name; path=$p.Path; sig=$g.sig; publisher=$g.publisher; count=1}; $seen[$p.Path]=$o; $res+=$o
  if ($res.Count -ge 250) { break } }
@($res) """ + J, read=True, scan=True, timeout=600),
    A("scan_network", "security", "Scan network connections", "Programs listening for connections and programs talking to the internet, with the process behind each.", "low", """
$conn=@(Get-NetTCPConnection -State Listen,Established -ErrorAction SilentlyContinue)
$map=@{}
foreach ($i in ($conn | Select-Object -ExpandProperty OwningProcess -Unique)) { try { $p=Get-Process -Id $i -ErrorAction Stop; $map[[int]$i]=@{name=$p.Name; path=$p.Path} } catch {} }
$res=foreach ($c in $conn) { $m=$map[[int]$c.OwningProcess]; @{state="$($c.State)"; laddr=$c.LocalAddress; lport=$c.LocalPort; raddr=$c.RemoteAddress; rport=$c.RemotePort; pid=$c.OwningProcess; proc=$m.name; path=$m.path} }
@($res) """ + J, read=True, scan=True, admin=True, timeout=300),
    A("scan_remote", "security", "Scan for remote-access tools", "Remote desktop settings, shared folders, and well-known remote-control programs (AnyDesk, TeamViewer, VNC and similar).", "low", """
$names='anydesk','teamviewer','rustdesk','screenconnect','connectwise','logmein','vnc','splashtop','ammyy','supremo','radmin','dwservice','parsec','remoteutilities','zohoassist'
$procs=@(Get-Process -ErrorAction SilentlyContinue | Where-Object { $n=$_.Name.ToLower(); @($names | Where-Object { $n -like ('*' + $_ + '*') }).Count -gt 0 } | Select-Object Name,Id,Path)
$apps=@(Get-ItemProperty 'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*','HKLM:\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*','HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*' -ErrorAction SilentlyContinue | Where-Object { $d=[string]$_.DisplayName; $d -and @($names | Where-Object { $d.ToLower() -like ('*' + $_ + '*') }).Count -gt 0 } | Select-Object DisplayName,DisplayVersion,Publisher)
$rdp=(Get-ItemProperty 'HKLM:\\System\\CurrentControlSet\\Control\\Terminal Server' -Name fDenyTSConnections -ErrorAction SilentlyContinue).fDenyTSConnections
$svc=@(Get-Service -Name TermService,WinRM,sshd -ErrorAction SilentlyContinue | ForEach-Object { @{name=$_.Name; status="$($_.Status)"; start="$($_.StartType)"} })
$shares=@(Get-SmbShare -ErrorAction SilentlyContinue | Where-Object { -not $_.Special } | Select-Object Name,Path)
@{processes=$procs; apps=$apps; rdp_enabled=($rdp -eq 0); services=$svc; shares=$shares} """ + J, read=True, scan=True, timeout=300),
    A("scan_privacy", "security", "Scan camera, microphone and location use", "Which programs have used your webcam, microphone or location, and whether one is using it right now (read from Windows' own privacy log).", "low", """
$base='HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\CapabilityAccessManager\\ConsentStore'
$res=@()
foreach ($cap in 'webcam','microphone','location') {
  foreach ($sub in @("$base\\$cap", "$base\\$cap\\NonPackaged")) {
    if (Test-Path $sub) { Get-ChildItem $sub -ErrorAction SilentlyContinue | ForEach-Object {
      $p=Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
      if ($p.LastUsedTimeStart) { $res += @{capability=$cap; app=$_.PSChildName; start=[int64]$p.LastUsedTimeStart; stop=[int64]$p.LastUsedTimeStop; nonpackaged=($sub -like '*NonPackaged')} } } } } }
@($res) """ + J, read=True, scan=True, timeout=120),
    A("scan_accounts", "security", "Scan user accounts", "Local accounts, administrators, the Guest account and accounts with no password.", "low", """
$users=@(Get-LocalUser | ForEach-Object { @{name=$_.Name; enabled=[bool]$_.Enabled; password_required=[bool]$_.PasswordRequired; last_logon="$($_.LastLogon)"} })
$admins=@(Get-LocalGroupMember -SID S-1-5-32-544 -ErrorAction SilentlyContinue | ForEach-Object { @{name=$_.Name; cls="$($_.ObjectClass)"; source="$($_.PrincipalSource)"} })
@{users=$users; admins=$admins} """ + J, read=True, scan=True, timeout=120),
    A("scan_system", "security", "Scan system protection and settings", "Antivirus and firewall state, recent detections, the hosts file, proxy settings and User Account Control.", "low", """
$def=$null; try { $d=Get-MpComputerStatus; $def=@{antivirus=[bool]$d.AntivirusEnabled; realtime=[bool]$d.RealTimeProtectionEnabled; signature_age_days=[int]$d.AntivirusSignatureAge; quick_scan_end="$($d.QuickScanEndTime)"} } catch {}
$threats=@(); try { $threats=@(Get-MpThreatDetection | Select-Object -First 15 | ForEach-Object { @{id=$_.ThreatID; at="$($_.InitialDetectionTime)"; process=$_.ProcessName; resources=@($_.Resources)} }) } catch {}
$fw=@(Get-NetFirewallProfile | ForEach-Object { @{name=$_.Name; enabled="$($_.Enabled)"} })
$hosts=@(Get-Content "$env:SystemRoot\\System32\\drivers\\etc\\hosts" -ErrorAction SilentlyContinue | Where-Object { $_ -notmatch '^\\s*#' -and $_.Trim() })
$ie=Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings' -ErrorAction SilentlyContinue
$uac=(Get-ItemProperty 'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\System' -Name EnableLUA -ErrorAction SilentlyContinue).EnableLUA
@{defender=$def; threats=$threats; firewall=$fw; hosts=$hosts; proxy_enabled=[bool]$ie.ProxyEnable; proxy_server=[string]$ie.ProxyServer; proxy_script=[string]$ie.AutoConfigURL; uac_enabled=($uac -eq 1)} """ + J, read=True, scan=True, timeout=120),
    A("defender_update", "security", "Update Defender signatures", "Downloads the latest Microsoft Defender definitions.", "low", "Update-MpSignature; 'Signatures updated.'", admin=True, timeout=600),
    A("defender_quick_scan", "security", "Run a Defender quick scan", "Starts a Microsoft Defender quick scan. This app is not an antivirus: it asks Windows' own to scan.", "low",
      "Start-MpScan -ScanType QuickScan; 'Quick scan finished. Check Windows Security for results.'", admin=True, timeout=3600),
    A("defender_full_scan", "security", "Run a Defender full scan", "A full scan can take hours and slow the computer.", "medium",
      "Start-MpScan -ScanType FullScan; 'Full scan finished. Check Windows Security for results.'", admin=True, timeout=14400),
]
BY_ID = {a["id"]: a for a in ACTIONS}
CATEGORIES = [("maintenance", "Maintenance and cleanup"), ("settings", "Settings and services"), ("network", "Network"), ("accounts", "Accounts and software"), ("security", "Security scans")]
SCAN_ORDER = ["scan_system", "scan_accounts", "scan_remote", "scan_privacy", "scan_startup", "scan_network", "scan_processes"]


def public(a: dict) -> dict:
    """What the browser may see: everything but the script text."""
    return {k: a[k] for k in ("id", "cat", "title", "what", "risk", "read", "params", "admin", "typed", "revert_after", "restore_point", "note", "scan", "timeout")} | {"undoable": bool(a["restore"])}
