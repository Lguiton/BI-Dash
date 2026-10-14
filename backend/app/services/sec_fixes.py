"""How to fix it: plain-English guides for every finding the Cybersecurity tools can raise, with steps, a way to check it worked, and what could go wrong.

A guide is text to read and follow yourself, on systems you own or are authorised to change. Nothing here changes a setting. Where a step changes something that could
break a program or lock you out, the caution says so; try one PC first. Search matches your words against titles, keywords and the steps themselves."""
from __future__ import annotations

import json
import re

FIXES: list[dict] = []
REF: dict[str, str] = {}      # a finding's ref (check id, header id, log id, checklist id) -> guide id


def _g(gid, title, area, keywords, why, steps, verify, minutes, caution="", tool="", refs=()):
    FIXES.append({"id": gid, "title": title, "area": area, "keywords": keywords, "why": why, "steps": list(steps), "verify": verify, "minutes": minutes, "caution": caution, "tool": tool})
    for r in refs:
        REF[r] = gid


PS = "Open Start, type PowerShell, right-click Windows PowerShell and choose Run as administrator."
# ------------------------------------------------------------------ Windows PC
_g("win-smb1", "Turn off SMB version 1", "Windows PC", "smb1 smb file sharing old protocol wannacry eternalblue", "SMB1 is an old file-sharing protocol that ransomware like WannaCry spread through.",
   [PS, "Run: Get-WindowsOptionalFeature -Online -FeatureName SMB1Protocol   (this shows whether it is on).", "Run: Disable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol", "Restart the PC when asked.",
    "Test that file sharing and any network scanner or old NAS you use still work."], "Re-run the hardening script: smb1 should read False.", 10,
   "Very old scanners, copiers and NAS boxes may only speak SMB1. Check them first; the better fix is updating or replacing them.", "Endpoint hardening tab", ("smb1",))
_g("win-ps2", "Turn off Windows PowerShell 2.0", "Windows PC", "powershell 2 ps2 downgrade attack logging", "PowerShell 2.0 lacks the logging and protections of newer versions, so attackers downgrade to it.",
   [PS, "Run: Disable-WindowsOptionalFeature -Online -FeatureName MicrosoftWindowsPowerShellV2Root", "Restart if asked."], "Re-run the script: ps2 should read Disabled.", 5, "Almost nothing modern needs it.", "Endpoint hardening tab", ("ps2",))
_g("win-tls", "Turn off old TLS 1.0 and 1.1", "Windows PC", "tls tls10 tls11 schannel old encryption", "TLS 1.0 and 1.1 are retired encryption versions with known weaknesses.",
   ["Open Registry Editor (regedit) as administrator and make a backup: File > Export.", r"Go to HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols.", "Create keys 'TLS 1.0' and 'TLS 1.1', each with a key named 'Server'.",
    "In each Server key add DWORD values Enabled = 0 and DisabledByDefault = 1.", "Restart the PC."], "Re-run the script: tls10 and tls11 should read off.", 20, "Very old software or devices that only speak TLS 1.0 will stop connecting. Test first.", "Endpoint hardening tab", ("tls10", "tls11"))
_g("win-lm", "Require NTLMv2 only (LAN Manager level 5)", "Windows PC", "lm ntlm ntlmv2 lan manager authentication level", "Old LM and NTLMv1 responses are easy to crack.",
   ["Press Win+R, type secpol.msc (Windows Pro) and open Local Policies > Security Options.", "Open 'Network security: LAN Manager authentication level'.", "Choose 'Send NTLMv2 response only. Refuse LM & NTLM'.", "Click OK and restart."], "Re-run the script: lmlevel should read 5.", 10,
   "Old printers and NAS devices that use NTLMv1 will fail to sign in. Note NTLMv2 itself still works.", "Endpoint hardening tab", ("lmlevel",))
