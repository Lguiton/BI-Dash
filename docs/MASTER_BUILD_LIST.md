# Master build list

> **Scope (decided Oct 14):** this is Lamarcus's personal dashboard for running his own freelance services. It is not sold or given to clients; clients only receive deliverables (invoices, summaries, reports, handoff packs). The product he sells is **Eivanta Analytics**, a separate project. So: no client logins, no multi-tenant work and no public hosting here. If he hires people later, the next steps are logins, per-person timers and permissions.


What is done, what is next, and what is waiting on a go-ahead. Update this file when something changes.

## Next (agreed)
- [ ] Use the dashboard for real work for a few weeks and write down what annoys you (this decides what to build next).
- [x] Clean-up: header tightened. Work mode, Settings and Save page as PDF now sit beside the page title, and the menu row sits under it, so nothing wraps mid-button.
- [x] Fix log extended to Data and BI, Machine learning and Full-stack: a "Fix log" section on the Analyst, Data Scientist, Data Engineer, ML and Full-stack dashboards in Work mode.

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
- [x] **Sample work page** (built, zip 53): `/samples`, `samples.py`. A separate downloadable page of labelled practice work; the rules are enforced in code (sample label on every item, no emails or phone numbers, no reviews or testimonials, no outside requests). Nothing is published or sent.
- [ ] Launcher `.bat` for the test data (after the dashboard is fully built and tested).
- [ ] Gmail (IMAP) and Google Calendar sign-in. Last; wait until you say ready.
- [x] Live network capture (built, zip 53): Settings > Scanned files and capture. Needs Npcap and administrator rights on Windows, the backend in Windows Python (not WSL), and your own network only. Headers only by default.
- [x] OCR for scanned files (built, zip 53): needs Tesseract on the backend's computer. Every Upload button then reads photos and scanned PDFs.
- [ ] Security review against your transcripts.
- [ ] Optional: NLP and deep-learning "by hand" tabs.
- [ ] Hosting online (login on, HTTPS, strong owner password).
- Compliance library in Settings (Legal and compliance tab) with agent `compliance` tool (security, itsupport).
- Cloud and as-a-service lab with IaC reviewer, templates, real-work checklist, quiz (IT support, Network); agent tools iac_review, cloud_pick.

## Advanced batches (zip 51)
- **IT Support**: `it_admin.py`, `/api/itadmin`, `ItAdminLab` (email authentication check, Microsoft 365 and Intune reference, onboarding and offboarding runbooks, script review, priority matrix, SLA math, stop codes, patch policy), 11 admin repair guides (`it_repair_admin.py`), agent tools `email_auth`, `script_review`, `stop_code`.
- **Security**: `sec_pro.py`, `/api/secpro`, `SecProLab` (CVSS 3.1 calculator, annualized loss and control payback, risk matrix and register, pen-test scope template, OWASP Top 10, attack stages, forensic timeline, Suricata and Snort rule explainer, HIPAA, SOC 2, PCI and continuity checklists), agent tools `cvss`, `risk_ale`, `rule_explain`.
- **Network**: `net_pro.py`, `/api/netpro`, `NetProLab` (OSPF cost, spanning tree root, IPv6 plan, EUI-64, PoE budget, fiber budget, wireless link budget, TCP speed limit, firewall rule review, VPN, QoS, SNMP and monitoring reference), agent tools `fiber_budget`, `poe_budget`, `ipv6_plan`, `firewall_review`, `tcp_limit`.
- **Upload button** reads Excel, PDF and Word (`/api/files/text`); the text sent to the agent grew from 4,000 to 12,000 characters.
- Advanced labs for every field are now built (see Zip 53). Nothing is left in the audit list; quizzes for the new labs are not written yet.
- **"Agents do the job" card** (`JobAgentCard.tsx`) on every real work dashboard (all 12 tracks in Work mode) and on the field pages: pick an open job, then the field's agent and the three-AI team draft the work, with a file upload for the job. Drafts only; nothing is sent, closed or marked done. The job page and the pinned job bar already had the same buttons.

## Zip 52
- **One set of file rules for every upload button** (`frontend/src/lib/fileCheck.ts`): the same plain-English message for an unfinished download (`.crdownload`), an empty file, an old `.xls`, an `.evtx`, a zip or a wrong type, and one accepted-types list per kind (data, text, anything, csv, capture, backup). Text-only readers (security logs, IT events, theme finder) now also take Excel, PDF and Word by converting them first; security logs read UTF-16 exports; the theme finder takes .tsv and .json.
- **Pick a dashboard after Intake** (`intake_handoff.py`, `/api/intake/{id}/suggest` and `/brief`): after a run, "Where do you want to work on this file?" ranks dashboards from the columns, types and file name. Clicking one opens it (`/tracks/<id>?view=tools&run=<id>`) with a "Your uploaded file is ready here" banner (`WorkingFile.tsx`) and one button for that dashboard's agent to start on the file (columns and first rows only, personal-data columns left out).

