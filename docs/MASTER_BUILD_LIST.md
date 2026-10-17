# Master build list

> **Scope (decided Oct 14):** this is Lamarcus's personal dashboard for running his own freelance services. It is not sold or given to clients; clients only receive deliverables (invoices, summaries, reports, handoff packs). The product he sells is **Eivanta Analytics**, a separate project. So: no client logins, no multi-tenant work and no public hosting here. If he hires people later, the next steps are logins, per-person timers and permissions.


What is done, what is next, and what is waiting on a go-ahead. Update this file when something changes.

## Next (agreed)
- [ ] Use the dashboard for real work for a few weeks and write down what annoys you (this decides what to build next).
- [ ] Clean-up: tighten the header so the Settings button does not wrap.
- [ ] Extend the fix log to other fields (data, ML, full stack) if you want a record there too.

## Done recently

- [x] **Known issues and support dates** on the IT repair and Cybersecurity dashboards (work mode): CISA's list of flaws attackers are using (downloaded once a day, searched on your computer) and endoflife.date support dates (only the product name is sent). Free, no key, passive reads. Not yet tested against the live sites; if one cannot be reached it shows the last saved copy with its date. Other free APIs considered: AbuseIPDB (1,000 checks a day, free account), RIPEstat, FRED, Census, Open-Meteo (non-commercial only).

- [x] **One-place job flow**: type the job in the top box and click Go (it suggests dashboards) or **Start as job** (picks a client and a field from your words, creates the job and a first step, opens that field's dashboard). A **pinned job bar** under the top box on every page holds the timer, steps, a quick note, a Field switcher, Switch job and Close job. Home's open jobs have **Work on it**. Fields: IT repair, Networking, Cybersecurity, Data analyst, Data scientist, Machine learning, AI engineering, Engineering, Data engineering, Full stack, Project management, Systems analysis. The field guess uses a "Field:" title prefix, then keywords; you can change it.
- [x] Dropdown lists readable in dark mode.

- [x] Marketing package (Docs) and pitch deck (Slides) for the freelance business: names, slogan, mission, positioning, SWOT, draft prices, channels, 30-day plan. Names not checked for availability; platform fees not verified.

- [x] **My projects** in Settings: quick links to Eivanta Analytics and Project AIDA (open, copy folder path, running check).

- [x] **Learned for Eivanta**: a one-line note on each job page (typed, client names removed), with a markdown download of everything learned.

- [x] **Assistant desk**: approval queue for AI drafts (edit, accept, discard), job descriptions per assistant, activity log with a used rate, your own saved examples (rank first, client names removed), and a closing note drafted for each job that only reaches the client once you accept it.

- [x] **Today panel** on Home: late invoices with a reminder already written (copy it, nothing is sent), follow-ups, late jobs, overdue work, a timer left running over 2 hours, jobs ready to close, and a backup reminder.
- [x] **Recurring jobs** (per client on the Clients page): weekly or monthly, created with their steps once per period when the app runs.
- [x] **AI prep drafts with a daily cap**: OpenAI only, off by default, cap 1 to 50 (default 10), counted per day and kept across restarts. A button on each work item and an AI first look at each table. Optional automatic drafts for new work items. No client names sent.
- [x] **Close-job nudge**: the job page and Today say when every work item is done.

- [x] **One page per job** (`/job?id=`): hours, unbilled amount, work items, fixes for that client, invoices; **Close job** creates the invoice (hours, quoted price, or none) and a client-ready summary page.
- [x] **Work timer**: start/stop on a work item; hours go to the linked job as billable time and onto the invoice. Items not linked to a job keep the time but it is not billed. A timer over 12 hours is capped.
- [x] **Worked examples for the agents**: 24 hand-written approaches (2 per agent) in `backend/app/content/worked_examples.json`, shown as reference when the question shares at least two keywords. Not training; the agent still does not learn.
- [x] Work and Learn modes, one dashboard per field, Settings tabs, the price list and rates.
- [x] Fix log for IT repair, Cybersecurity and Network, with ticket links and secret blanking.
- [x] Work log on the home screen ("What I'm working on").
- [x] Test data script for the Practice workspace.
- [x] Agents read your own past fixes (IT, Cybersecurity, Network) when AI mode is "full".
- [x] "Send to agent" in the Web panel (text from a page goes to the agent as a labelled outside source; save the answer to the fix log).
- [x] Generate code tab (Full Stack field and track): describe it, get checked, risk-scanned code to copy. Never run.
- [x] Agent checks: past-work lookup (free) and field-work questions with a rubric (live).
- [x] AI routing: simple to Gemini, medium to OpenAI, complex (ML, NLP, statistics, math, code) to Claude.
- [x] Practice kits: 20 of the 24 practice jobs now have made-up files to work on, a plain brief, "what done looks like", and a hidden answer key computed from the same data (job page > Practice materials). IT repair and Cybersecurity jobs have none: use your own gear.
- [x] Work team (Practice and Real): type the job in the pinned job bar, "Draft with the team": Gemini, OpenAI and Claude each do it, Claude judges and writes one final draft. Draft only (Assistant desk), off by default, own daily cap, IT/Network/Security give checklists and advice only. In Real, only your instructions and pasted material are seen (client names removed; tables summarised locally).
- [x] Agent follow-ups: a short "yes" / "continue" now stays on the same model, topic and reference material as the answer before it, sends only the last exchange (fewer tokens), and tells the agent not to repeat steps. Agents no longer bring up the manual step unless asked.
- [x] Agents use the dashboard tools: Networking (subnet, VLSM, summarize, overlaps, contains, split, transfer time, bandwidth-delay, config audit, capture reader), IT (capacity, availability, RAID, event logs), Security (log analysis and search), Data analyst and Data scientist (forecast, variance, profit what-if, distribution fit, DAX). Local calculations only; nothing that reaches another computer. Agents can also read the job pinned in the job bar (read-only; practice files included for practice jobs, never the answer key).
- [x] Work mode: on a wide screen the agent sits beside the tools, so you don't switch tabs. On a narrow screen the Tools / AI agent tabs remain.

- [x] Faster job flow: standard steps by field, paste-in client message (rules, draft quote), "Do the next step" agent help, job keyboard shortcuts, Today strip on Home, lazy-loaded dashboard panels (about 38% less JS on a dashboard).

- [x] Client messages (10 types, free templates plus optional AI) and a weekly "who to contact" list on Leads. Decided against a full customer service or marketing dashboard (the Marketing Dashboard is a separate tool).

## Waiting for your go-ahead
- [ ] **Portfolio page** (sample work for prospects): a simple public-facing page, separate from the dashboard, which stays private. Starts after you finish a few practice jobs. Rules: every item labeled "sample" or "practice", no fake reviews or testimonials, no client names or data, made-up data for any sample dashboard. Use before/after, the written quote, and the job summary or checklist PDF as the pieces.
- [ ] Launcher `.bat` for the test data (after the dashboard is fully built and tested).
- [ ] Gmail (IMAP) and Google Calendar sign-in. Last; wait until you say ready.
- [ ] Live network capture (needs Npcap or libpcap and admin rights; your own network only; opt-in).
- [ ] OCR for scanned files (needs Tesseract installed).
- [ ] Security review against your transcripts.
- [ ] Optional: NLP and deep-learning "by hand" tabs.
- [ ] Hosting online (login on, HTTPS, strong owner password).
- Compliance library in Settings (Legal and compliance tab) with agent `compliance` tool (security, itsupport).
- Cloud and as-a-service lab with IaC reviewer, templates, real-work checklist, quiz (IT support, Network); agent tools iac_review, cloud_pick.