_g("win-wdigest", "Stop WDigest keeping clear-text passwords", "Windows PC", "wdigest mimikatz credentials memory", "When on, a logged-in password can be read from memory by attack tools.",
   [r"Open regedit as administrator, go to HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\SecurityProviders\WDigest.", "Set the DWORD UseLogonCredential to 0 (or delete the value).", "Restart."], "Re-run the script: wdigest should read 0 or unset.", 5, "", "Endpoint hardening tab", ("wdigest",))
_g("win-secureboot", "Turn on Secure Boot", "Windows PC", "secure boot uefi firmware bootkit", "Stops tampered startup code from loading before Windows.",
   ["In Windows search type msinfo32 and check 'BIOS Mode' (must be UEFI) and 'Secure Boot State'.", "If BIOS Mode is Legacy, the disk must be converted first (Microsoft's mbr2gpt tool), after a full backup.", "Restart into firmware settings (hold Shift while clicking Restart > Troubleshoot > Advanced > UEFI Firmware Settings).", "Enable Secure Boot, save and exit."],
   "msinfo32 shows Secure Boot State: On.", 20, "Back up first. Converting a disk wrongly can stop the PC booting. Some very old hardware does not support it.", "Endpoint hardening tab", ("secureboot",))
_g("win-bitlocker", "Encrypt the drive (BitLocker)", "Windows PC", "bitlocker encryption disk encrypt laptop stolen recovery key", "A lost or stolen laptop should not hand over the data on it.",
   ["Open Settings > Privacy & security > Device encryption (Windows Home) or Control Panel > BitLocker Drive Encryption (Pro).", "Turn it on and choose to back up the recovery key to your Microsoft account or print it.", "Store the recovery key somewhere other than that PC (password manager or printed in a safe place).", "Let encryption finish; the PC stays usable."],
   "Re-run the script: bitlocker should read On, or run manage-bde -status.", 15, "Losing the recovery key can mean losing the data. Store it before you rely on it.", "Endpoint hardening tab", ("bitlocker", "disk_encryption"))
_g("win-firewall", "Turn the Windows firewall on for every profile", "Windows PC", "firewall domain private public windows defender firewall", "The firewall blocks unwanted incoming connections.",
   [PS, "Run: Set-NetFirewallProfile -Profile Domain,Private,Public -Enabled True", "If another security product manages the firewall, confirm that product's firewall is on instead."], "Re-run the script: fw_domain, fw_private and fw_public should read True.", 5, "", "Endpoint hardening tab", ("fw_domain", "fw_private", "fw_public"))
_g("win-rdp", "Turn off Remote Desktop (or lock it down)", "Windows PC", "rdp remote desktop 3389 ransomware brute force", "Open Remote Desktop is one of the most common ways ransomware gets in.",
   ["Open Settings > System > Remote Desktop and switch it Off if you do not use it.", "If you do need it: do not expose port 3389 to the internet. Put it behind a VPN, require Network Level Authentication and a strong password with 2FA.", "On the router, make sure there is no port-forward to 3389."], "Re-run the script: rdp should read off. Run the Local ports tab to confirm 3389 is closed.", 10, "Turning it off will stop remote support you rely on. Use a VPN-based tool instead.", "Endpoint hardening tab, Local ports", ("rdp",))
_g("win-nla", "Require Network Level Authentication for Remote Desktop", "Windows PC", "nla network level authentication rdp", "Makes a person sign in before the remote desktop session even starts.",
   ["Open System Properties > Remote tab.", "Tick 'Allow connections only from computers running Remote Desktop with Network Level Authentication'.", "Click OK."], "Re-run the script: nla should read on.", 3, "", "Endpoint hardening tab", ("nla",))
