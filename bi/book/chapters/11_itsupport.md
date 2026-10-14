# Part 11: IT Specialist

## The role in one page

An IT specialist keeps people productive. You fix what is broken, protect the data, know what the organisation owns, and write things down so the next person can repeat the fix. In a small business you are the whole IT department; in a larger one you may be on a help desk, a desktop team or an infrastructure team.

**Who you work with.** Everyone, which is the point. Staff who are stuck and often stressed, managers who approve access and spending, network and security colleagues (see Parts 9 and 10), vendors who sell and repair equipment, and auditors who ask how you know what you claim.

**A typical day.** Read the ticket queue and sort by impact and age. Reset a locked account (after verifying who is asking). Fix a printer. Onboard a new starter: account, groups, laptop, multi-factor sign-in. Check backup reports and disk space. Spend an hour on a project (a patch cycle, a script, a documentation page). Close tickets with notes a stranger could follow.

**What good looks like.**

- People are told what is happening and when, even when the answer is "not yet".
- Problems are solved by method: ask what changed, check the cheap causes first, change one thing at a time.
- Every device and account is known, owned and recorded; leavers lose access the same day.
- Backups are tested by restoring, not by trusting a green tick.
- Fixes are documented, so the second occurrence takes five minutes.

**What it is not.** It is not magic, and it is not just resetting passwords. It is not a licence to read anyone's mail or files out of curiosity: you hold powerful access and the job runs on trust. It is also not the same as a developer, network engineer or security analyst, though you will borrow from all three.

