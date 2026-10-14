# Part 9: Cybersecurity

## The role in one page

A security practitioner reduces the chance and the cost of bad things happening to information and the systems that hold it. In a small company that is one person doing a bit of everything. In a large one it splits into specialities: security analyst (watches and investigates), security engineer (builds protections into systems), application security (reviews code and design), governance and risk (policy, audits, vendor questions), and incident responder (leads when something goes wrong).

**Who you work with.** Everyone. Developers, who need security advice that does not stop them shipping. IT and network staff, who run the machines you worry about. Managers, who decide how much risk to accept. Lawyers and auditors, when data about customers or patients is involved.

**A typical day** is mostly unglamorous: triage alerts, read a pull request that touches login, chase an expired certificate, answer "is this email safe?", check last night's backup, and perhaps spend one hour on real investigation.

**What good looks like.** Fewer surprises. Secrets are not in code. Software is patched on a schedule. Backups have been restored at least once on purpose. Logs exist and someone reads them. There is a written first-hour plan for incidents, and people know where it is. Good practitioners also explain risk in plain words and let the owner of the business decide.

**What it is not.** It is not movie hacking. Most of the work is defence, hygiene and communication. It is not a promise of safety: you reduce risk, you never reach zero. It is not "saying no": a security team that blocks everything gets bypassed. And it is not permission to test other people's systems. Probing machines you do not own, or have no written permission to test, can be a crime in many places (in the US, laws such as the Computer Fraud and Abuse Act apply; this book is not legal advice).

**Honest hard parts.**

- You are blamed for what did not happen and rarely thanked for it.
- Attackers need one gap; defenders must cover all of them.
- Alerts are noisy, and false positives wear analysts down.
- Tools sell certainty they cannot provide. A clean scan is not a clean bill of health.

This book teaches the defensive side only. Offensive tools (Nmap, Burp Suite, Metasploit, Kali Linux) are explained so you understand what they do and how defenders use the same ideas, but you will not build or run attacks here.

## How to use this part

There are four levels. Times assume about five hours a week.

| Level | Focus | Hours | Weeks |
|---|---|---|---|
| 1 Foundations | Risk, secrets, hashing, passwords, MFA | 30 | 6 |
| 2 Practitioner | Web exposure, logs, input handling, patching and backups | 40 | 8 |
| 3 Advanced | Threat modelling, detection design, authentication, cryptography in practice | 50 | 10 |
| 4 Expert | Programmes, incidents, ethics, reviewing others' claims | 40 | 8 |

That is about 160 hours, or 32 weeks. Do not rush; the habits matter more than the speed.

**Pairing reading with practice.** Read a section, then do its "Practice on your own" labs the same day. Use a virtual machine, a spare laptop, a home router or a small app you wrote, and never anything you do not own or lack written permission to test. Keep a notebook of what you did and learned.

Remember the limits of any tool. A scanner or checklist is a **guardrail, not a vault**: it helps you notice slips, it does not make you safe. Its findings are **leads, not verdicts**: each needs your judgement. Offensive tools are taught about here, not built.

## Level 1: Foundations (beginner)

### What you will be able to do

- You can explain confidentiality, integrity and availability with one example each.
- You can separate threat, vulnerability and risk, and rank two risks by likelihood times impact.
- You can say why a secret must never be committed to git, and what to do if one was.
- You can tell hashing, encryption and encoding apart.
- You can judge a password by length and randomness, and explain why MFA helps.
- You can audit a computer you own, fix a failing item and re-check.

### Core ideas

#### The CIA triad and risk

Confidentiality means only the right people can read something. Integrity means nobody changes it without being noticed. Availability means it works when needed. A stolen customer list breaks confidentiality. A tampered invoice breaks integrity. Ransomware that locks your files breaks availability. Most incidents hit at least one of these, and good thinking starts by asking which one matters most for the asset in front of you.

A **threat** is something that could cause harm (a phisher). A **vulnerability** is a weakness it could use (a shared password). **Risk** is the combination: roughly likelihood times impact. Score each from 1 to 5. A laptop theft: likelihood 3 (it happens), impact 4 (customer data on disk) gives 12. A rare data-centre fire: likelihood 1, impact 5 gives 5. Fix the 12 first, unless the 5 is cheap. The numbers are judgement, not science; their value is forcing you to compare.

#### Secrets stay out of code

A secret is anything that proves identity or grants access: API keys, database passwords, private keys, tokens. The common mistake is committing one to a repository. Git keeps history, so deleting the file later does not remove the key; anyone with the repository can dig it out. If it is public, bots find it quickly.

The habit: keep secrets in a `.env` file that is listed in `.gitignore` and readable only by you (`chmod 600 backend/.env` on Linux or macOS). Commit a `.env.example` with fake values so others know what to fill in. If a real key is ever committed, do two things in order: **revoke it at the provider and create a new one**, then clean the repository. Revoking comes first because you must assume the old key is already copied.