_g("win-namespoof", "Turn off LLMNR, NetBIOS and multi-homed name resolution", "Windows PC", "llmnr netbios nbt-ns smnr responder name spoofing poisoning", "These fallback name lookups can be answered by an attacker on the same network to capture password hashes.",
   ["LLMNR: Local Group Policy (gpedit.msc) > Computer Configuration > Administrative Templates > Network > DNS Client > Turn off multicast name resolution = Enabled.", "Multi-homed: same folder, 'Turn off smart multi-homed name resolution' = Enabled.", "NetBIOS: Network adapter properties > IPv4 > Advanced > WINS > Disable NetBIOS over TCP/IP.", "Restart and test that you can still reach file shares by name."],
   "Re-run the script: llmnr, netbios and smnr should read off.", 15, "Networks that rely on NetBIOS names for old devices may need those names added to DNS first.", "Endpoint hardening tab", ("llmnr", "netbios", "smnr"))
_g("win-uac", "Turn on User Account Control", "Windows PC", "uac user account control prompt admin elevation", "UAC asks before something changes the system, which stops silent malware installs.",
   ["Search 'Change User Account Control settings'.", "Move the slider to the default (second from the top) or the top.", "Restart."], "Re-run the script: uac should read on.", 3, "", "Endpoint hardening tab", ("uac",))
_g("win-admins", "Shrink the local Administrators group", "Windows PC", "administrators admin group standard user least privilege laps", "Malware running as an administrator can do much more damage than the same malware as a standard user.",
   ["Create a separate administrator account with a strong, unique password for maintenance.", "Open Settings > Accounts > Other users, pick the everyday account and choose Change account type > Standard User.", "Keep the admin password in your password manager; use it only when asked for elevation."], "Re-run the script: the Administrators count should be small (one or two).", 15,
   "Make sure the new admin account works before demoting the everyday one, or you can lock yourself out of changes.", "Endpoint hardening tab", ("admins", "standard_accounts"))
_g("win-credguard", "Turn on Credential Guard", "Windows PC", "credential guard device guard virtualization based security vbs", "Isolates sign-in secrets so tools cannot steal them from memory.",
   ["Check that the PC is Windows Pro/Enterprise with virtualization on in firmware.", "Open gpedit.msc > Computer Configuration > Administrative Templates > System > Device Guard > Turn On Virtualization Based Security.", "Set 'Credential Guard Configuration' to 'Enabled without lock', restart."], "Re-run the script: credguard should read running.", 20,
   "Some drivers and virtualisation software conflict. Test on one PC first.", "Endpoint hardening tab", ("credguard",))
_g("win-defender", "Turn on Defender real-time protection (or confirm your antivirus)", "Windows PC", "defender antivirus real-time protection malware", "Real-time protection stops common malware as it arrives.",
   ["Open Windows Security > Virus & threat protection > Manage settings and switch Real-time protection on.", "If it says another product manages protection, open that product and confirm it is on and its definitions are current.", "Run a Quick scan."], "Re-run the script: defender_rt should read On, or the other product shows green.", 5, "Run only one real-time antivirus at a time.", "Endpoint hardening tab", ("defender_rt", "antivirus"))
_g("win-asr", "Configure attack surface reduction rules", "Windows PC", "asr attack surface reduction rules office macros defender", "Blocks behaviour malware relies on, such as Office programs launching scripts.",
   [PS, "Run: Set-MpPreference -AttackSurfaceReductionRules_Ids <rule id> -AttackSurfaceReductionRules_Actions AuditMode  (start every rule in Audit mode).", "Watch the Defender events for a couple of weeks.", "Move rules that show no false alarms to Block (Actions Enabled)."], "Re-run the script: asr should show rules configured.", 30,
   "Blocking rules can stop legitimate macros and tools. Audit first.", "Endpoint hardening tab", ("asr",))
_g("win-patch", "Get updates installed", "Windows PC", "windows update patch age missing updates", "Most break-ins use holes that already have a fix.",
   ["Open Settings > Windows Update and click Check for updates.", "Install everything, restart, and check again until it says you are up to date.", "Turn on 'Get the latest updates as soon as they're available' and set active hours.", "Set a weekly reminder to restart the PC."], "Re-run the script: patch_age shows a recent date.", 30, "Save work first; some updates restart the PC.", "Endpoint hardening tab", ("patch_age", "updates"))
