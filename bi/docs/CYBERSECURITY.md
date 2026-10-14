# Cybersecurity: defend what you own

Open **Tracks > Cybersecurity**. Everything here is defensive and runs against your own app, your own logs, or public websites.
Security is risk reduction: fix the cheap, common slips first, watch for patterns, and have a plan.

## Vocabulary
- **CIA triad**: confidentiality (only the right people read it), integrity (nobody changes it unnoticed), availability (it works when needed).
- **Threat, vulnerability, risk**: a threat acts on a vulnerability; risk is likelihood times impact.
- **Hash vs encryption**: a hash is one-way. Encryption can be reversed with a key. Passwords are stored as slow, salted hashes.
- **2FA / TOTP**: a second factor made from a shared secret and the clock. The lab shows the maths.
- **Brute force / credential stuffing / enumeration**: guessing passwords, replaying leaked ones, discovering valid usernames.
- **SQL injection, XSS, path traversal**: input treated as code, script or file path. Parameters and escaping prevent them.
- **Least privilege, defence in depth, patching**: the three habits behind most good outcomes.

## The tools (all built in)
| Tab | What it does | Honest limit |
|---|---|---|
| Self-audit | Checks .env placement and permissions, secrets in files (file:line only), CORS, backups, SMTP | Finds common slips; can't prove you are secure |
| Logs | Detects brute force, takeover after brute force, enumeration, probing, injection patterns, 5xx bursts | Detections are leads, not verdicts |
| Web checks | Security headers and TLS certificate of a public site | Public hosts only; private/loopback/metadata addresses are refused |
| Local ports | Checks a fixed list of ports on this machine | Doesn't scan other machines |
| Crypto | Hash and verify, password strength and generator, TOTP lab | Crack time is an estimate with a stated assumption |
| Incidents | Tracker with a checklist per category | A checklist helps; judgement still matters |

## Taught, not built
Wireshark, Nmap, Burp Suite, Metasploit, Kali, C2 frameworks and fuzzers are offensive or dual-use tools. Learn them in a lab you own
(a VM, or a deliberately vulnerable app) and only test systems you have written permission to test. See the Tool map for the list.

## Checklist for a personal app
1. `.env` is ignored by git, readable only by you. 2. No secrets in tracked files. 3. CORS lists real origins. 4. A backup exists and a restore was tested.
5. Dependencies are audited (`pip-audit`, Dependabot). 6. Only the ports you need are open. 7. You have a written first-hour incident checklist.