#### Hash, encrypt, encode

Three different ideas people mix up. **Encoding** (Base64, URL encoding) changes representation and has no secrecy at all; anyone can reverse it. **Encryption** hides data and can be reversed by someone with the key. **Hashing** produces a fixed-length fingerprint and cannot be reversed. 

Worked example. The SHA-256 of the text `hello` is:

```
2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824
```

Change one letter and the output changes completely. That makes hashes ideal for checking that a download was not damaged or swapped: compare the hash you compute with the one the publisher shows. MD5 and SHA-1 are broken for security (fine for spotting accidental corruption only). The empty input hashes to `e3b0c442...b855`, a value you will meet often.

#### Passwords and MFA

Attackers rarely guess one password at a time against a website, which locks them out. The bigger danger is an **offline** attack: a stolen file of hashes tested at enormous speed. Length and randomness decide how long that takes. An eight-letter lowercase password has about 8 x 4.7 = 38 bits of entropy (each lowercase letter is log2 of 26, about 4.7 bits). At an assumed ten billion guesses per second, half the space is searched in about 10 seconds. Six random words from a 7,776-word list give about 77 bits, which is out of reach.

The rules that survive scrutiny: long, random, unique per site, stored in a password manager. Add **multi-factor authentication**, so a stolen password alone is not enough. Authenticator-app codes beat SMS; hardware keys and passkeys resist phishing best.

### Practice on your own

On a computer you own, audit yourself. Search any repository you keep for words like `password` and `key` (a free secret scanner helps), check key-file permissions with `ls -l`, and list where your backups are and who can reach them. Fix one item and re-check.

Hash the text `hello` with `printf hello | sha256sum` (`shasum -a 256` on macOS, or `hashlib` in Python) and compare it with the value above, then change one letter. Download any open-source installer and verify its published checksum. Finally, try three dummy passwords (never real ones) in a password manager's strength meter and note what it penalises.

### Exercises

1. Name which CIA property is hit by: (a) a USB stick lost with client files, (b) a spreadsheet silently edited, (c) a web server taken down by overload.
2. Risk-rank: phishing (likelihood 4, impact 3), lost laptop (3, 4), data-centre flood (1, 5). Which first?
3. A friend commits an API key then deletes the file in the next commit. Is the key safe? What exactly should they do?
4. Is Base64 encryption? Decode `aGVsbG8=` in any Python shell with `import base64; base64.b64decode("aGVsbG8=")` and say what you learn.
5. Calculate the entropy of a 10-character password of random lowercase letters and digits (36 symbols).
6. Why can you not "decrypt" a hash? What do attackers do instead?
7. Audit one computer you own, list every weakness you find, and write one fix sentence per item.

### Answers and hints

1. (a) confidentiality, (b) integrity, (c) availability.
2. Scores 12, 12 and 5. Phishing and the laptop tie; pick the cheaper fix first (a laptop disk-encryption setting is cheaper than training), then the other.
3. No. History still holds it. Revoke and replace the key at the provider first, then tidy the repository and add `.env` to `.gitignore`.
4. No, it is encoding. The result is `b'hello'`: anyone can reverse it with no key.
5. 10 x log2(36) = 10 x 5.17 = about 52 bits.
6. A hash throws information away, so there is nothing to reverse. Attackers hash guesses and compare, which is why slow, salted hashing matters (Level 3).

### Checkpoint

Answer aloud:

1. What are the three parts of the triad, with an example each?
2. How do threat, vulnerability and risk relate?
3. Why does deleting a committed secret not fix the problem?
4. Why is a hash not encryption?
5. Why does length beat symbols in a password?
6. Why is SMS the weakest common second factor?
7. What does a self-audit not prove?

Common mistakes:

- Treating a high score on a tool as proof of safety.
- Fixing the exciting risk instead of the likely one.
- Reusing one "good" password everywhere.
- Calling Base64 or obfuscation "encryption".
- Rotating a leaked key but leaving it in history without checking who used it.

## Level 2: Practitioner (intermediate)

### What you will be able to do

- You can read the security headers and TLS certificate of a public site you own and say which gaps matter.
- You can read an auth log and an access log and tell brute force, enumeration and probing apart.
- You can explain why parameterised queries stop SQL injection and write one.
- You can list what a service is exposing with `ss -tlnp` and explain 127.0.0.1 versus 0.0.0.0.
- You can set up a patching and backup routine, including a restore test.
- You can write an incident report from log evidence.

### Core ideas

#### What a website says about itself

Every response carries headers, and a handful tell the browser how to protect visitors. `Strict-Transport-Security` (HSTS) says "always use HTTPS for this site". A sensible value is `max-age=31536000; includeSubDomains` (one year); many checkers call anything under 15,552,000 seconds (180 days) too short. `Content-Security-Policy` limits which scripts a page may run, blunting cross-site scripting; a first policy is `default-src 'self'`, and words like `'unsafe-inline'` weaken it. `X-Content-Type-Options: nosniff` stops browsers guessing file types. `X-Frame-Options: DENY` (or CSP `frame-ancestors 'none'`) stops other sites framing yours for clickjacking. Cookies should carry `Secure`, `HttpOnly` and `SameSite`. Servers should not announce exact version numbers.