_g("win-seclog", "Enlarge the Windows security log", "Windows PC", "event log security log size forensic retention", "A tiny log overwrites the evidence of an attack within days.",
   [PS, "Run: wevtutil sl Security /ms:201326592", "If you can, forward important events to another machine or a logging service."], "Re-run the script: seclog should read 192 MB or more.", 3, "", "Endpoint hardening tab", ("seclog",))
_g("win-macros", "Block Office macros from the internet", "Windows PC", "excel word macros office vba internet mark of the web", "Macros in files from email or the web are a classic malware route.",
   ["Open gpedit.msc > User Configuration > Administrative Templates > Microsoft Excel (and Word) > Excel Options > Security > Trust Center > Block macros from running in Office files from the Internet = Enabled.", "Or in Excel: File > Options > Trust Center > Trust Center Settings > Macro Settings > Disable all macros with notification."],
   "Re-run the script: excel_macros should read blocked.", 5, "A workbook you rely on that uses macros will stop working until you store it in a trusted location.", "Endpoint hardening tab", ("excel_macros",))
# ------------------------------------------------------------------ owner checklist
_g("mfa-email", "Turn on two-step sign-in for email", "Accounts", "2fa mfa two step authenticator email gmail outlook", "Whoever controls the email can reset every other password.",
   ["Install an authenticator app (Microsoft Authenticator, Google Authenticator or a password manager's built-in one).", "Open the email account's security settings and choose 2-step verification, then 'authenticator app'.", "Scan the QR code, enter the 6-digit code, and save the backup/recovery codes.", "Print the recovery codes or store them in your password manager. Do not store them in the same email account.", "Sign out and back in to test."],
   "Sign in on a new browser: it asks for the app code.", 10, "Prefer the app to text-message codes; text codes can be stolen by SIM swapping.", "Checkup report checklist", ("mfa_email",))
_g("mfa-money", "Turn on two-step sign-in for money accounts", "Accounts", "2fa bank payment paypal accounting quickbooks stripe square", "These are the accounts thieves go for first.",
   ["List every account that can move or see money: bank, card issuer, payment apps, accounting, payroll, payment processor.", "In each, open Security settings and enable app-based 2FA (or a hardware key if offered).", "Save recovery codes per account.", "Set up alerts for sign-ins and transfers."], "Sign in on a new device; it asks for the second step.", 30, "", "Account inventory", ("mfa_money",))
_g("password-manager", "Set up a password manager", "Accounts", "password manager reuse unique bitwarden 1password keepass", "Reused passwords turn one leak into many break-ins.",
   ["Choose a reputable password manager and install it on the PC and phone.", "Create one long master passphrase (use the passphrase generator in the Crypto tab) and write it down once, keeping it somewhere safe.", "Turn on 2FA for the manager itself.", "Change passwords starting with email, then money, then everything else; let the manager generate them.", "Use its breach report to find reused and weak ones."],
   "The manager's security dashboard shows no reused passwords for key accounts.", 60, "Never lose the master passphrase; there is usually no reset.", "Crypto tab, Breach check", ("password_manager",))
_g("backup-set-up", "Set up automatic backups", "Backups", "backup backups data automatic ransomware 3-2-1", "Backups are the difference between a bad day and a business-ending one.",
   ["List what must be kept: customer files, accounting data, photos, email if local.", "Follow 3-2-1: three copies, two kinds of storage, one off-site.", "Pick tools: cloud backup service or File History/Backup to an external drive, set to run daily without you.", "Run the first backup and check the file count looks right.", "Add a reminder to test a restore (see 'Test a restore')."],
   "Open the backup tool and see last backup time within a day.", 45, "An external drive that is always plugged in can be encrypted by ransomware with everything else. Keep one copy unplugged or in the cloud.", "Backup restore tracker", ("backups_exist",))