## Analyst batch (in zip 53)
- `analyst_pro.py`, `/api/analystpro`, `AnalystProLab` on the Analyst dashboard: forecast with a range (checked against "repeat last value"), cohorts and retention (pasted or straight from a table), funnel, Pareto, A/B test, break-even, unit economics, margins, cash runway, cash cycle, NPV and IRR, star schema from a flat table, 10 runnable window-function recipes, SQL to DAX to Tableau to Excel map, dashboard design review, metric definition card, requirements interview and page, report QA checklist and self-service rollout. Agent tools: `forecast_range`, `cohort`, `funnel`, `unit_economics`, `breakeven`, `ab_test`.
- Held on purpose (you said when): launcher .bat (after the build is finished), Gmail and Calendar sign-in (when you say ready), hosting online. Optional: NLP and deep-learning by-hand tabs, security review against your transcripts.


## Zip 53 (includes zips 51 and 52)
- **Advanced labs for the remaining fields**, one shared page (`ProLab.tsx`, `/api/prolab`, `prolab.py` framework, one module per field). Every calculator is also an agent tool for that field.
  - Computer Engineer (`prolab_cpe.py`): state machine check with Verilog, setup and hold timing, pipeline CPI, virtual memory and TLB, average memory access time, UART baud, timer prescaler, I2C pull-ups, ADC resolution and ENOB, op-amp gain, RC filter and order, buck and boost design, DC motor operating point, second-order response, PID from Ziegler-Nichols, PCB trace width, microstrip impedance, reliability and MTBF, derating, plus datasheet, embedded, HDL/FPGA, architecture, bench, standards and PCB-flow references.
  - Full-stack (`prolab_fullstack.py`): JWT checker, OpenAPI lint, Dockerfile review, CI workflow starter, migration lint, Core Web Vitals, accessibility check and contrast, cache maths, queue sizing, password hash cost, plus auth, testing, observability, API design, git and system-design references.
  - Project Manager (`prolab_pm.py`): Monte Carlo schedule risk, critical path, PERT, RACI check, stakeholder map, resource loading, earned value status report, pricing, plus PMBOK, retrospectives, roadmapping, agile, contracts and change references.
  - Systems Analyst (`prolab_sysanalyst.py`): user stories, Mermaid diagrams, process lint, UAT cases, migration mapping and cutover checklist, vendor scoring, change impact, business case, data requirements, integration pattern, plus TOGAF-lite and elicitation references.
  - AI (`prolab_ai.py`): LoRA memory, vector database size, retrieval metrics, chunking, quantization speed, KV cache, LLM cost with caching, prompt comparison, plus red team, guardrails, LLMOps and multimodal references.
  - ML (`prolab_ml.py`): convolution shape, transformer size, LSTM parameters, exact Shapley values, tuning budget, item recommender, forecast metrics (MASE), drift (PSI), serving capacity, bandit simulation, plus experiment tracking.
  - Data Engineer (`prolab_de.py`, track id `engineering`): Kafka sizing, Spark partitions and skew, DAG validator, data contract check, volume anomaly, warehouse cost, small-files compaction, plus lakehouse, streaming and observability references.
  - Data Scientist (`prolab_ds.py`, track id `scientist`): Bayesian A/B, sample size, Kaplan-Meier, linear programming, distance between places, fairness audit, difference in differences, bootstrap interval, plus causal, experiment and ethics references.
- **OCR** (`ocr.py`, `/api/ocr`): photos and scanned PDFs to text through Tesseract; the universal file reader now takes png, jpg, tif, bmp and webp and falls back to OCR for scanned PDFs. Install steps show in Settings when Tesseract is missing.
- **Live capture** (`capture.py`, `/api/capture`): scapy capture on a chosen card, limits (60 s, 5,000 packets), a confirm box, headers only by default, summary through the existing capture reader, save as .pcap.
- **Sample work page** (`samples.py`, `/samples`): see above.
- Fix: the shared `.input` style was never defined (about 60 components used it), so many boxes had no border. It now matches `.field`.
- Not live-tested: AI provider calls. Quizzes for the new labs are not written.

## Launcher (after zip 53)
- `Start BI Dashboard.bat` in the project folder: double-click menu to start (everyday: backend and screen in WSL, scanned-file reading works), start with live capture (asks for administrator, backend in Windows `.venv-win`, screen in WSL), stop everything, or open the dashboard. Builds the screen if it has not been built. Never connects to the internet. Not tested on Windows from here.
- Fixed headers-only capture: records keep 128 bytes but remember the real packet length (matches tcpdump), so Wireshark and the summary no longer see false gaps.
- Capture download is now a clear button.