A header score is narrow evidence. A site can have perfect headers and a broken login. Treat the check as one class of easy mistakes being absent.

#### TLS certificates

TLS encrypts traffic and, through a certificate signed by a trusted authority, proves you reached the real domain. Things that go wrong: expiry (the most common outage), a certificate that does not cover the name, and old protocol versions. Today TLS 1.2 and 1.3 are acceptable; TLS 1.0, 1.1 and SSLv3 should be off. Certificates expire on a fixed date, so put renewal on a calendar or automate it. A common warning threshold is about 21 days. Never click through a browser certificate warning on a login page.

#### Reading logs

Logs are the memory of a system. Three shapes matter: auth logs (who tried to log in), web access logs (who asked for what, and the status code), and application logs (what the program thought). Learn the patterns:

- **Brute force**: many failures for one account or from one address in a short time. A common starting rule is five failures inside ten minutes.
- **Takeover after brute force**: failures followed by a success from the same address. That is the one to treat as an emergency.
- **Enumeration**: one address trying many different usernames (five or more is a common threshold).
- **Probing**: requests for paths such as `/.env` or `/wp-login.php` that should not exist, often returning 404.
- **Injection strings**: requests whose URL contains fragments like `' OR 1=1` or `<script>`. A 4xx response is a relief; a 200 deserves code review.

A 404 for `/.env` is noise; a 200 is a leak.

#### Handling input safely

Injection happens when input is treated as code. The cure is to keep data and instructions separate. In SQL, send the query text and the values apart:

```python
import sqlite3
con = sqlite3.connect("shop.db")
name = "O'Brien"                       # any user input, however odd
rows = con.execute("SELECT id, email FROM customers WHERE last_name = ?", (name,)).fetchall()
```

The `?` is a placeholder; the driver passes `name` as a value that can never become SQL. Never build the query by joining strings with user input. The same principle applies elsewhere: encode output for HTML to stop cross-site scripting, and never use user input directly as a file path or shell command. Validate input (length, type, allowed characters), but treat validation as a second layer, not the cure.

#### Patching, exposure and backups

Most real breaches use known, already-fixed flaws. Habits that matter: update on a schedule; run `pip-audit -r backend/requirements.txt` and `npm audit` for known-vulnerable dependencies; turn on Dependabot alerts; remove services you do not use. See what is listening with `ss -tlnp` (Linux) or `netstat -ano` (Windows). A service bound to `127.0.0.1` is reachable only from the same machine; bound to `0.0.0.0` it is reachable from anywhere that can route to it. Databases and admin tools should rarely be on the second list.

Backups are your answer to ransomware and accidents, but only if they work. Follow 3-2-1: three copies, two kinds of media, one offsite. Then **restore one** into a scratch location and open the files. An untested backup is a hope.

### Practice on your own

Pick a public site you own (a personal page will do). Run `curl -sI https://yoursite.example` and compare the headers with the list above. Run `openssl s_client -connect yoursite.example:443 -servername yoursite.example` and note the certificate expiry and protocol version.

Write a 20-line made-up auth log using documentation-range addresses (203.0.113.x and 198.51.100.x): eight failed logins from one address followed by a success, and six invalid-user lines from another. Find both patterns with `grep` and `sort | uniq -c`. List listeners on your own machine with `ss -tlnp` and explain each one. Finally back up a folder, restore it somewhere else and compare with `diff -r`.

### Exercises

1. Which header would you add first to a site with no HSTS, no CSP and no nosniff, and why?
2. A certificate shows 12 days left. Is that a problem, and what do you do?
3. In an auth log, five failures from one IP appear in 3 minutes, then `Accepted password for admin` from it. Describe your first three actions.
4. Rewrite `"SELECT * FROM users WHERE id = " + user_id` safely in Python (sqlite3 style).
5. Why is `/etc/passwd` in a URL a lead and not proof of attack?
6. A database listens on 0.0.0.0:5432 on a home server. Explain the risk and two ways to reduce it.
7. Design a monthly routine (under 30 minutes) covering patching, audit and backup restore.
8. Write a 150-word incident report for the takeover in exercise 3.

### Answers and hints

1. HSTS is quick and removes a whole class of downgrade risk once the site is fully HTTPS. A CSP is more valuable but needs testing, so start it in a trial period.
2. It is below a typical 21-day warning line. Renew now, then check automatic renewal.
3. Contain (reset the password, end sessions, block the IP), investigate (what did that login do: commands, new keys, files), and keep evidence (copy the log lines before anything rotates).
4. `con.execute("SELECT * FROM users WHERE id = ?", (user_id,))`.
5. Scanners send it to every site; a 404 or 400 means it did nothing. Only a 200 containing system data would be a problem.
6. Anyone who can reach the host can try to log in or exploit database flaws. Bind to 127.0.0.1 or a private interface, use a firewall to allow only known addresses, and require strong credentials.