_g("restore-test", "Test a restore", "Backups", "restore test backup verify recovery drill", "A backup you have never restored is a hope, not a plan.",
   ["Pick one file or folder at random from the backup.", "Restore it to a different location (not over the original).", "Open it and check it is complete and readable.", "Record the date and result in the Backup restore tracker.", "Once a quarter, restore a whole folder or a whole PC's key data to a spare machine."], "The tracker shows a recent successful test.", 15, "", "Backup restore tracker", ("backups_tested", "restore"))
_g("backup-offsite", "Keep one backup off-site or offline", "Backups", "offsite offline cloud backup air gap immutable", "A backup that is always connected can be encrypted along with the PC.",
   ["Choose: a cloud backup service with version history, or a second external drive.", "If using a drive, plug it in only to back up, then unplug it and store it away from the office.", "Rotate two drives if you can, one at home and one at work."], "You can name where the offline or off-site copy is and when it last updated.", 20, "", "Backup restore tracker", ("backups_offsite",))
_g("router-password", "Change the router's default passwords", "Network", "router default password admin wifi wpa", "Default router passwords are published online.",
   ["Find the router's admin page (usually 192.168.0.1 or 192.168.1.1, or the address on its label).", "Change the admin password to a long unique one from your password manager.", "Set Wi-Fi to WPA2 or WPA3 with a long passphrase.", "Turn off remote administration, WPS and UPnP if you do not need them.", "Update the router firmware."],
   "Log in with the new password, and the old default no longer works.", 20, "Write the new admin password down before saving; a factory reset is the only fix if you lose it.", "", ("router_password",))
_g("guest-wifi", "Put guests and smart devices on a separate Wi-Fi", "Network", "guest wifi iot cameras smart tv vlan separation", "Keeps a cheap camera or a visitor's phone away from business PCs.",
   ["In the router settings, turn on the guest network with its own name and password.", "Move smart TVs, cameras, printers and visitors onto it.", "Make sure 'allow guests to see each other and local devices' is off."], "From a phone on the guest Wi-Fi you cannot open the office PC's shared folders.", 15, "Some printers and cameras need to be on the main network to be used from the office. Test each.", "", ("guest_wifi",))
_g("staff-training", "Run a short phishing awareness session", "People", "training awareness phishing staff employees", "Most attacks start with one convincing email.",
   ["Pick 20 minutes. Use the Phishing practice tab to go through examples together.", "Agree the rule: if money, passwords or urgency are involved, check by phone using a number you already have.", "Agree who to tell, and make it safe to report a mistake quickly.", "Repeat every six months."], "Everyone can name who to tell and the one-call rule.", 30, "", "Phishing practice", ("training",))
_g("incident-plan", "Write a one-page incident plan", "People", "incident response plan hacked breach contacts runbook", "Panic wastes the first hour, which matters most.",
   ["Write: who decides, who to call (IT help, bank, insurer, lawyer), and where the plan is kept offline.", "Write the first five steps: disconnect the PC from the network, do not turn it off if you can avoid it, change passwords from a clean device, tell the bank if money is involved, start the timeline.", "Use the Incident timeline tab to record what happens.", "Print it and put it where it can be found without the network."], "The plan exists on paper and someone other than you has read it.", 45, "", "Incident timeline", ("incident_plan",))
# ------------------------------------------------------------------ website
_g("web-hsts", "Add the HSTS header", "Website", "hsts strict transport security https header", "Tells browsers to always use HTTPS for your site.", ["First make sure every page works on HTTPS.", "Add the response header: Strict-Transport-Security: max-age=31536000; includeSubDomains.", "Start with a short max-age (like 300) while testing, then raise it.", "In most hosts this is a setting or a config line in the web server."],
   "Run the Web checks tab again: HSTS shows OK.", 15, "If part of the site still needs plain HTTP it will break once HSTS is on.", "Web checks tab", ("hsts",))