**Honest hard parts.** Interruptions never stop. People describe symptoms in their own words, and the first report is often wrong. You carry the blame for problems you did not cause. Priorities collide (the director's laptop versus the server). On-call and out-of-hours work are common. And practice trackers are only personal-scale: production support needs real systems, an approvals process and your employer's policies.

## How to use this part

Four levels; times assume about five hours a week.

| Level | Focus | Estimated time |
|---|---|---|
| 1 Foundations | Method, tickets, hardware and OS basics, accounts, first network checks | 20 hours (about 4 weeks) |
| 2 Practitioner | Active Directory, PowerShell, inventory, event logs, joiners and leavers | 30 hours (about 6 weeks) |
| 3 Advanced | Capacity, availability, RAID, backups, email authentication, patching | 35 hours (about 7 weeks) |
| 4 Expert | Service management, privilege, scale, ethics, disaster recovery | 30 hours (about 6 weeks) |

Capstones add 15 to 40 hours each.

**Pair the reading with practice.** Do the sums by hand first, then check them in a spreadsheet or a few lines of Python. Each level ends with "Practice on your own": labs with your own computers, a spreadsheet, virtual machines and free tools.

**Honest limits.**

- A personal ticket log and inventory teach the habits; production support needs real systems, an approvals process and your employer's policies.
- Simple SLA clocks count elapsed hours, not business hours.
- Log patterns are leads, not verdicts; only well-known event IDs are covered here.
- RAID is not a backup. Forecasts that assume straight-line growth are rough.
- Check a command before running it on a production machine.
- Active Directory, Group Policy, Entra ID and Intune, ticketing suites and backup products are taught about here, not built in.
- Active Directory, Group Policy, Entra ID and Intune, ticketing suites and backup products are taught about here, not built in.

## Level 1: Foundations (beginner)

### What you will be able to do

- You can write a ticket that someone else could act on without calling the user.
- You can set priority from impact and urgency and say what the SLA clock means.
- You can explain what a decimal terabyte looks like to Windows, and why storage "disappears".
- You can reset an account safely: verify, reset, force a change, check MFA.
- You can read `ipconfig /all` and say what each field rules out.
- You can follow the five habits on a real problem and write down the fix.

### Core ideas

#### The method

Five habits carry most of the job. First, **ask before you touch**: what changed, when did it last work, who else is affected? Second, **cheapest explanation first**: power, cable, restart, typo, expired password. Third, **one change at a time**, recorded, so you know what fixed it. Fourth, **confirm with the person**, not just on your screen. Fifth, **document the fix**.

**Worked example.** "I can't print." Questions: just you? since when? any error text? Check the printer is on and online, then the right default printer, then the queue. Clear the queue and restart the print spooler (`Restart-Service Spooler`). Print a test page, confirm with the user, and note "stuck job in queue, cleared by restarting the spooler". Keep a checklist per category (hardware, software, network, account, email, printer, other) that follows this order.

#### Writing a good ticket

A ticket is a small contract. It needs: who asked, what is wrong in the user's own words, exact error text or a screenshot, what they already tried, when it started, impact (how many people, what work is blocked) and your running notes with times. Bad: "Email broken." Good: "Maria (Accounts): Outlook shows 'cannot connect to server' since 08:40; webmail works; two colleagues unaffected; she did not change anything; laptop was updated last night." The good version already points at the desktop client rather than the mail service, and it tells whoever picks it up what to skip.

Keep notes factual and blameless. Tickets are read later by managers, auditors and your future self, and "user is clueless" in a ticket is a career mistake.

#### Priority and the SLA clock

Priority comes from **impact** (how many people, how critical the work) and **urgency** (how soon it hurts). One person cannot print: low or medium. The whole office has no internet: urgent. A simple scheme uses elapsed-hours targets such as urgent 4, high 8, medium 24, low 72. The clock is simply opened time to now (or to resolved time).

**Worked example.** A high ticket opened at 09:00 has a target of 17:00 the same day. A medium ticket opened Friday 16:00 breaches at Saturday 16:00 on this clock, even though nobody works Saturday. That is the honest limit: a simple elapsed clock does not model business hours or pausing the clock while you wait for the user. Real systems do, and you will learn to define such rules in Level 4. Resolved within SLA means age at resolution is at or below the target.

#### Hardware and storage basics

A computer is a CPU, memory (RAM, volatile), storage (SSD or hard disk, persistent), a power supply and a board connecting them, plus the display and network. Check the cheap physical causes first: power, cables, indicator lights, a known-good swap.

Storage units trip everyone up. Drive makers use decimal units (1 TB = 1,000,000,000,000 bytes); Windows reports binary units (1 GiB = 1,073,741,824 bytes), shown as "GB". So a "1 TB" drive appears as about 931 GB: 10^12 divided by 2^30 is 931.3. Nothing is missing. Remember it before someone raises a ticket claiming a faulty disk. Also note that a new disk needs partitioning and formatting before it is usable, and formatting erases everything.

#### Accounts, passwords and MFA

Every action should be tied to a named account with only the access it needs (**least privilege**). The commonest ticket is "locked out" or "forgot password". The safe routine is: verify identity first (a callback to a known number or a manager's confirmation, never just the caller's word), check for a lockout or expiry, reset the password to a temporary one, require a change at next sign-in, confirm that multi-factor authentication (MFA) still works, and glance for repeated failures that suggest an attack. Social engineers call help desks for exactly this reason.

Teach people to use a password manager and long passphrases. Never ask for a password, and never send one by email or chat in clear text. Record who approved any access change.

#### First network checks

You do not need to be a network engineer to triage. On a Windows machine run `ipconfig /all`. Look for: an IPv4 address (a 169.254.x.x address means DHCP did not answer), a default gateway, and DNS servers. Then `ping <gateway>`, `ping 8.8.8.8`, `ping example.com`. If the first two succeed and the name fails, it is DNS. If the gateway fails, think cable, Wi-Fi or VLAN. If only one user is affected, change their cable, port or access point before blaming the network. For Wi-Fi, `netsh wlan show interfaces` shows signal and channel. Escalate to the network engineer with your findings written in the ticket, not just "network is down" (see Part 10).

### Practice on your own

1. **Tickets.** In a spreadsheet or a free helpdesk tool, log five tickets of different categories and priorities. For each, record times and what you tried, in order.
2. **Resolve two.** Compute the age at resolution and whether each met its target. Leave one open and note when it would breach.
3. **Checklist.** Write a "set up a new computer" checklist for your own setting, then follow it on a spare machine or VM.
4. **Method.** Pick a real problem on your own devices (slow Wi-Fi, a printer) and apply the five habits, writing the ticket as you go.

### Exercises

1. Rewrite "Wi-Fi bad" as a good ticket for someone who will pick it up without talking to the user.
2. What priority is: (a) one person cannot print, (b) the payroll system is down on payday, (c) the whole office has no internet?
3. A medium ticket is opened Monday 10:00. When does the clock say it breaches?
4. A "2 TB" drive shows in Windows as about how many GB?
5. Someone phones asking you to reset the finance director's password because she is travelling. What do you do?
6. A laptop has IP 169.254.10.5. What does that tell you and what do you check?
7. Name four things to record when you close a ticket.
8. List the first three questions you ask on any report of "it stopped working".

### Answers and hints

1. Example: "Ahmed (Sales, 2nd floor): laptop shows Wi-Fi connected but pages load in 30+ seconds since Monday 09:00; phone on same Wi-Fi is fine; happens near the window desks; signal shows 2 bars."
2. (a) low or medium, (b) urgent or high (impact and a hard deadline), (c) urgent.
3. Tuesday 10:00 (24 elapsed hours).
4. 2 x 10^12 / 2^30 = about 1,862 GB.
5. Do not reset on the phone request alone. Verify through a known channel (call her back on the number on file, or get a manager's confirmation), reset to a temporary password, force a change, confirm MFA, and note it in the ticket.
6. DHCP did not answer. Check the cable or Wi-Fi association, the VLAN, and whether the DHCP server or relay is up; then renew.
7. The cause, the fix, the time, who confirmed, and anything to prevent a repeat.
8. What changed, when did it last work, and who else is affected?

### Checkpoint

1. What are the five habits?
2. What makes a ticket actionable?
3. How do impact and urgency set priority?
4. What does the SLA clock measure here, and what does it not model?
5. Why does a 1 TB drive show as 931 GB?
6. How do you verify a caller before a reset?
7. What does 169.254.x.x mean?
8. Why record every change?

Common mistakes:

- Changing three things at once, then not knowing what fixed it.
- Skipping identity verification because the caller sounds convincing.
- Closing a ticket without asking the user to confirm.
- Writing vague tickets ("email broken") that force repeat questions.
- Treating a failed ping as proof of a dead path.
- Working out of hours on a production change with no backup.

## Level 2: Practitioner (intermediate)

### What you will be able to do

- You can explain users, groups, organisational units and Group Policy in Active Directory.
- You can write short PowerShell commands that query and report, and say what each does before you run it.
- You can keep an inventory that answers "what do we own and when does it expire?"
- You can read an event log export and pick the first finding to investigate.
- You can run joiner and leaver processes in the right order.

### Core ideas

#### Active Directory and Group Policy

Active Directory (AD) is the directory service of a Windows domain: it holds users, computers and groups, and domain controllers answer sign-in requests (Kerberos or NTLM). Objects live in **organisational units** (OUs). Give access to **groups**, not people: put users in a role group, and grant the group access to the resource. Then onboarding is "add to group" and offboarding is "remove from groups".

**Group Policy** applies settings to users and computers. Policies apply in the order Local, Site, Domain, OU (later wins unless enforced). `gpupdate /force` pulls policy now; `gpresult /r` shows which policies applied to this user and computer. When a setting "does not apply", check the OU the object is in, the link, the security filtering, and replication. AD is practised in a VM with a free evaluation Windows Server; Entra ID and Intune are cloud services and out of scope here.

```
Unlock-ADAccount jsmith
Search-ADAccount -LockedOut
Get-ADGroupMember "Finance-Users"
dcdiag
```

#### PowerShell for reporting

PowerShell passes **objects** down the pipeline, not text, so you filter on properties. Learn the pattern: get, filter, select, output. Always preview before changing: `-WhatIf` shows what would happen.

```
Get-Service | Where-Object Status -eq Stopped
Get-Process | Sort-Object CPU -Descending | Select-Object -First 10
Get-Volume
Get-ADUser -Filter 'Enabled -eq $false' | Select-Object Name, SamAccountName
Search-ADAccount -AccountInactive -TimeSpan 90.00:00:00 -UsersOnly | Select-Object Name, LastLogonDate
```

The last line lists accounts inactive for 90 days, a leaver-cleanup report. Note that `LastLogonDate` is derived from a replicated attribute that can lag by up to about two weeks, so treat the list as candidates to check, not accounts to delete. Bulk work from a CSV is the usual next step: `Import-Csv new.csv | ForEach-Object { ... }`, run first with `-WhatIf`. Anything destructive gets a dry run and a second pair of eyes.

#### Inventory and lifecycle

You cannot protect or support what you do not know exists. An inventory records at least: name, kind, OS, owner, serial, purchase date, warranty end and status (in use, spare, repair, retired). A useful rule: flag warranties ending within 90 days as expiring and those in the past as expired, ignoring retired assets.

**Worked example.** Today is 2026-10-09 and a laptop's warranty ends 2026-12-15. Days left: 22 to the end of October, 30 more to the end of November, 15 into December: 67. That is within 90, so "expiring": decide whether to renew, replace or accept the risk. A server with no warranty date shows "unknown"; that is a gap to fix. The inventory also exposes your OS mix: three machines on an unsupported OS is a risk to report. The tracker is manual; real organisations use tools such as Snipe-IT or GLPI, or management software with discovery, but the fields and the discipline are the same.

#### Reading event logs

Windows records events in the Application, Security and System logs. Event Viewer exports to CSV, and `Get-WinEvent` queries from PowerShell. Learn the common IDs: 4624 successful logon, 4625 failed logon, 4740 account lockout, 4720 account created, 4732 member added to a local group, 7045 service installed, 1102 security log cleared, 41 and 6008 unexpected shutdown.

**Worked example.** Six failed logons for `bob` from 203.0.113.9 two seconds apart, then a lockout, then a successful logon from the same address; then an account `svc_backup2` is created, someone is added to Administrators, a service called `updater` is installed, and the audit log is cleared. Each event may be innocent; together they form the classic pattern of a credential guess, a foothold, persistence and cover-up. A success after failures from the same address is the part to rate highest. Response: disable and reset the account, isolate the machine, preserve the logs before touching more, find who created the new account, and escalate to security (see Part 9). It is a lead, not proof; the Event Viewer remains the source of truth.

#### Joiners, movers and leavers

Keep four checklists: onboard, offboard, new PC, outage. Order matters. **Onboard:** create the account, add to groups (least privilege), enrol MFA, create the mailbox, image and record a device, install standard software, grant app access, explain the password manager and how to ask for help, and record who approved the access. **Offboard:** disable the account (do not delete yet), reset the password and sign out all sessions, revoke MFA devices and tokens, remove from groups, handle the mailbox as policy says, collect and wipe devices (and update the inventory), transfer file ownership, cancel licences and finally delete after the retention period.

Why disable first? You keep the data and the audit trail and can reverse a mistake, while access ends immediately. **Movers** (changing role) are the forgotten third case: remove the old group memberships as you add the new ones, or people accumulate access over the years.

### Practice on your own

1. **Inventory.** Record your own computers, phones and router in a spreadsheet with serial, purchase date, warranty end and status. Which warranties end within 90 days? What OS mix do you have?
2. **Event logs.** On a Windows machine or VM, open Event Viewer, filter Security for 4624 and 4625 and export to CSV. Then fail a few sign-ins on purpose on a test account and find them. Write the first three actions you would take on the Level 2 pattern, in order.
3. **Evidence.** Remove the successful logon from that pattern and say which conclusion becomes weaker, and what that teaches about evidence.
4. **Joiners and leavers.** In a lab domain (a free evaluation Windows Server in a VM), create a test user, add to a group, then offboard in the right order. Write the one step you would add for your own workplace.

### Exercises

1. Why give a share access through a group rather than to each user?
2. Write a PowerShell line that lists stopped services.
3. A laptop's warranty ends 2026-11-20. Today is 2026-10-09. How many days are left, and would you call it expiring if your threshold is 90 days?
4. What does event ID 4625 repeated 30 times from one IP suggest? What do you check next?
5. What does event 1102 mean and why does it matter?
6. A leaver's account was deleted on their last day and now the manager wants their files. What went wrong in process?
7. Order these offboarding steps: delete account, disable account, collect laptop, revoke MFA.
8. Why is `LastLogonDate` not enough to delete accounts?

### Answers and hints

1. Group membership is the unit you add and remove: one change at onboarding or offboarding, and the access is auditable.
2. `Get-Service | Where-Object Status -eq Stopped`.
3. 22 + 20 = 42 days (to 31 October, then 20 into November). Under 90, so "expiring".
4. A password guessing or spraying attack, or a stale saved password on a device. Check whether any 4624 success followed from that IP, which accounts were targeted and whether they locked out (4740).
5. The security audit log was cleared, which is a typical way to hide activity. Find who and why.
6. Deleting immediately: disable first, keep for the retention period, transfer ownership of files.
7. Disable, revoke MFA, collect the laptop, delete after retention.
8. It can lag by about two weeks and does not reflect all kinds of use (for example service accounts that never "log on" interactively). Verify before removal.

### Checkpoint

1. What is an OU, and what is Group Policy?
2. What does `gpresult /r` tell you?
3. Why do PowerShell pipelines pass objects?
4. What fields does your inventory need?
5. How would you define "expiring" for warranties, and what would you do at that point?
6. Which event IDs are you looking for in a suspected account takeover?
7. Why disable before delete?
8. What is a mover and why does it matter?

Common mistakes:

- Granting permissions directly to people instead of groups.
- Running a bulk command without `-WhatIf` or a test group.
- Forgetting to update the inventory when a device changes hands.
- Reading a single event in isolation.
- Deleting leavers' accounts before the retention period.
- Forgetting movers.

## Level 3: Advanced

### What you will be able to do

- You can forecast when a disk reaches a warning level and decide when to order.
- You can convert an availability target into permitted downtime and combine components.
- You can compute RAID usable space and explain what each level does and does not protect.
- You can design a backup scheme with RPO and RTO and calculate backup time.
- You can explain SPF, DKIM and DMARC and fix a common mail-delivery fault.

### Core ideas

#### Capacity planning

Disks fill quietly and then loudly. The forecast is simple: measure used space, measure monthly growth, and divide the room to the warning level by the growth.

**Worked example.** A 1 TB disk (1,000 GB) is 70% used (700 GB), growing 25 GB per month. The warning level of 80% is 800 GB: 100 / 25 = 4.0 months. Full is 300 / 25 = 12 months. Order storage before the warning date, because purchasing, delivery and migration take weeks; a plan keyed to "full" is a plan to fail. A spreadsheet gives the same dates. The limit is honest: growth is straight-line, but real growth is lumpy (a new project, a one-off video, a backup job gone wrong), so re-measure monthly. Include CPU, memory and licence counts in the same habit.

#### Availability and downtime

Availability is the fraction of time a service works. Permitted downtime follows from arithmetic on 8,766 hours in an average year: 99% allows about 87.7 hours; 99.9% about 8.77 hours; 99.99% about 52.6 minutes (a month, about 4.4 minutes). Each extra nine costs far more than the one before.

Components combine. In **series** (the service needs both), multiply: two systems of 99.9% give 0.999 x 0.999 = 99.8%. In **parallel** (either one is enough), multiply the failure rates: two 99% systems give 1 - 0.01 x 0.01 = 99.99%, if failures are independent, which they often are not (shared power, shared network, the same bad update). Agree the target with the business, because "always up" is not a number. The Availability calculator turns a percentage into downtime per day, month and year.

#### RAID: availability, not backup

RAID combines disks to survive a failure or gain speed. With N disks of S terabytes: RAID 0 stripes (usable N x S, no protection, one failure loses everything). RAID 1 mirrors (usable S, survives all but one disk failing). RAID 5 keeps one disk of parity (usable (N-1) x S, survives one failure, needs at least 3 disks). RAID 6 keeps two (usable (N-2) x S, survives any two, needs at least 4). RAID 10 mirrors pairs then stripes them (usable N/2 x S, survives one failure per pair, needs 4 or more and an even count).

**Worked example.** Four 4 TB disks: RAID 5 gives 12 TB (75% efficient), RAID 6 gives 8 TB, RAID 10 gives 8 TB. Six 8 TB disks in RAID 5 give 40 TB. Large disks rebuild slowly, and a second failure or a read error during the rebuild can destroy a RAID 5 array, which is why RAID 6 is preferred for big disks.

**RAID does not protect against deletion, corruption, ransomware, a failed controller or a fire.** A deleted file is deleted on every disk. RAID keeps the service running; a backup brings the data back.

#### Backups, RPO and RTO

The **3-2-1 rule**: three copies, on two different media, one off-site, and add one copy that cannot be changed or deleted by an attacker (offline or immutable). **RPO** (recovery point objective) is how much data you can afford to lose, as time; it sets backup frequency. **RTO** (recovery time objective) is how long you can afford to be down; it sets the method and hardware. A backup you have not restored is a hope, not a backup: schedule restore tests.

Types: **full** copies everything; **incremental** copies changes since the last backup of any kind; **differential** copies changes since the last full. Restoring Thursday after a Sunday full: with incrementals you need Sunday plus Monday, Tuesday, Wednesday and Thursday (five sets); with differentials you need Sunday plus Thursday (two).

**Worked example: backup time.** A 500 GB full over 1 Gbps at 85% efficiency: 4 x 10^12 bits / 8.5 x 10^8 = about 4,706 seconds, or 78 minutes. Over 100 Mbps: 4 x 10^12 / 8.5 x 10^7 = about 47,059 seconds, or 13 hours. That decides whether nightly fulls are realistic. Tools: robocopy `/MIR` (which deletes at the destination, so test first), `rsync -avh --dry-run` to preview, and products such as Veeam or restic.

#### Email authentication and patching

Mail sent as your domain is judged by three DNS records. **SPF** lists who may send: a TXT record such as `v=spf1 include:_spf.example.com -all`. **DKIM** signs messages with a key published in DNS. **DMARC** says what to do when checks fail and where to report: a TXT record at `_dmarc.example.com`, such as `v=DMARC1; p=none; rua=mailto:dmarc@example.com`. Start with `p=none` to observe, then move to quarantine and reject once legitimate senders pass. If outside recipients report that your mail bounces or lands in spam, check these three first, and use `dig TXT example.com +short` to see the records.

Patching is the other recurring duty: test on a small group, roll out in waves, keep a rollback plan, and report what is out of date. On Linux, `sudo apt update && sudo apt upgrade` and `systemctl status`, `journalctl -u <service> -n 100`, `df -h` and `last -n 20` are the daily tools.

### Practice on your own

1. **Forecast.** In a spreadsheet, enter used 700 GB of 1,000, growth 25 GB a month, warning at 80%. Confirm 4 months to warning and 12 to full, then try growth of 50.
2. **Availability.** Compute downtime per year and per month for 99.5%, 99.9% and 99.99%.
3. **RAID and virtual disks.** In a VM, build a RAID 1 or RAID 5 array with virtual disks (Linux `mdadm` or your hypervisor), remove a disk, and watch the array degrade and rebuild. Then delete a file and notice RAID does nothing about it.
4. **Backup drill.** Back up a folder with restic or rsync to a second disk, delete something, and restore it. Write an RPO and RTO for a business you know.

### Exercises

1. A 2,000 GB volume is 1,200 GB used with 40 GB monthly growth. When does it reach 80%?
2. What downtime per year does 99.5% allow?
3. Five 6 TB disks: usable space in RAID 5, RAID 6, RAID 10 (can it be built?).
4. Two systems each 99.5% in series: combined availability?
5. Nightly full of 250 GB over 200 Mbps at 85%: how long?
6. A user says "RAID means I do not need backups." Reply in two sentences.
7. Why might your DMARC `p=reject` break a legitimate newsletter?
8. Design a backup for a 5-person office: media, frequency, RPO, RTO, test.

### Answers and hints

1. 80% of 2,000 is 1,600; (1,600 - 1,200) / 40 = 10 months.
2. 0.005 x 8,766 = about 43.8 hours.
3. RAID 5: 4 x 6 = 24 TB; RAID 6: 3 x 6 = 18 TB; RAID 10 needs an even number, so five disks cannot.
4. 0.995 x 0.995 = 0.990, about 99.0%.
5. 250 x 8 x 10^9 = 2 x 10^12 bits; 170 Mbps; about 11,765 seconds, or 3.3 hours.
6. RAID survives a disk failure but copies deletion, corruption and ransomware to every disk. Only a separate, tested backup recovers them.
7. The newsletter service may not be in SPF or signing with DKIM for your domain; add it before enforcing.
8. Example: daily encrypted backup to a NAS plus a nightly copy to cloud storage (off-site) and a weekly offline disk; RPO 24 hours, RTO 1 working day; restore a random file monthly and a full machine twice a year.

### Checkpoint

1. How do you forecast a disk-full date?
2. What does 99.9% allow per year?
3. Series versus parallel availability?
4. What does each RAID level survive?
5. Why is RAID not a backup?
6. What are RPO and RTO?
7. Incremental versus differential?
8. What do SPF, DKIM and DMARC each do?

Common mistakes:

- Ordering storage for the full date instead of the warning date.
- Assuming independent failures when systems share power or a network.
- Treating a mirrored disk as a backup.
- Never testing a restore.
- Running `robocopy /MIR` the wrong direction.
- Enforcing DMARC before auditing senders.

## Level 4: Expert and professional judgement

### What you will be able to do

- You can separate incident, problem and change, and measure a service with more than a mean.
- You can design privileged access so one stolen password is not a disaster.
- You can standardise and automate support so it scales past one person.
- You can handle privacy, evidence and honesty properly when you hold powerful access.
- You can plan and rehearse recovery from a major failure.

### Core ideas

#### Service management and honest metrics

Three ideas, common to the practices usually grouped as ITIL, keep a team sane. An **incident** is an interruption to restore now. A **problem** is the underlying cause, found afterwards so it does not recur. A **change** is a planned alteration, with approval, a test and a rollback. Most big outages are changes that skipped a step.

Design SLAs deliberately: separate first response from resolution, define business hours, and pause the clock while you wait for the user (a simple elapsed-hours clock does none of this). Beware the mean. Resolution times of 1, 2, 2, 3 and 48 hours have a mean of 56 / 5 = 11.2 hours, but a median of 2: the mean describes nobody's experience. Report the median and the slowest 10% as well, and tickets breached, not only averaged. After any significant incident write a blameless review: timeline, impact, cause, what worked, and actions with owners and dates.

#### Privilege and trust

Administrators are the target. Give staff a standard account for daily work and a separate admin account used only for admin tasks, never for email or browsing. Require MFA on admin access. Use unique local administrator passwords per machine (a tool such as Windows LAPS exists for this; check current documentation) rather than one shared password in a spreadsheet. Keep one sealed break-glass account for emergencies, monitored so any use raises an alert. Review group memberships on a schedule: access only ever accumulates unless someone prunes it. Log administrator actions, and keep the logs off the machine that can be tampered with (event 1102 is the clue that someone cleared one).

#### Scale: standard builds, documentation and automation

One person fixing each machine by hand does not scale. Build every device the same way from an image or script, keep a knowledge base of short runbooks written from real tickets, and automate the repeating tasks (account creation from a form, a weekly inactive-account report, disk-space alerts). Use the inventory as the source of truth: if a machine is not in it, it does not exist for patching, warranty or offboarding. Plan the lifecycle (replacement is usually planned in the range of three to five years; it varies) from warranty dates, so refresh is a budget line, not an emergency. Monitoring (Zabbix, Nagios and similar) should tell you before users call.

#### Ethics, privacy and evidence

You can read other people's mail, files and logs; that does not mean you may. Access only what the task requires, under a written policy, and record why. If you find something sensitive, stop and escalate; do not share it. Preserve evidence before you fix: take copies of logs, note times, avoid wiping a compromised machine until security says so. Be honest in reports: say what you know, what you inferred and what you could not verify. A tool's finding is a lead, not a verdict; do not accuse a colleague on a log line. Never take shortcuts that violate policy because someone senior asks; write down the request and escalate.

#### Disaster recovery and failure modes

Disasters are usually boring: ransomware, a failed controller, a flooded room, an expired certificate, a mistyped command that deleted a share. For each critical service, write down the single points of failure, the RPO and RTO, the restore steps and who does them. Then rehearse. A backup restore test, a "pretend the file server is gone" exercise and a contact-tree call prove more than any document. The Outage checklist (confirm, status message, what changed, dependencies, roll back, restore first and cause second, tell people, write the note) is the pattern. Include the dull dependencies: power, DNS, directory, certificates, licences, and the password manager itself. Keep a printed copy of the recovery plan and the keys to unlock encrypted disks somewhere that does not depend on the systems being recovered.

### Practice on your own

1. **Metrics.** Log ten tickets (real or staged, in a spreadsheet) with times chosen so three breach. Compute the mean and median resolution time yourself. Which tells the truer story?
2. **Incident report.** Take the Windows event pattern from the Level 2 example (or a fabricated export for a lab VM) and write a one-page incident report: timeline, impact, confidence, evidence preserved, actions.
3. **Leaver drill.** In a lab domain, run your offboarding checklist for a test user and update your inventory so the returned laptop shows as spare or retired.
4. **Capacity.** Build a one-year capacity plan for three of your own disks from two measurements a month apart.

### Exercises

1. Mean and median for resolution times 1, 1, 2, 3, 3, 5, 30 hours.
2. Name three reasons to use a separate admin account.
3. What belongs in a blameless review?
4. Why disable rather than delete a leaver at once, and when do you delete?
5. A director asks you to read an employee's mailbox "just to check". What do you do?
6. Write a three-line RPO and RTO statement for an accounts server.

### Answers and hints

1. Sum 45, mean 6.4 hours; median (middle of seven) 3 hours.
2. A phished daily account has no admin power; admin sessions are logged separately; admin credentials are not exposed to browsing and email.
3. A factual timeline, impact, root cause, what helped and hindered, and actions with owners and dates, with no blame on individuals.
4. Disabling ends access but keeps data and audit trail and is reversible. Delete after the retention period set by policy.
5. Ask for a written request approved under policy (HR or legal), record it, and limit access to what is asked. Do not do it informally.
6. Example: RPO 4 hours (backup every 4 hours); RTO 8 hours (restore to spare hardware or a VM); tested quarterly.

### Checkpoint

1. Incident versus problem versus change?
2. Why report the median?
3. What is a break-glass account?
4. Why must the inventory be the source of truth?
5. What do you do before wiping a compromised machine?
6. When may you read a user's files?
7. Name three dull dependencies of recovery.
8. Why rehearse recovery?

Common mistakes:

- Using one shared admin password everywhere.
- Quoting a mean without the spread.
- Reading user data out of curiosity.
- Writing a recovery plan that lives only on the failed system.
- Skipping the post-incident review once the pressure is off.

## Capstone projects

### 1. The home-office help desk

**Brief.** Run your own IT for four weeks as if it were an organisation. **Deliverables:** 15 tickets (real or staged) with notes and resolutions; a complete inventory; one filled-in onboarding and offboarding checklist; mean time to resolve and SLA results; a one-page summary of lessons. **Rubric (1 to 4 each):** tickets are actionable; priority is justified; inventory complete with warranty dates; checklists adapted; metrics read honestly.

### 2. Backup and recovery plan

**Brief.** Design and test a backup for a five-person office with a file server and cloud mail. **Deliverables:** inventory of data and its value, RPO and RTO per system, a 3-2-1 design including an immutable copy, backup-time calculations, capacity forecast for a year, restore test results and a one-page runbook. **Rubric:** RPO and RTO justified; arithmetic correct; restore actually tested; RAID not counted as backup; plan survives loss of the building.

### 3. IT operations handbook

**Brief.** Write the handbook for a 25-person company. **Deliverables:** support process and SLA table (with business hours and pause rules), joiner, mover and leaver procedures, admin-account design, patch policy, monitoring and alerts, an event-log triage guide, a disaster-recovery plan with a rehearsal report, and a privacy and acceptable-access policy. **Rubric:** procedures are testable; privilege is least; metrics are honest; ethics are explicit; someone else could run it on Monday.

## Tools reference

| Tool | What it is for | When you outgrow it |
|---|---|---|
| Ticketing system (osTicket, GLPI or a service desk product) or a spreadsheet | Tickets, notes, priorities and SLA clocks | Email intake, portals, business hours, reporting |
| Asset inventory (a spreadsheet, Snipe-IT or management suites) | Recording assets and warranties | Discovery and lifecycle tools |
| Event Viewer, `Get-WinEvent`, central logging | Reading Windows events | SIEM products and central log collection |
| Spreadsheet or script | Capacity forecasts, downtime and RAID sums | Monitoring with real trend data |
| Checklists and runbooks (wiki or documents) | Repeatable process and command reminders | A maintained knowledge base |
| Active Directory, Group Policy | Directory and policy for Windows networks | Cloud identity (Entra ID) and device management (Intune) |
| PowerShell, Bash, Python | Automation and reporting | Configuration management and pipelines |
| VirtualBox, Hyper-V, Proxmox | Safe labs to break things | Production virtualisation platforms |
| Remote tools (RDP, SSH) | Support machines remotely | Managed remote-support platforms |
| Veeam, restic, rsync | Backup and file copy | Enterprise backup with immutability and reporting |
| Zabbix, Nagios | Monitoring and alerts | Observability platforms |

## Glossary

- **AD (Active Directory)**: Microsoft's directory service for users, computers and groups.
- **Asset**: any device, licence or service you own and must track.
- **Backup**: a separate, restorable copy of data. Not the same as RAID or sync.
- **Break-glass account**: a sealed emergency admin account whose use triggers an alert.
- **Change**: a planned alteration with approval, test and rollback.
- **DKIM**: a mail signature verified through a DNS key.
- **DMARC**: a DNS policy for what to do when SPF or DKIM fail.
- **Differential backup**: changes since the last full backup.
- **Event ID**: a number identifying a type of Windows event, such as 4625.
- **Full backup**: a copy of everything.
- **GPO (Group Policy Object)**: a bundle of settings applied to users or computers.
- **Incident**: an interruption to a service to be restored quickly.
- **Incremental backup**: changes since the last backup of any kind.
- **Least privilege**: only the access needed for the task.
- **MFA**: multi-factor authentication.
- **Mean and median**: the average, and the middle value; resolution times need both.
- **Mover**: someone changing role, whose old access must be removed.
- **OU**: an organisational unit, a container in AD.
- **Problem**: the underlying cause of incidents.
- **RAID**: combining disks for availability or speed. Not a backup.
- **RPO**: recovery point objective, how much data loss is tolerable.
- **RTO**: recovery time objective, how long an outage is tolerable.
- **Runbook**: step-by-step instructions for a recurring task.
- **SLA**: a target for response or resolution time.
- **SPF**: a DNS record listing who may send mail for a domain.
- **3-2-1 rule**: three copies, two media, one off-site.
- **Warranty**: the vendor's repair or replacement commitment, with an end date.

## Career notes

**Roles it leads to.** Help desk analyst, desktop support technician, IT specialist, systems administrator, IT manager for a small business, cloud or endpoint administrator, security operations analyst, and with automation skills, infrastructure or site reliability engineer. Network engineering (Part 10) and cybersecurity (Part 9) are close neighbours.

**How to show your skill.** Keep the capstones: an anonymised ticket log with mean and median, an inventory, a tested backup plan, an event-log incident report and a handbook. Show scripts with `-WhatIf` and comments. Interviewers value a calm account of how you handled a real problem and what you documented afterwards. Your experience dealing with people under pressure in other work counts here, and you should say so.

**What to learn next.** Active Directory and Group Policy in a lab, then cloud identity and device management; PowerShell and scripting; networking (Part 10); backup and recovery design; basic security practice (Part 9); and service management. Entry-level and vendor certifications exist for support, systems and security; check the current exam objectives before choosing any, and use them as a study structure rather than a substitute for hands-on lab time.

## Match it in the app

Everything above works with a spreadsheet, your own computers and a virtual machine. If you also have the practice dashboard, its IT panel (`ItPanel`, logic in `services/itlab.py`, endpoints in `routers/it.py`, notes in `docs/IT_SPECIALIST.md`) matches the levels as follows. Work in the Practice workspace and do the sums by hand first.

**Level 1.** On the Helpdesk tab open tickets with a category and priority (urgent 4, high 8, medium 24, low 72 hours). Each category carries a checklist that follows the method; tick items and add timeline notes. Resolve two tickets and read the stats: open, past target, mean time to resolve and resolved within SLA. The Cheat sheets tab lists the five habits.

**Level 2.** On the Inventory tab add your own assets with owner, serial and warranty end; warranties inside 90 days show as expiring, past ones as expired, and the OS mix is counted. On the Event logs tab paste the built-in sample (or a CSV export with an Id column): you should see a table of event IDs with their meanings and findings such as repeated failed logons, a success from the same address and a cleared audit log. The Checklists tab holds onboard, offboard, new PC and outage lists with ticks. The Cheat sheets tab has PowerShell, Active Directory and Linux command groups.

**Level 3.** On Capacity and RAID, enter used 700, total 1000, growth 25, warning 80 to see 4 months to warning and 12 to full; the availability calculator turns a percentage into downtime per day, month and year; the RAID calculator gives usable space for levels 0, 1, 5, 6 and 10 and prints the caveat that RAID is not a backup. The Backups and recovery cheat group covers 3-2-1, RPO, RTO and safe copy commands.

**Level 4.** Use the Helpdesk with staged tickets to compare mean and median yourself; the app shows only the mean. Use the Event logs sample for the incident-report exercise, the offboarding checklist plus inventory for the leaver drill, and the Capacity tab for the capacity plan.

**What the app does not cover.** The helpdesk and inventory are personal-scale trackers: no email intake, user portal, business hours, paused clocks or network discovery. Event log findings are leads, not verdicts, and only well-known IDs are named. Capacity uses straight-line growth. There is no Active Directory, Group Policy, Entra ID, Intune, remote support, patching, monitoring, backup software or email authentication (SPF, DKIM, DMARC) checking; practise those in a VM or lab. Cheat sheets are static, so check a command before running it on a production machine. Service management, privileged access design, ethics and disaster recovery (Level 4) are judgement skills the app can only support with notes and checklists.