### Checkpoint

Answer aloud:

1. What do HSTS, CSP and nosniff each defend against?
2. Which log pattern is the most urgent and why?
3. Why does a `?` placeholder stop injection?
4. What is the difference between 127.0.0.1 and 0.0.0.0?
5. What does 3-2-1 mean, and what comes after it?
6. Why are findings leads, not verdicts?

Common mistakes:

- Chasing a 100 percent header score while ignoring the login code.
- Blocking an IP and calling the incident closed without checking what it did before.
- Escaping quotes by hand instead of using placeholders.
- Letting a certificate expire because renewal lived in one person's head.
- Believing a backup works because the job reported success.

## Level 3: Advanced

### What you will be able to do

- You can threat-model a small system with trust boundaries and STRIDE, and rank the results.
- You can design a log detection with a threshold, estimate its false positives and tune it.
- You can store passwords correctly and explain each parameter you chose.
- You can find broken access control in a design or code review.
- You can explain TLS, symmetric versus asymmetric cryptography and key management without hand-waving.
- You can read a security tool's rules or source and say what each check does and misses.

### Core ideas

#### Threat modelling

Threat modelling asks four questions: what are we building, what can go wrong, what will we do about it, did we do a good job. Draw the system as boxes and arrows (browser, API, database, third-party email service) and mark **trust boundaries**: places where data crosses from less trusted to more trusted, such as the internet to your API. At each boundary and component ask the six STRIDE questions: **S**poofing (pretending to be someone), **T**ampering (changing data), **R**epudiation (denying an action with no proof), **I**nformation disclosure, **D**enial of service, **E**levation of privilege.

Worked example, a login endpoint. Spoofing: stolen password, so add MFA. Tampering: session cookie edited, so sign it server-side. Repudiation: nobody can prove who changed a record, so log user and time. Information disclosure: error messages reveal whether a username exists, so use one generic message. Denial of service: unlimited attempts hammer the hash function, so rate-limit. Elevation: an ordinary user's ID can be changed to an admin's in a request, so check authorisation on the server. Six questions, six concrete controls, ranked by likelihood times impact.

#### Detection engineering

A detection is a rule that turns raw events into a decision a human must make. Its quality is measured by **precision** (of the alerts, how many were real) and **recall** (of the real events, how many alerted). They trade off. Suppose a rule "five failed logins in ten minutes" fires 40 times a day across 200 staff, and a review finds 2 were attacks. Precision is 2 / 40 = 5 percent: analysts will stop reading it. Raise it to ten failures and alerts may drop to 6 a day with both attacks still caught, precision 33 percent. But a patient attacker trying one password per hour never trips either rule, which is why detections must be layered: per-account lockout, unusual-location logins, alerts on any success after failures.

Every detection has tunable thresholds: a count (five), a window (ten minutes), a number of usernames. The "success after failures" rule is the highest-value one because its precision is high. Always record why you chose a threshold, and review it against real data every few months.

#### Passwords on the server side

Never store passwords, and never store them with fast hashes like SHA-256 (fine for fingerprints because it is fast; that speed is exactly the problem here). Use a purpose-built **slow, salted** algorithm: Argon2id, scrypt or bcrypt, with PBKDF2 where compliance requires it. A **salt** is a random value stored beside the hash so identical passwords yield different hashes and precomputed tables are useless. A standard-library sketch:

```python
import hashlib, hmac, os

N, R, P = 2**14, 8, 1          # cost parameters: raise N as hardware allows

def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=N, r=R, p=P, dklen=32)
    return f"scrypt${N}${R}${P}${salt.hex()}${dk.hex()}"

def verify_password(pw: str, stored: str) -> bool:
    _, n, r, p, salt, dk = stored.split("$")
    test = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt),
                          n=int(n), r=int(r), p=int(p), dklen=32)
    return hmac.compare_digest(test.hex(), dk)
```

Parameters are stored with the hash so you can raise them later. `compare_digest` compares in constant time. The memory use is 128 x N x R bytes, here 16 MiB per hash, which is what makes mass guessing expensive. Check current OWASP guidance for recommended settings; they rise over time.

#### Authentication versus authorisation, and access control

Authentication asks "who are you?". Authorisation asks "may you do this?". The most common serious web flaw is **broken access control**: code that checks you are logged in but not that the record is yours. Example: `GET /invoices/1042` returns invoice 1042 to any logged-in user, so changing the number shows other customers' invoices. The fix is to put ownership in the query: `SELECT ... FROM invoices WHERE id = ? AND customer_id = ?`, with the second value taken from the session, never from the request. Deny by default, check on the server for every request, and test with two accounts.

#### Cryptography in practice and TOTP