_g("web-csp", "Add a Content-Security-Policy header", "Website", "csp content security policy xss script injection header", "Limits what scripts and resources a page may load, which blunts cross-site scripting.", ["Start in report-only mode: Content-Security-Policy-Report-Only with a basic policy such as default-src 'self'.", "Watch what it would have blocked and allow only what you truly use.", "Switch to the real Content-Security-Policy header."],
   "Web checks again: CSP shows OK, and the site still works.", 60, "A policy that is too strict breaks features. Use report-only first.", "Web checks tab", ("csp",))
_g("web-headers-small", "Add the small protective headers", "Website", "nosniff x-content-type-options frame x-frame-options referrer permissions policy clickjacking", "Cheap headers that close off clickjacking and content-type tricks.",
   ["Add: X-Content-Type-Options: nosniff", "Add: X-Frame-Options: DENY (or SAMEORIGIN if you frame your own pages).", "Add: Referrer-Policy: strict-origin-when-cross-origin", "Add: Permissions-Policy: camera=(), microphone=(), geolocation=()."], "Web checks again shows them OK.", 10, "Do not block framing if another site legitimately embeds yours.", "Web checks tab", ("nosniff", "framing", "referrer", "permissions"))
_g("web-cert", "Renew or fix the website certificate", "Website", "certificate expired ssl tls renew lets encrypt", "An expired or wrong certificate scares visitors away and breaks the site.",
   ["Find out who issued it (the Web checks tab shows the issuer).", "If it is Let's Encrypt or your host's free certificate, renew it from the host's control panel or run the renewal tool.", "Turn on automatic renewal and a calendar reminder 30 days before expiry.", "Check that every name the site uses (with and without www) is covered."], "Web checks tab: expires in more than 21 days and TLS 1.2 or 1.3.", 20, "", "Web checks tab", ("expiry", "verify", "tls"))
# ------------------------------------------------------------------ logs
_g("log-takeover", "Respond to a possible account takeover", "Logs and incidents", "brute force success account takeover login after failures compromised", "Many failed logins followed by a success means the attacker may have guessed the password.",
   ["Treat the account as compromised. Reset its password from a clean device.", "Sign out all sessions and revoke keys and tokens.", "Check what that login did: files changed, emails forwarded, new users, new rules.", "Block the address at the firewall and turn on 2FA.", "Record all steps in the Incident timeline."], "The old password no longer works, no unknown sessions remain, and nothing unexpected changed.", 60, "Do not delete logs; you may need them.", "Incident timeline, Log analysis", ("brute-success",))
_g("log-guessing", "Stop password guessing", "Logs and incidents", "brute force password guessing failed logins fail2ban lockout", "Repeated failed logins from one address is an automated guessing attempt.",
   ["Make sure the account has a strong unique password and 2FA.", "Add a lockout or rate limit (fail2ban on Linux, account lockout policy on Windows).", "If the service does not need to be public, close the port or limit it to known addresses.", "Block the offending address."], "Failed attempts stop being accepted and the service is no longer open to the world.", 30, "A lockout can be used to lock out real users; use short lockouts.", "Log analysis", ("brute",))
