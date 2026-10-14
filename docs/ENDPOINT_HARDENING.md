# Endpoint hardening audit (Cybersecurity track)

Cybersecurity dashboard > **Endpoint hardening**. Built from the "Endpoint Hardening Checklist" PDF, which lists links but no pass or fail criteria.

## How it works
1. The app writes a **read-only** PowerShell script (Get- commands and registry reads only; a test fails the build if a changing verb appears).
2. You read it, run it yourself on a PC you own, and paste the output.
3. The app grades 24 checks, shows why each matters, and lists the first fixes. Fixes are text; nothing here changes a setting, and the app never reaches your computer.

Checks: SMB1, PowerShell 2.0, TLS 1.0 and 1.1, LAN Manager level, WDigest, Secure Boot, BitLocker, firewall (three profiles), RDP and NLA, LLMNR, NetBIOS, smart name resolution, UAC, local administrators, Credential Guard, Defender real-time protection, ASR rules, patch age, Security log size, Excel internet-macro blocking.

Unreadable settings are graded "unknown", not "fail". The score counts only checks that could be read.

## Limits
One Windows PC at a time. No Group Policy, Intune or fleet reporting, no MFA, backup or EDR checks, no macOS or Linux baselines. **The script was not run on a real Windows machine while building this** (no PowerShell in the build environment): the grader is tested against sample output, so run it on a test PC first and tell me if a line errors. Some checks need an administrator prompt.

## Slips and gaps in the PDF
1. "$166B, more than double by 2028" has no source.
2. "The $50M ransomware attack on Acer": $50 million was the ransom demanded (REvil, 2021), not the cost of the attack.
3. The LockBit "five months via exposed RDP" line has no link or date; unverified.
4. Colonial Pipeline "inactive account without MFA" is shorthand for a leftover VPN account with a leaked password and no MFA.
5. "Refuse LM and NTLM" at the LanMan setting reads as blocking all NTLM; level 5 refuses LM and NTLMv1, NTLMv2 still works.
6. "Disable DNS Multicast" means LLMNR; mDNS is separate.
7. Defender Application Guard has been deprecated; the advice is dated.
8. "InfoSec Twitter (start here)" is dated; SimplyCyber appears as both a community and a PowerShell 2.0 reference.
9. Titled a checklist but no owners, order or pass criteria.
10. Missing: MFA everywhere, disk encryption, tested backups, EDR, LAPS, application allow-listing.
11. The last page is a vendor advertisement; nothing from it is copied.

Also added: IT track checklist "Harden a Windows endpoint (one change at a time)".