Symmetric encryption uses one shared key (fast; AES). Asymmetric uses a key pair (public and private; slower; used to agree on keys and to sign). TLS uses asymmetric methods to agree on a fresh symmetric key, then encrypts traffic with it; a modern handshake gives **forward secrecy**, so recording traffic today does not help if the server key leaks tomorrow. Rules: use authenticated modes (AES-GCM or ChaCha20-Poly1305), never reuse a nonce with the same key, never invent your own algorithm, and protect keys (not in code, rotated, limited to those who need them). Key management is harder than the cipher.

TOTP (RFC 6238) is HMAC of a shared secret and the time step, truncated. The RFC's published test uses the ASCII secret `12345678901234567890` (Base32 `GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ`) at Unix time 59 and gives the 8-digit code 94287082, so the 6-digit code is 287082. A standalone check:

```python
import base64, hashlib, hmac, struct

def totp(secret_b32, t, digits=6, step=30):
    key = base64.b32decode(secret_b32)
    mac = hmac.new(key, struct.pack(">Q", int(t // step)), hashlib.sha1).digest()
    off = mac[-1] & 0x0F
    code = (struct.unpack(">I", mac[off:off + 4])[0] & 0x7FFFFFFF) % 10**digits
    return str(code).zfill(digits)

print(totp("GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ", 59))   # 287082
```

### Practice on your own

Implement the TOTP function above and compare its output with a free authenticator app using a throwaway secret on a test account you create. Try a code from 90 seconds ago and watch it fail; real servers accept one step either side for clock drift. Write a small detector in any language for "N failures within W minutes, then a success", run it on a made-up log, and vary N and W to see which events still alert. Threat-model a small app you built with the STRIDE questions and list one control per answer.

### Exercises

1. Draw a data-flow sketch for a small web app (browser, API, database, third-party email service) and mark two trust boundaries.
2. Apply STRIDE to a setting that sends row-level customer data to an outside AI service. Which categories apply?
3. A rule fires 60 times a week; 3 were real. Compute precision. Suggest one change that keeps recall.
4. Why is salting needed if the hash is already slow?
5. Find the access-control flaw: `UPDATE tickets SET status='closed' WHERE id=?` with the id from the URL.
6. Why must a nonce never repeat under one key in AES-GCM?
7. Write detection logic, in words, for "success after failures" including the time window.
8. Why might a TOTP checker accept a code from the previous 30-second step?

### Answers and hints

1. Boundaries: browser to API (the internet), and API to the third-party service (data leaves your control).
2. Information disclosure mainly (row-level data leaves), plus repudiation if no log records what was sent.
3. 3 / 60 = 5 percent. Require the success-after-failure condition or raise the threshold, then re-check that known attacks still alert.
4. The slow hash limits guessing speed; the salt stops one guess being tested against every user at once and kills precomputed tables.
5. It never checks the ticket belongs to the user or team. Add an ownership condition from the session.
6. A repeated nonce lets an attacker combine two ciphertexts to learn about the plaintexts and can reveal the authentication key.

### Checkpoint

Answer aloud:

1. What is a trust boundary and why does it matter?
2. Define precision and recall for a detection.
3. Why is SHA-256 wrong for password storage?
4. What is an IDOR-style flaw and how is it fixed?
5. What does forward secrecy protect against?
6. Where do keys live in your designs, and who can read them?
7. Why are TOTP codes accepted one step either side?

Common mistakes:

- Listing threats without ranking or owners.
- Tuning an alert threshold on one night's data.
- Using "encrypted" to mean "safe" without asking who holds the key.
- Checking access control in the browser instead of the server.
- Copying cost parameters from a five-year-old blog post.

## Level 4: Expert and professional judgement

### What you will be able to do

- You can build a risk register and justify spending, or not spending, with numbers and honest uncertainty.
- You can lead the first hour of an incident and run a blameless review afterwards.
- You can set the scope and rules for authorised testing and handle a found weakness ethically.
- You can review a penetration-test report or vendor security claim and spot what it does not say.
- You can design security that people actually follow, at team or organisation scale.

### Core ideas

#### Risk registers and spending

A risk register lists risks with an owner, a score, a decision (reduce, accept, transfer or avoid) and a review date. To compare cost with benefit, use annualised loss expectancy: single loss expectancy times annual rate of occurrence. If a lost unencrypted laptop would cost 20,000 to handle and you expect one every ten years, the annual expectation is 20,000 x 0.1 = 2,000. A disk-encryption setting that costs an hour is obviously worth it. A 15,000-a-year tool aimed at the same risk is not. The inputs are guesses, so show ranges.

Risk belongs to the business owner. Your job is to make the choice informed, write it down and revisit it, not to decide alone. Frameworks such as the NIST Cybersecurity Framework (its functions are Govern, Identify, Protect, Detect, Respond, Recover) or the CIS Controls gives you a checklist to avoid forgetting areas; they are tools, not goals.

#### Incident leadership