_g("log-enum", "Respond to username guessing", "Logs and incidents", "username enumeration user enum invalid user", "Someone is trying many usernames to find real ones.", ["Check none of the names tried exist as real accounts you did not expect.", "Disable accounts you no longer need.", "Close or restrict the service to known addresses if it does not have to be public."], "Failed tries stop, and the account list matches who works with you.", 20, "", "Log analysis", ("enum",))
_g("log-scan", "Respond to web scanning", "Logs and incidents", "scan scanner probes 404 wp-admin env git web requests", "Bots probe every site for known weak files. It is noise unless something answers.", ["Check the responses to those requests: any 200 results for admin pages, .env or .git files are real problems.", "Remove or protect anything that should not be public.", "Add a rate limit or a web application firewall if the volume is high."], "The probed paths return 404 or 403 for outsiders.", 20, "", "Log analysis", ("scan",))
_g("log-sensitive", "Respond to requests for sensitive files", "Logs and incidents", "sensitive files env git backup config requests", "Someone asked for files like .env or backups. If any were served, secrets may be exposed.", ["Check whether those requests returned the file (status 200).", "If yes, treat every secret in them as leaked: rotate passwords, keys and tokens now.", "Move the files out of the web folder and block the paths."], "The paths now return an error and the old secrets have been replaced.", 45, "", "Log analysis", ("sensitive",))
# ------------------------------------------------------------------ new tools
_g("account-review", "Review who has access to which accounts", "Accounts", "account inventory access review shared accounts owner offboarding", "Old and shared accounts are how people keep access they should have lost.", ["Open the Account inventory tab and list each important account.", "Remove anyone who no longer needs access.", "Replace shared logins with one login per person.", "Record the review date and repeat every six months."], "Every account shows an owner, 2FA, stored recovery codes and a recent review.", 30, "", "Account inventory", ("acct_stale", "acct_shared", "acct_no_recovery"))
_g("device-eol", "Replace or update a device that is out of support", "Devices", "end of life eol unsupported windows 10 windows 7 old os no updates", "A system that no longer gets security updates stays vulnerable forever.", ["Check the vendor's page for the exact end-of-support date for that version.", "If an upgrade is available and the hardware supports it, back up and upgrade.", "If not, plan replacement. Until then, keep it off the internet or isolated, and do not use it for banking or email.", "Record the plan and date in the Device inventory tab."], "The device runs a supported version, or has a dated replacement plan and is isolated.", 60, "Check any paid extended-security option with the vendor; do not rely on it for long.", "Device inventory", ("device_eol",))
_g("phish-clicked", "I clicked a phishing link or opened an attachment", "Logs and incidents", "phishing clicked link attachment entered password malware", "Act fast and calmly: speed limits the damage.", ["Disconnect the device from the network (Wi-Fi off, cable out). Do not turn it off if you can avoid it.", "If you typed a password, change it now from a different, clean device, and every account that shared it. Turn on 2FA.", "If you opened an attachment, run a full antivirus scan before reconnecting.", "If money or banking is involved, call the bank right away using the number on your card.", "Tell whoever handles IT, and record what happened in the Incident timeline."],
   "Passwords changed from a clean device, scan clean, nothing unexpected in accounts.", 45, "Do not reply to the sender or click anything else.", "Incident timeline", ("phish",))
_g("pwned-password", "A password was found in a breach", "Accounts", "pwned breach leaked password haveibeenpwned exposed", "A breached password is on attackers' lists and will be tried everywhere.", ["Change it everywhere you used it, starting with email and money.", "Use a unique generated password for each account (password manager).", "Turn on 2FA so a leaked password alone is not enough."], "The breach check no longer finds the new password, and 2FA is on.", 20, "", "Breach check", ("pwned",))
_g("mac-hardening", "Fix a macOS hardening finding", "macOS", "mac macos filevault firewall gatekeeper sip updates guest remote login", "These settings protect a Mac from theft, malware and remote access.", ["FileVault: System Settings > Privacy & Security > FileVault > Turn on; store the recovery key safely.", "Firewall: System Settings > Network > Firewall > On.", "Gatekeeper: leave 'App Store and identified developers' selected.", "SIP: if it is off, restart into Recovery and run csrutil enable.", "Updates: System Settings > General > Software Update > turn on automatic updates.", "Remote Login (SSH) and guest user: turn off if not needed."],
   "Re-run the macOS script: the failing line now passes.", 20, "Recovery key loss can lose the data. Save it first.", "Endpoint hardening (macOS and Linux)", ("mac_filevault", "mac_firewall", "mac_gatekeeper", "mac_sip", "mac_updates", "mac_ssh", "mac_guest"))