NIST's incident guidance describes the cycle: preparation, detection and analysis, containment/eradication/recovery, and post-incident activity. In the first hour, aim to **contain, preserve, communicate**. Contain: isolate the device or revoke the credential, preferably without destroying evidence (disconnect rather than power off, when evidence matters). Preserve: copy logs and note times before they rotate. Communicate: one named lead, one place for the timeline, regular short updates, and an early decision on who must be told (customers, regulators, insurers). If health or personal data is involved, obligations may be legal, such as HIPAA in the US for health information; get proper advice instead of guessing.

Afterwards hold a **blameless review**: what happened, what helped, what hurt, what changes. People who fear blame hide mistakes, which makes the next incident worse. Track time to detect and time to resolve over many incidents; one number means little.

#### Authorised testing and ethics

Offensive techniques exist because defenders must test. The ethical and legal line is **authorisation**. Before any test, get written permission from someone entitled to give it, with scope (which systems, which dates), rules of engagement (no data destruction, no testing of third parties, stop conditions) and a contact for emergencies. Anything outside scope is off limits even if reachable. Test only what you own or are authorised to test; a deliberately vulnerable practice app in your own lab is the safe way to learn.

If you find a weakness in someone else's system by accident, stop, do not explore further or keep data, and report it through their published security contact. This is called coordinated disclosure. In reports, say what you verified and what you did not test.

#### Reviewing others' work

A penetration test is a time-boxed sample, not a guarantee. Read the scope first: what was excluded? Then the method, dates, and whether findings are ranked by real impact or just copied scanner output. For a vendor questionnaire, ask for evidence (a recent independent audit report, how they handle keys, their breach history policy) rather than ticking yes or no. "We use bank-grade encryption" means nothing without detail.

When reviewing a colleague's design, ask the same five questions: what is being protected, who could attack it, where are the trust boundaries, what happens when this control fails, how would we notice. Criticise the design, not the person, and offer a cheaper alternative when you say no.

#### Failure modes and scale

Security fails in predictable ways. **Alert fatigue**: real alerts get ignored. **Security theatre**: visible rituals that reduce no real risk (forced monthly password changes). **Workarounds**: controls too awkward to follow get bypassed. **Single points of failure**: one admin account, one person who knows the process. **Insiders**, meaning mistakes as much as malice, which is why least privilege and logging apply to staff too.

At organisation scale you move from doing to enabling: defaults that are safe (SSO, a password manager, encrypted laptops), paved roads for developers, training that is short and practised, and tabletop exercises where a team talks through a scenario and finds gaps in an hour.

### Practice on your own

Write a one-page playbook for a lost laptop: owner, first-hour steps (lock or wipe, revoke sessions, check disk encryption, list the data on it, decide who must be told) and contacts. Run it as a tabletop with a friend: read out the scenario, have them follow the playbook, and note three gaps. Keep a simple timed log of each decision with its reason, then write the blameless review. Repeat for phishing. A document or spreadsheet is enough; this is personal-scale practice, not a team ticketing system.

### Exercises

1. Build a three-row risk register (owner, score, decision, review date) for a small online shop.
2. Compute ALE for a risk costing 50,000 with a 5 percent yearly chance. Would a 1,500-a-year control be justified?
3. List what you must do in the first hour after finding an exposed cloud storage folder with customer files.
4. Draft the scope paragraph for a test of your own home server.
5. Imagine a penetration-test report with only a findings table: list five things a reader needs to know that the findings table alone omits.
6. Argue for or against forced 90-day password changes, with evidence.
7. A vendor says they are "fully secure". Write five follow-up questions.
8. Write the blameless review of the lost-laptop tabletop in 200 words.

### Answers and hints

2. 50,000 x 0.05 = 2,500 per year. The control costs less than the expected loss, so yes, if it really cuts the risk by a good share; reducing 60 percent saves 1,500, which only breaks even.
3. Remove public access, record what and how long, check access logs, rotate exposed secrets, decide who must be told, add a prevention check.
4. Name the host, the address range, test dates, allowed activities, forbidden ones (no destruction), your contact and a stop rule.
5. Scope, exclusions, dates, method, limits, severity rationale, retest status.
6. Against: forced changes push people to predictable edits and workarounds; prefer long unique passwords, a manager, MFA, and changing on evidence of compromise.

### Checkpoint

Answer aloud:

1. Who owns a risk decision, and what is your role?
2. What three things come first in an incident?
3. What makes a test authorised?
4. What do you do after finding a weakness by accident?
5. What should you ask first about a penetration-test report?
6. Name three failure modes of a security programme.
7. Why blameless?

Common mistakes:

- Presenting estimated numbers as facts.
- Cleaning a compromised machine before keeping evidence.
- Treating compliance as security, or the reverse.
- Testing "just a little" outside scope.
- Saying no without offering a safer, workable alternative.

## Capstone projects

### Capstone 1: Harden and document a personal app (small, about 8 hours)

**Brief.** Take a small app or home setup you run from a first self-audit to a documented, repeatable baseline.

**Deliverables.** The first and last audit results with every fix listed; a one-page checklist for the app (secrets, permissions, ports, dependencies, backup); proof of one restored backup; a note on three items the audit cannot see.

**Rubric** (0 to 2 each; 8 or more is solid):

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| Every fail fixed and re-run | None | Some | All, with the second audit shown |
| Backup restore tested | Not done | Done, not checked | Done and files opened |
| Honest about limits | None named | One | Three or more |

### Capstone 2: Investigate a log and write the incident report (medium, about 20 hours)

**Brief.** Build a made-up log of at least 300 lines (documentation-range IP addresses only) with one slow brute force, one noisy scanner and normal traffic, plus a short auth log whose brute force ends in a success. Investigate both.

**Deliverables.** Each detection with evidence and your verdict (real, false positive, unsure) and reasoning; a timeline; containment and recovery actions; a one-page incident report with lessons; a proposal for two tuned thresholds with before-and-after alert counts; an incident record with timestamps in a document or tracker.

**Rubric** (0 to 2 each; 10 or more is solid):

| Criterion | What a 2 looks like |
|---|---|
| Evidence | Each claim cites specific log lines |
| Judgement | Verdicts distinguish lead from conclusion; unknowns stated |
| Timeline | Ordered, with times and sources |
| Response | Contain, preserve and communicate all present |
| Tuning | Threshold changes justified with counts, and the cost in missed events named |

### Capstone 3: Security programme for a small organisation (large, about 45 hours)