_g("linux-hardening", "Fix a Linux hardening finding", "Linux", "linux ufw firewall ssh root login password authentication unattended upgrades luks sudo nopasswd", "These are the common weak spots on a Linux server or laptop.", ["Firewall: sudo ufw default deny incoming; sudo ufw allow ssh; sudo ufw enable.", "SSH: in /etc/ssh/sshd_config set PermitRootLogin no and PasswordAuthentication no (after keys work), then sudo systemctl restart ssh.", "Updates: sudo apt install unattended-upgrades (Debian/Ubuntu) and run sudo dpkg-reconfigure unattended-upgrades.", "Sudo: remove NOPASSWD entries with sudo visudo.", "Disk encryption needs to be chosen at install; for new data use an encrypted volume (LUKS).", "Listening services: run ss -tulnp, and disable the ones you do not use (sudo systemctl disable --now name)."],
   "Re-run the Linux script: the failing line now passes.", 30, "Test SSH key login in a second terminal before turning password login off, or you can lock yourself out.", "Endpoint hardening (macOS and Linux)", ("linux_firewall", "linux_ssh_root", "linux_ssh_password", "linux_updates", "linux_sudo", "linux_luks", "linux_listen"))


def get(gid: str) -> dict | None:
    return next((f for f in FIXES if f["id"] == gid), None)


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2}


def search(q: str, limit: int = 6) -> list[dict]:
    qw = _words(q)
    if not qw:
        return []
    out = []
    for f in FIXES:
        kw, tw, bw = _words(f["keywords"]), _words(f["title"]), _words(" ".join(f["steps"]) + " " + f["why"])
        s = 3 * len(qw & kw) + 3 * len(qw & tw) + len(qw & bw) + (2 if q.lower().strip() in f["title"].lower() else 0)
        if s:
            out.append((s, f))
    out.sort(key=lambda x: -x[0])
    top = out[0][0] if out else 0
    out = [o for o in out if o[0] * 4 >= top]
    return [{"id": f["id"], "title": f["title"], "area": f["area"], "minutes": f["minutes"], "why": f["why"], "score": s} for s, f in out[:limit]]


def for_ref(ref: str, title: str = "") -> str | None:
    base = ref.split(":")[0]
    if base in REF:
        return REF[base]
    if title:
        r = search(title, 1)
        if r and r[0]["score"] >= 4:
            return r[0]["id"]
    return None


def areas() -> dict:
    out: dict[str, list[dict]] = {}
    for f in FIXES:
        out.setdefault(f["area"], []).append({"id": f["id"], "title": f["title"], "minutes": f["minutes"]})
    return out


TOOL_SEC_FIX = {"name": "sec_fix", "description": "Look up the how-to-fix guide for a security finding or problem. action 'search': query = the finding or what the user typed (e.g. 'smb1', 'RDP open', 'expired certificate', 'clicked a phishing link') -> best matching guides. "
                "action 'guide': id -> the full guide with steps, how to verify, time and cautions. Walk the user through the steps one at a time, state the caution before any step that could break something, and never claim a fix has worked until they have run the verify step.",
                "input_schema": {"type": "object", "properties": {"action": {"type": "string", "enum": ["search", "guide"]}, "query": {"type": "string"}, "id": {"type": "string"}}, "required": ["action"]}}


def tool_result(args: dict) -> str:
    a = args or {}
    if a.get("action") == "guide":
        g = get(str(a.get("id") or ""))
        if not g:
            return json.dumps({"error": "No guide with that id.", "try": search(str(a.get("query") or a.get("id") or ""), 3)})
        return json.dumps(g)
    return json.dumps({"results": search(str(a.get("query") or ""), 5)})