**Brief.** Imagine a ten-person firm that handles sensitive customer or patient information (a skilled nursing facility's business office is a realistic case). Design a first-year security programme using only what it could afford and sustain.

**Deliverables.** A data-flow sketch with trust boundaries; a threat model using STRIDE for the two most critical flows; a ranked risk register of at least ten risks with owners and decisions; policies in plain language (passwords and MFA, devices, backups, acceptable use); an incident playbook for three categories with a tabletop script; a 12-month roadmap; a one-page honest summary of what the programme will not stop; and a note on legal duties to check with a professional.

**Rubric** (0 to 3 each; 18 or more is strong):

| Criterion | 3 means |
|---|---|
| Fit to the organisation | Controls match size, budget and data |
| Risk reasoning | Ranking is explained, ranges shown, owners named |
| Usability | Staff could follow policies without help |
| Incident readiness | Playbooks have owners, contacts and evidence steps |
| Honesty | Limits and unknowns clearly stated; no overclaiming |

## Tools reference

| Tool | What it is for | When you outgrow it |
|---|---|---|
| Audit scripts and checklists (for example Lynis on Linux, or your own) | Check permissions, services, secrets and settings on a machine you own | When you need continuous, multi-host or compliance-grade assessment |
| `grep`, `awk`, `sort`, `uniq` | Reading and counting log lines | When you need live collection and alert routing (a SIEM such as Splunk or Elastic) |
| `curl -I`, `openssl s_client` | See headers and certificates of a site you own | When you need monitoring and a certificate inventory |
| `ss -tlnp` | See what is listening on your own machine | When you must inventory many hosts, which needs authorised scanning tools |
| Python `hashlib` and `hmac` | Hashing and TOTP maths for learning | Real credential libraries (Argon2id, bcrypt), a password manager |
| A document or ticket tracker | Incident log and checklists | An incident platform with assignment, audit trail and on-call |
| `pip-audit`, `npm audit`, Dependabot | Known-vulnerable dependency checks | When you need software inventories and policy gates in a build pipeline |
| Wireshark (taught, not built) | Inspect network traffic on networks you own or are authorised on | When you need continuous network monitoring |
| Nmap (taught, not built) | Discovers hosts and open ports; defenders use it to inventory their own exposure | Never replaced, but only run on authorised ranges |
| Burp Suite (taught, not built) | An intercepting proxy for testing web apps you own or have permission to test | When you need scale and automation under a formal test programme |
| Metasploit and Kali Linux (taught, not built) | A framework of known exploits and a Linux distribution bundling security tools; used by authorised testers in labs | Professional testing with scope, reports and retesting |
| Deliberately vulnerable practice apps | Legal places to learn (for example OWASP Juice Shop, DVWA) | When you move to real, authorised engagements |

## Glossary

- **Authentication**: proving who you are.
- **Authorisation**: deciding what an authenticated user may do.
- **Availability**: data and services work when needed.
- **Brute force**: guessing credentials by trying many.
- **CIA triad**: confidentiality, integrity, availability.
- **Coordinated disclosure**: reporting a flaw privately to its owner, with time to fix.
- **Credential stuffing**: trying passwords leaked elsewhere against a new site.
- **CSP**: Content-Security-Policy header limiting which scripts a page may run.
- **Encryption**: reversible hiding of data with a key.
- **Enumeration**: discovering which usernames or resources exist.
- **False positive**: an alert for something harmless.
- **Hash**: one-way fixed-length fingerprint of data.
- **HSTS**: header telling browsers to use HTTPS only.
- **Least privilege**: giving only the access needed, no more.
- **MFA**: authentication using two or more kinds of proof.
- **Salt**: random value mixed into a password hash.
- **SIEM**: system that collects logs and raises alerts.
- **SQL injection**: input treated as SQL; prevented by placeholders.
- **STRIDE**: spoofing, tampering, repudiation, information disclosure, denial of service, elevation of privilege.
- **Threat model**: structured analysis of what could go wrong with a system.
- **TOTP**: time-based one-time code from a shared secret and the clock.
- **Trust boundary**: place where data passes between levels of trust.
- **Vulnerability**: a weakness that could be used to cause harm.
- **XSS**: cross-site scripting, where untrusted input runs as script in a page.

## Career notes

**Roles it leads to.** Security analyst (SOC), incident responder, security engineer, application security engineer, cloud security engineer, governance, risk and compliance analyst, security awareness lead, and later security architect or head of security. Smaller companies blend these; titles vary a lot, so read job descriptions for the work, not the label.

**Showing your skill.** Employers believe evidence over claims. Keep a portfolio of the three capstones: a self-audit before and after, an investigated log with a clear report, and a small-organisation programme. Write short, honest posts or notes on what you learned. Your ten years of business development inside a skilled nursing facility are an asset here: you understand how sensitive resident information is handled, how staff really work, and why policies fail when they ignore workflow. Plain-language risk conversations are rarer than tool skills.

**What to learn next.** Networking (see Part 10) and Linux administration, which underlie nearly everything. Python for automation of log work. Cloud identity and access basics. Secure software development (see Part 8). Privacy and the legal rules for the data you handle. Detection engineering and incident response in more depth.

**Certifications.** Several vendor-neutral and vendor certifications exist for entry, practitioner and management levels. They can help with screening filters, but they do not replace demonstrated work. Check the current exam objectives, prices and prerequisites on the issuing body's own site before choosing one, as they change.

## Match it in the app

The Practice dashboard has a Cybersecurity track (Tracks, then Cybersecurity) with six tabs: Self-audit, Log analysis, Web checks, Local ports, Crypto labs and Incidents. Use the **Practice** workspace; the Real workspace holds your own data. The app is a guardrail, not a vault, its findings are leads, not verdicts, and it runs on text you paste and on public hosts only. Nothing in it is needed to follow the book.

**Level 1.** In **Self-audit**, read the score and every `warn` or `fail` item (file and fix, never the secret itself). Fix one, for example `chmod 600 backend/.env`, and re-run; the score should rise. In **Crypto labs**, hash `hello` and expect the SHA-256 shown in Level 1; paste it as the expected hash to see a match, then change the text to `Hello` to see a mismatch. Try passwords in Password strength and read the stated assumption under the crack-time estimate.

**Level 2.** In **Log analysis**, load the sample auth log. Expect about five detections, best first: a critical takeover from 203.0.113.50 (eight failed root logins, then success), high-severity guessing and a medium enumeration finding for 198.51.100.7, a low note for `/wp-login.php`, and a high finding for an injection-looking search that returned 200. All addresses are documentation ranges. Use the search box to filter by address. In **Web checks**, enter a public site you own to see header findings and certificate days left; private and local addresses are refused on purpose. In **Local ports**, compare the open list with what you expect (a fixed list, on 127.0.0.1 only).

**Level 3.** Read `backend/app/services/seclogs.py` (thresholds `BRUTE_N`, `BRUTE_WINDOW`, `ENUM_USERS`), `security.py` (hashing, strength, TOTP) and `selfaudit.py`. In the TOTP lab create a practice secret, match its four explanation steps to `totp()`, and try an old code. Edit a copy of the sample log (spread failures over 30 minutes, or use four) and predict whether each detection fires. For each self-audit check, note one false-reassurance case, such as the secret scan knowing only six key formats.

**Level 4.** In **Incidents**, log a "Lost or stolen device" incident, work its checklist, add timeline notes, and move the status through investigating, contained and resolved; read the mean hours to resolve. It is a personal-scale tracker, not a team ticketing system. Then compare your own playbook with `docs/CYBERSECURITY.md`.

**Capstones.** Capstone 1 can use the Self-audit scores and the Backups page; Capstone 2 the Log analysis and Incidents tabs.

**What the app does not cover.** It does not scan networks or other machines, assess vulnerabilities in software, monitor endpoints, or review cloud configuration. It has no labs for authentication flows, access-control testing, encryption beyond hashing and TOTP, threat modelling, risk registers, policy writing or tabletop exercises. Log analysis handles one pasted file, with no live collection, correlation across sources or alert routing. Offensive tools (Nmap, Burp Suite, Metasploit, Kali) are taught about in Level 4 and the Tools reference, never built. Treat the app as practice for Levels 1 and 2 habits, and do the rest on your own.
