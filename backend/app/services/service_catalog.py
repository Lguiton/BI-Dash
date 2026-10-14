"""Your service list: what you can sell, what the client gets, how long it usually takes and which part of this dashboard helps you deliver it.
Hours and rates are starting points you can change. Nothing here is a market price; set rates that suit your area and experience."""
from __future__ import annotations

from app.services import state

GROUPS = {
    "bi": "Analytics and BI",
    "ds": "Data science and machine learning",
    "data": "Data cleanup and engineering",
    "cpe": "Computer engineering",
    "net": "Network engineering",
    "it": "IT support and repair",
    "sec": "Cybersecurity (defensive)",
    "ai": "AI engineering",
    "pm": "Project and product management",
    "fs": "Full stack software",
    "biz": "Business consulting and leadership",
    "devops": "DevOps, cloud and DevSecOps",
    "mkt": "Digital marketing and revenue operations",
    "ux": "UI/UX and graphic design",
    "health": "Health data, informatics and BI",
    "stat": "Statistics, genomics and research",
}
DEFAULT_RATES = {"bi": 75, "ds": 85, "data": 70, "cpe": 85, "net": 85, "it": 75, "sec": 90, "ai": 105, "pm": 90, "fs": 90, "biz": 145, "devops": 95, "mkt": 65, "ux": 70, "health": 100, "stat": 80}   # USD per hour, set from the Las Vegas price research (Oct 2026); change in Services


def _s(id_, group, name, deliver, hours, model, tool, needs=""):
    return {"id": id_, "group": group, "name": name, "deliverable": deliver, "hours": list(hours), "model": model, "tool": tool, "needs": needs}


SERVICES = [
    # --- Analytics and BI
    _s("bi-setup", "bi", "Business dashboard setup", "A working dashboard on the client's own numbers with 4 KPIs, a trend and breakdowns, plus a 30 minute walkthrough.", (4, 8), "fixed", "Business dashboards, Import, Custom builder", "Their data in CSV, Excel or a similar file"),
    _s("bi-monthly", "bi", "Monthly KPI report", "A client report each month: plain-English summary, key numbers vs last period, wrong-way alerts and next actions.", (1.5, 3), "monthly", "Client report (PDF), Explain this number", "A monthly data export from the client"),
    _s("bi-kpi-design", "bi", "KPI and metric definition workshop", "A one-page list of the numbers that matter, how each is calculated, owner and target.", (3, 6), "fixed", "KPIs, Explain this number, Glossary"),
    _s("bi-budget", "bi", "Budget vs actual and cash view", "A budget-vs-actual dashboard with variances and a simple cash runway.", (4, 8), "fixed", "CFO agent, Scenario what-if, Company"),
    _s("bi-whatif", "bi", "What-if and pricing scenarios", "A short scenario pack: price change, a hire, a lost account, a cost cut, with runway and yearly effect.", (2, 4), "fixed", "CFO agent scenario tool"),
    _s("bi-audit", "bi", "Reporting health check", "A review of how a business reports today with a ranked fix list.", (3, 5), "fixed", "Data quality, Health check"),
    _s("bi-train", "bi", "Dashboard training session", "A recorded or live session teaching staff to read and update their dashboard.", (1, 2), "hourly", "Explain this number, Glossary, Quiz"),
    _s("bi-adhoc", "bi", "Ad-hoc analysis", "A written answer to one business question, with the query, the numbers, caveats and a recommendation.", (2, 5), "fixed", "Toolbox: Question to answer, Analysis notebook", "The question and the data"),
    _s("bi-survey", "bi", "Survey analysis", "Survey results read fairly: counts, ranges around each percentage, group comparisons and a plain summary.", (3, 6), "fixed", "Toolbox: Survey and A/B analyzer, Pivot", "The survey export"),
    _s("bi-client-pack", "bi", "Client-ready dashboard and report pack", "A designed one-page client report, a data story with a recommendation, and a KPI dictionary.", (4, 8), "fixed", "Toolbox: Dashboard designer, Data story, KPI dictionary", "Their data and the KPIs they care about"),
    _s("bi-sched", "bi", "Scheduled reports and alert rules", "A monthly report that builds itself plus a few alert rules for the numbers that must not slip.", (3, 6), "monthly", "Toolbox: Scheduled reports, Alert rules"),
    # --- Data science
    _s("ds-forecast", "ds", "Sales or demand forecast", "A tested forecast with accuracy shown honestly and what to do with it.", (6, 12), "fixed", "Forecast, ML Lab, Build model", "At least a few months of dated history"),
    _s("ds-churn", "ds", "Customer or job outcome model", "A model that predicts an outcome (late, lost, repeat) with the biggest drivers explained.", (8, 16), "fixed", "Build model, Predict, ML Lab", "A table with past outcomes"),
    _s("ds-segment", "ds", "Customer segmentation", "Customer groups with a plain description of each and a suggested action.", (6, 10), "fixed", "Analysis Lab, ML Lab"),
    _s("ds-ab", "ds", "A/B test or experiment read-out", "Whether a change really worked, with the maths and a recommendation.", (3, 6), "fixed", "Analysis Lab, Calculator"),
    _s("ds-anomaly", "ds", "Anomaly and fraud flagging", "A list of unusual transactions or readings with reasons.", (5, 10), "fixed", "Analysis Lab, Data quality"),
    _s("ds-notebook", "ds", "Analysis write-up", "A clear written analysis of one question, with charts and the method.", (6, 12), "fixed", "Analyst agent, Python Lab"),
    _s("ds-health", "ds", "Model health check", "A review of an existing model: how it was tested, whether it beats a simple guess, drift on recent data and a keep/retrain verdict.", (3, 6), "fixed", "Toolbox: Model drift check, Model card", "The model's data and recent outcomes"),
    _s("ds-feasible", "ds", "Will this predict anything? (feasibility study)", "A short study that says honestly whether your data can predict an outcome, before any money is spent building it.", (3, 6), "fixed", "Model studio, Toolbox: Forecast studio", "A table with past outcomes"),
    _s("ds-handoff", "ds", "Model card and handoff pack", "A plain-English model card with purpose, tests, limits and a drift-check plan, ready to give to a client.", (2, 4), "fixed", "Toolbox: Model card, Model drift check"),
    # --- Data cleanup and engineering
    _s("data-clean", "data", "Data cleanup and merge", "Messy spreadsheets cleaned, de-duplicated, standardised and combined into one tidy table.", (3, 10), "fixed", "Any-file import, Test first (sandbox), Cleaning", "Copies of the files"),
    _s("data-migrate", "data", "Spreadsheet to database move", "A set of spreadsheets moved into a proper database with a schema and a refresh routine.", (8, 20), "fixed", "SQL Lab, Pipelines, Star schema"),
    _s("data-pipeline", "data", "Automated data refresh", "A scheduled job that loads new data, checks it and alerts on problems.", (6, 14), "fixed", "Pipelines, Sources, Alerts"),
    _s("data-quality", "data", "Data quality review", "A report of duplicates, gaps and wrong values with fixes and rules to stop them returning.", (3, 6), "fixed", "Data quality, Expectations"),
    _s("data-backup", "data", "Backup and recovery set-up", "Automatic backups to a second place, a tested restore and a one-page recovery guide.", (2, 4), "fixed", "Backups, Backup copy folder, Health check"),
    _s("data-schema", "data", "Schema and data contract set-up", "A written contract of columns, types and rules, checked automatically, plus a change detector that warns when a source shifts shape.", (3, 8), "fixed", "Toolbox: Data contract, Schema change detector", "A sample of the source data"),
    _s("data-weekly", "data", "Stop the weekly spreadsheet mess", "The weekly copy-and-paste replaced by a scheduled load, a contract check and one dashboard, run in parallel for a month first.", (10, 24), "fixed", "Sources, Pipelines, Toolbox: Data contract", "The current spreadsheets and the steps done by hand"),
    _s("data-dedupe", "data", "Duplicate and merge clean-up", "Duplicates found and removed and files merged safely into new tables, with a before-and-after count and one-click undo.", (3, 8), "fixed", "Toolbox: Dedupe and merge", "Copies of the files"),
    _s("data-sizing", "data", "Data volume sizing", "An honest estimate of storage, memory and speed for your data volume, and what to use at that size.", (1, 3), "fixed", "Toolbox: Volume estimator"),
    # --- Computer engineering
    _s("cpe-pc", "cpe", "Custom PC build and set-up", "A parts list to budget, a built and tested PC, drivers, updates and a data transfer.", (3, 6), "fixed", "How to repair: PC build, Windows toolkit"),
    _s("cpe-embedded", "cpe", "Arduino, ESP32 or Raspberry Pi project", "A small working device (sensor, relay, display) with wiring, code and documentation.", (8, 24), "fixed", "Engineering Mathematician, CPE Lab", "A clear spec and parts"),
    _s("cpe-logic", "cpe", "Digital logic and number-system help", "Worked solutions for Boolean logic, number bases, Gray code, ASCII, parity and checksums, with the steps shown.", (1, 3), "hourly", "Engineering Mathematician agent"),
    _s("cpe-board", "cpe", "Electronics fault finding", "A diagnosis of a dead device to the failed part, with a repair quote or a replacement advice.", (1, 3), "hourly", "How to repair: multimeter, soldering, electronics"),
    _s("cpe-hardware", "cpe", "Hardware upgrade and data move", "RAM, SSD and battery upgrades with a full clone so nothing is lost.", (1.5, 3), "fixed", "How to repair: laptop upgrade"),
    _s("cpe-doc", "cpe", "Technical documentation", "Wiring diagrams, bills of materials and user guides for a build.", (3, 8), "fixed", "Diagram studio"),
    # --- Network engineering
    _s("net-home", "net", "Home or small-office Wi-Fi and mesh design", "A site plan, the right gear, wired backhaul where possible, tested coverage and a one-page map.", (3, 6), "fixed", "How to repair: mesh, router, Ethernet crimp"),
    _s("net-secure", "net", "Network security tidy-up", "Guest and IoT separation, updated firmware, strong Wi-Fi, a device list and a checklist.", (2, 4), "fixed", "Security tools, Health check, How to repair: mesh security"),
    _s("net-cabling", "net", "Cabling and patch panel job", "Cable runs, terminated and tested, labelled, with a port map.", (3, 10), "fixed", "How to repair: Ethernet crimp", "Site visit"),
    _s("net-cctv", "net", "CCTV and alarm installation", "Cameras, recorder, PoE switch, remote viewing through a VPN, and a handover.", (4, 12), "fixed", "How to repair: CCTV, recorder, alarm panel"),
    _s("net-vlan", "net", "VLAN, DHCP and addressing plan", "An addressing plan with VLANs, DHCP scopes and reservations for a business.", (4, 10), "fixed", "Net tools, DHCP guide, dnsmasq generator"),
    _s("net-monitor", "net", "Network monitoring and troubleshooting", "A monitoring set-up with alerts and a diagnosis of slow or dropping connections.", (3, 8), "fixed", "Ops monitor, Log explorer, Honeypot"),
    # --- Cybersecurity (defensive only, on systems the client owns or has authorised in writing)
    _s("sec-checkup", "sec", "Small-business security checkup", "A graded hardening review of one or two Windows PCs, the website check and a short findings report with the fix order.", (3, 6), "fixed", "Cybersecurity: Endpoint hardening, Self-audit, Web header and TLS checks, Client handoff pack", "The client's OK to run a read-only script on their PCs"),
    _s("sec-web", "sec", "Website security review", "Security headers and certificate checked on the public site, with plain-English fixes and a re-check.", (1, 2), "fixed", "Cybersecurity: Web header and TLS checks", "A public website address"),
    _s("sec-web-monthly", "sec", "Monthly website watch", "A monthly re-check of headers and certificate expiry with a one-paragraph summary.", (0.5, 1), "monthly", "Cybersecurity: Web header and TLS checks, Clients"),
    _s("sec-logs", "sec", "Log review", "Sign-in or web server logs read for repeated failures and odd requests, with leads to follow up and what to change.", (2, 5), "fixed", "Cybersecurity: Log analysis", "Copies of the logs (remove customer data first if you can)"),
    _s("sec-passwords", "sec", "Password and two-step sign-in clean-up", "A password manager set up, authenticator-app 2FA on the owner's key accounts, and a one-page habits sheet.", (2, 4), "fixed", "Cybersecurity: Password strength, TOTP lab", "The owner present to approve each account change"),
    _s("sec-ir-plan", "sec", "Incident response plan", "A one-page 'what to do if we are hacked' plan with contacts, first steps and a practice run.", (2, 4), "fixed", "Cybersecurity: Incident tracker, Playbook simulator"),
    _s("sec-incident", "sec", "Calm-down help after an incident", "A walk-through after a suspected hack: what to secure first, what to check and what to tell customers. No guarantee of recovery.", (2, 6), "hourly", "Cybersecurity: Incident tracker, Log analysis"),
    _s("sec-risk", "sec", "Risk and policy worksheet", "Data sorted by importance (confidentiality, integrity, availability), a NIST-style self-check and the top five fixes. A readiness checklist, not a compliance audit.", (3, 6), "fixed", "Cybersecurity: Frameworks lab, STRIDE worksheet, CVSS score"),
    _s("sec-code", "sec", "Code and secrets check", "A pasted-code review for exposed keys, unsafe queries and risky patterns, with line numbers and safer versions to read before using.", (1, 3), "fixed", "Full Stack: Code Workbench; Cybersecurity: code pattern scanner", "Code the client owns"),
    _s("sec-aware", "sec", "Staff security awareness session", "A one-hour session on phishing, passwords and backups with a short quiz and a handout.", (2, 3), "fixed", "Cybersecurity labs, Quiz"),
    # --- IT support and repair
    _s("it-laptop", "it", "Laptop repair (screen, keyboard, battery, upgrades)", "A repaired and tested laptop with a short report of what was found.", (1, 3), "fixed", "How to repair: laptops by make"),
    _s("it-phone", "it", "Phone and tablet repair", "Screen, battery, charging-port and software repairs with a data backup first.", (0.75, 2), "fixed", "How to repair: phones by make"),
    _s("it-virus", "it", "Virus, slow PC and Windows repair", "A cleaned, updated and sped-up PC with a protection check.", (1, 3), "fixed", "How to repair: Windows toolkit, malware cleanup"),
    _s("it-data", "it", "Data recovery attempt", "A recovery attempt with a list of what was found. No promise on results.", (2, 5), "fixed", "How to repair: data recovery, USB and card"),
    _s("it-printer", "it", "Printer set-up and repair", "A printer installed on the network, with scanning and a reservation, or repaired.", (0.75, 2), "fixed", "How to repair: printers"),
    _s("it-onsite", "it", "On-site IT visit", "Troubleshooting of whatever is wrong, billed by the hour.", (1, 4), "hourly", "How to repair (all), Windows shortcuts"),
    _s("it-retainer", "it", "Small-business IT care plan", "Monthly check of backups, updates, antivirus and Wi-Fi, plus support requests.", (2, 4), "monthly", "Health check, Backups, Briefing"),
    _s("it-auto-elec", "it", "Car audio, dash cam and accessory wiring", "Neat, fused installs that do not drain the battery.", (1.5, 4), "fixed", "How to repair: car audio, dash cam, car drain"),
    # --- Computer engineering additions
    _s("cpe-logger", "cpe", "Sensor or data-logger kit", "A working sensor build with parts list, wiring notes, tested code and a test plan.", (6, 14), "fixed", "Parts list checker, Battery runtime estimator, Sketch writer, Test plan", "The measurements wanted and where it will be installed"),
    _s("cpe-bom", "cpe", "Hardware specification and parts list", "A checked parts list with prices, pin and power budget and risks.", (2, 5), "fixed", "Parts list checker"),
    # --- Data science: text and documents
    _s("ds-text-sort", "ds", "Text and ticket sorting", "A model that sorts emails, tickets or comments into your categories, with an honest accuracy report and a 'needs a person' queue.", (8, 20), "fixed", "Text classifier, Labeling workbench", "A few hundred labeled examples, or time to label them"),
    _s("ds-doc-extract", "ds", "Document field extraction", "Rules that pull amounts, dates and IDs from documents, tested on real samples.", (6, 16), "fixed", "Extraction tester", "20 or more sample documents"),
    _s("ds-doc-search", "ds", "Document search", "Search over a client's documents that finds the relevant passages.", (8, 20), "fixed", "NLP and Deep Learning studio", "The documents and consent to process them"),
    # --- AI engineering
    _s("ai-assistant", "ai", "AI assistant or workflow build", "A working assistant for one job with its instructions, tests and cost estimate.", (10, 30), "fixed", "Eval runner, Prompt library, LLM cost estimator", "A clearly described job and sample questions"),
    _s("ai-risk", "ai", "AI readiness and risk review", "A review of where AI fits, with a risk register and a data-privacy summary.", (3, 8), "fixed", "AI risk register, Handoff pack"),
    _s("ai-evals", "ai", "Prompt and evaluation pack", "A tested prompt set with a pass-rate report you can rerun after any change.", (5, 12), "fixed", "Eval runner, Prompt library"),
    _s("ai-cost", "ai", "AI cost and privacy review", "A monthly cost forecast with ways to cut it, and a review of what data leaves the building.", (2, 5), "fixed", "LLM cost estimator, AI risk register"),
    # --- Project and product management
    _s("pm-plan", "pm", "Project plan and schedule", "A task list with estimates, dependencies, milestones and a critical path.", (3, 8), "fixed", "Estimator, Project track"),
    _s("pm-risk", "pm", "Risk register", "A ranked list of project risks with owners and actions.", (2, 4), "fixed", "Project track"),
    _s("pm-reqs", "pm", "Requirements and user stories", "Testable user stories with acceptance criteria the client signs off.", (3, 8), "fixed", "User-story writer"),
    _s("pm-sprint", "pm", "Sprint and board set-up", "A working board, rules and a first sprint planned.", (2, 5), "fixed", "Project track"),
    _s("pm-status", "pm", "Weekly status reporting", "A one-page report each week: health, done, next, risks and decisions needed.", (1, 2), "monthly", "Status report"),
    _s("pm-roadmap", "pm", "Roadmap and prioritization", "A now, next, later roadmap with the reasons for the order.", (3, 6), "fixed", "Roadmap builder"),
    _s("pm-rescue", "pm", "Project rescue", "A diagnosis of a late or stuck project and a re-plan with a date everyone agrees.", (4, 10), "fixed", "Status report, Estimator, Decision and retro log"),
    _s("pm-sow", "pm", "Proposal and statement of work", "A clear scope document with deliverables, price, exclusions and change process.", (2, 5), "fixed", "SOW writer", "A brief from the client"),
    # --- Full stack
    _s("fs-app", "fs", "Small web app or internal tool", "A working web app with database, forms and reports, deployed.", (20, 60), "fixed", "Scaffold writer, API contract writer, Deploy runbook", "A written list of what it must do"),
    _s("fs-api", "fs", "API and database design", "A designed API contract and table layout, ready to build.", (4, 12), "fixed", "API contract writer, Scaffold writer"),
    _s("fs-bugs", "fs", "Bug fixes and code review", "Fixes for named bugs and a review report with a ranked list.", (2, 8), "hourly", "Code review report, Code Workbench", "Access to the code"),
    _s("fs-sheet", "fs", "Spreadsheet-to-app migration", "A tested app that replaces a shared spreadsheet with the data moved over.", (16, 40), "fixed", "Scaffold writer", "The spreadsheet and a list of who uses it"),
    _s("fs-care", "fs", "Site maintenance plan", "Monthly updates, backups, uptime checks and small fixes.", (2, 4), "monthly", "Deploy runbook"),
    # --- Business consulting and leadership
    _s("biz-diag", "biz", "Business diagnosis and action plan", "Interviews, a numbers check, a SWOT and a three-action plan with owners and dates.", (6, 14), "fixed", "SWOT builder, Decision matrix"),
    _s("biz-okr", "biz", "Goals and OKR set-up", "A quarter of measurable objectives and key results with an owner and a weekly check-in rhythm.", (3, 6), "fixed", "OKR builder"),
    _s("biz-sop", "biz", "Procedures and SOP writing", "Written, tested procedures for the tasks that matter, each with an owner and review date.", (2, 5), "fixed", "SOP writer"),
    _s("biz-lead", "biz", "Leadership coaching and team workshop", "A half-day workshop or a coaching block on meetings, decisions and change, with a one-page follow-up.", (3, 8), "fixed", "Decision matrix, Decision and retro log"),
    # --- Project management additions
    _s("pm-itproj", "pm", "IT project management", "Plan, critical path, budget tracking, change control and a go-live checklist for a system rollout.", (10, 40), "hourly", "Critical path, Earned value, Change request, Go-live checklist"),
    _s("pm-health", "pm", "Project budget and schedule health check", "An earned-value review of a running project with a re-forecast and options.", (3, 6), "fixed", "Earned value, Critical path"),
    # --- DevOps, cloud and DevSecOps
    _s("do-pipeline", "devops", "CI pipeline and Docker set-up", "A tested build pipeline and a clean container image, with notes the team can follow.", (6, 16), "fixed", "CI pipeline writer, Dockerfile writer"),
    _s("do-reliab", "devops", "Reliability and delivery review", "Delivery metrics, an uptime target and a ranked list of fixes for deploys and alerts.", (4, 8), "fixed", "Delivery metrics (DORA), Uptime budget"),
    _s("do-cloud", "devops", "Cloud design and cost review", "A one-page cloud design, a cost estimate and a recovery pattern matched to the business's limits.", (6, 16), "fixed", "Cloud cost estimator, Availability calculator, Disaster recovery picker"),
    _s("do-migrate", "devops", "Cloud migration plan", "A system-by-system plan (retire, retain, repurchase, replatform, rehost) with a first rehearsal move.", (8, 20), "fixed", "Migration helper"),
    _s("do-dso", "devops", "DevSecOps pipeline hardening", "Secrets scanning, workflow and dependency checks and a security gates checklist added to the pipeline.", (6, 14), "fixed", "Secrets scanner, Pipeline checker, Dependency checker, Security gates checklist"),
    # --- Cybersecurity additions
    _s("sec-revsys", "sec", "Revenue-system access and risk review", "A review of who can touch billing, CRM and payments with a conflict report and SaaS inventory.", (4, 10), "fixed", "Access review, SaaS inventory and risk"),
    _s("sec-pci", "sec", "Card-payment scope review", "A plain-English view of card-data exposure with steps to shrink it.", (2, 4), "fixed", "Card-data scope helper"),
    # --- Data science: computer vision
    _s("ds-cv", "ds", "Image detection or inspection pilot", "A small detector pilot on the client's images with an honest score report.", (16, 40), "fixed", "Label audit, Detection scorer", "A few hundred labeled images"),
    _s("ds-cv-audit", "ds", "Image label and dataset audit", "A report on label problems, class balance and the metrics that matter before more labeling money is spent.", (3, 8), "fixed", "Label audit, Box overlap (IoU)"),
    # --- Digital marketing and revenue operations
    _s("mkt-campaign", "mkt", "Ad campaign review", "A review of spend, click and sale numbers against break-even with the three changes most likely to help.", (3, 6), "fixed", "Campaign metrics"),
    _s("mkt-content", "mkt", "Social media content plan", "A month of planned posts across the right platforms, with templates and a tracking sheet.", (4, 10), "fixed", "Content calendar, UTM link builder"),
    _s("mkt-manage", "mkt", "Social media management", "Posting, replies and a monthly report on what worked.", (6, 14), "monthly", "Content calendar, UTM link builder, Campaign metrics"),
    _s("rev-funnel", "mkt", "Sales funnel and pipeline review", "A funnel report showing the weakest stage and the pipeline needed to hit the target.", (3, 8), "fixed", "Funnel and pipeline coverage"),
    _s("rev-econ", "mkt", "Unit economics and pricing check", "A page showing lifetime value, payback and the churn or cost changes that would make growth profitable.", (2, 5), "fixed", "Unit economics"),
    # --- UI/UX and graphic design
    _s("ux-audit", "ux", "Accessibility and usability audit", "A prioritised list of contrast, readability and flow problems with fixes.", (4, 10), "fixed", "Contrast checker, Usability test plan"),
    _s("ux-system", "ux", "Colour and type system", "A palette, type scale and spacing rules the client can reuse, with contrast checked.", (4, 10), "fixed", "Palette builder, Type scale, Contrast checker"),
    _s("ux-test", "ux", "Usability test", "A five-person test with a short report of what to fix first.", (8, 16), "fixed", "Usability test plan"),
    _s("ux-brand", "ux", "Logo, flyer and social graphics", "A small set of on-brand graphics with agreed revision rounds.", (4, 12), "fixed", "Palette builder, Type scale"),
    # --- Health data, informatics and BI
    _s("hd-kpi", "health", "Healthcare KPI definitions and dashboard", "A written KPI dictionary and a dashboard spec (or build) for a facility reader such as an administrator or director of nursing.", (8, 24), "fixed", "Healthcare KPI calculator, Dashboard spec", "Aggregate data, not patient-level records"),
    _s("hd-staff", "health", "Staffing and quality report", "A monthly report of staffing hours per resident day, agency share, falls and pressure injuries.", (3, 6), "monthly", "Healthcare KPI calculator"),
    _s("hd-rate", "health", "Rates and benchmarking review", "Rates with confidence intervals, age adjustment and observed-versus-expected ratios you can defend.", (4, 10), "fixed", "Rate with interval, Age adjustment, Observed vs expected"),
    _s("hd-deid", "health", "De-identification review", "A scan and manual review of a dataset for identifiers, with a list of fields to drop or generalise.", (3, 8), "fixed", "Identifier scanner", "Made-up or de-identified sample first"),
    _s("hd-cohort", "health", "Cohort table and diagnostic accuracy analysis", "A baseline table, test accuracy and survival figures from de-identified data.", (6, 16), "fixed", "Cohort table, Test accuracy, Survival curves"),
    _s("hd-interface", "health", "Interface specification and message review", "A written interface spec and a review of sample messages and codes (HL7, FHIR or files).", (6, 16), "fixed", "HL7 reader, FHIR check, Code format checker, Interface spec"),
    # --- Statistics, genomics and research
    _s("st-analysis", "stat", "Statistical analysis and write-up", "The right tests with effect sizes and intervals, written up in plain language.", (4, 14), "fixed", "Compare two groups, Table of counts (chi-square), Confidence interval"),
    _s("st-power", "stat", "Study design and sample size", "A sample size with assumptions, a randomization schedule and a protocol outline.", (3, 8), "fixed", "Sample size, Randomization, Protocol outline"),
    _s("st-multi", "stat", "Multiple-testing and results check", "A review of many-test results with adjusted values and a clear statement of what holds up.", (2, 5), "fixed", "Multiple testing, Correlation"),
    _s("st-genomic", "stat", "Sequence and variant data summary", "QC-style summaries of sequences or a variant file, with filters and a plain report.", (4, 12), "fixed", "Sequence summary, VCF summary, Hardy-Weinberg check", "Non-identifiable data or proper consent"),
    _s("st-research", "stat", "Research support (planning, citations, reproducibility)", "Help organising a study: question, plan, data management and a reproducible analysis.", (3, 10), "hourly", "Protocol outline, Citation formatter"),
]


def rates() -> dict:
    saved = state.setting_get("real", "service_rates", None) or {}
    return {g: float(saved.get(g, DEFAULT_RATES[g])) for g in GROUPS}


def set_rates(new: dict) -> dict:
    cur = rates()
    for g in GROUPS:
        if g in new:
            v = float(new[g])
            if not 0 <= v <= 2000:
                raise ValueError("A rate must be between 0 and 2000 per hour.")
            cur[g] = v
    state.setting_set("real", "service_rates", cur)
    state.audit("service_rates", ", ".join(f"{g}={v:g}" for g, v in cur.items()))
    return cur


def catalog() -> dict:
    r = rates()
    items = []
    for s in SERVICES:
        lo, hi = s["hours"]
        rate = r[s["group"]]
        items.append({**s, "rate": rate, "low": round(lo * rate, 2), "high": round(hi * rate, 2)})
    return {"groups": [{"id": k, "name": v, "rate": r[k]} for k, v in GROUPS.items()], "services": items,
            "note": "Hours and rates are starting points. Change the hourly rate for each group to match your market; monthly services are priced per month."}


def quote(lines: list[dict], client: str = "", discount_pct: float = 0.0) -> dict:
    by = {s["id"]: s for s in SERVICES}
    r = rates()
    out, total_lo, total_hi = [], 0.0, 0.0
    for ln in lines:
        s = by.get(str(ln.get("id")))
        if not s:
            raise ValueError("Unknown service in the quote.")
        qty = max(1, min(int(ln.get("qty") or 1), 50))
        lo, hi = s["hours"]
        rate = r[s["group"]]
        out.append({"id": s["id"], "name": s["name"], "qty": qty, "model": s["model"], "hours": [lo * qty, hi * qty], "low": round(lo * rate * qty, 2), "high": round(hi * rate * qty, 2)})
        total_lo += lo * rate * qty
        total_hi += hi * rate * qty
    d = max(0.0, min(float(discount_pct or 0), 50.0)) / 100
    return {"client": client[:80], "lines": out, "subtotal": [round(total_lo, 2), round(total_hi, 2)], "discount_pct": round(d * 100, 1),
            "total": [round(total_lo * (1 - d), 2), round(total_hi * (1 - d), 2)], "note": "A range based on the typical hours. Confirm the final price once you have seen the work."}


# ------------------------------------------------------------------ Henderson / Las Vegas price list (researched October 2026)
# Market = published ranges from Las Vegas firms and national freelance guides; "price" is set roughly 10-20% under them.
# Rows with market "Estimate" had no direct source. Ranges change; treat as a starting point.
PRICE_LIST_DATE = "2026-10-13"


def _p(service, gets, market, price):
    return {"service": service, "gets": gets, "market": market, "price": price}


PRICE_LIST = [
    {"group": "Everyday tech help (homes and individuals)", "rows": [
        _p("Remote tech support", "Fix slowdowns, setup, email, printer and Wi-Fi help over screen share", "$40-50/mo plans; about $60/hr local", "$55/hr, 1 hour minimum"),
        _p("In-home visit, computer or network", "Virus cleanup, setup, router and Wi-Fi tuning, data transfer", "$50-150 on-site; $125-175/hr at pro shops", "$75/hr + $40 trip (Henderson or Las Vegas)"),
        _p("Personal data backup setup", "Automatic backup plan and a restore test", "Part of IT plans", "$95 flat"),
    ]},
    {"group": "Small business IT and security (1 to 25 staff)", "rows": [
        _p("IT support, hourly", "Break-fix and help-desk work", "$125-175/hr; after hours $175-250", "$105/hr; after hours $150/hr"),
        _p("Monthly IT care plan", "Check-ins, updates, backups, user help", "$100-200 per user/mo (average about $145)", "$85-125 per user/mo, 5-user minimum"),
        _p("Onboarding and setup", "Inventory, accounts, backups, security baseline", "$1,200 to $10,000", "$900-3,500"),
        _p("Basic security checklist review", "Defensive review of accounts, email, backups and devices with a written fix list", "$5,000-15,000 at firms", "$1,500-4,500 for a small office"),
        _p("Compliance gap review (starter)", "Gap list against a framework with a plain-English plan", "$8,000-20,000", "$4,500-12,000"),
    ]},
    {"group": "Data, BI and analytics", "rows": [
        _p("Data analyst, hourly", "Cleaning, analysis, answers to business questions", "Mid $65-120/hr; senior $120-200", "$60-95/hr"),
        _p("Custom dashboard", "A dashboard from your sheets or database with a walkthrough", "Marketplace $90-200 (lowest tier); local pro work is far higher", "$900-3,500"),
        _p("Monthly reporting retainer", "Refreshed dashboards and a monthly summary", "$300-1,500/mo", "$300-1,200/mo"),
        _p("Spreadsheet and data cleanup", "Fix, merge, de-duplicate, automate", "Analyst hourly rates", "$60/hr or $250-900 flat"),
        _p("Statistics and study analysis", "Tests, models and a clear written results summary", "$40-150/hr; from scratch $60-80", "$55-110/hr"),
    ]},
    {"group": "Web, design and marketing", "rows": [
        _p("Small business website", "Up to 5 pages, mobile friendly, contact form", "$1,800-5,500 local freelance", "$1,500-4,800"),
        _p("Web design, hourly", "Edits and extras", "$75-150/hr", "$65-95/hr"),
        _p("Website care plan", "Updates, backups, small edits", "$75-200/mo", "$65-175/mo"),
        _p("Logo", "Concepts, revisions, files for print and web", "$300-800", "$250-700"),
        _p("Social media graphics", "Posts and story images", "$25-150 each; packages $200-1,500/mo", "$20-120 each; $180-1,300/mo"),
        _p("Brand starter package", "Logo, colors, fonts, guidelines", "$3,500-12,500", "$2,800-9,500"),
        _p("Social media management", "Plan, post, reply, monthly report", "$500-2,000/mo", "$450-1,700/mo"),
        _p("UI/UX design, hourly", "Screens, flows, prototypes", "$65-100/hr mid-level", "$55-90/hr"),
        _p("App or site design project", "A handful of screens, a visual direction, a component set", "$10,000-25,000 (US)", "$7,500-19,000"),
    ]},
    {"group": "Consulting, project management, software and AI", "rows": [
        _p("Business consulting, hourly", "Process, strategy and leadership advice", "$150-300/hr at advisory firms", "$110-180/hr"),
        _p("Business assessment", "Review, findings and a prioritized plan", "$1,500-5,000", "$1,200-4,000"),
        _p("Advisory retainer", "Standing monthly advice and check-ins", "$2,000-10,000/mo", "$1,500-6,000/mo"),
        _p("Project management, hourly", "Plans, schedules, status, risk tracking", "Estimate (no direct source)", "$70-110/hr"),
        _p("Software or automation, hourly", "Full-stack features, scripts, integrations", "Estimate (web work $75-150/hr)", "$70-110/hr"),
        _p("AI and ML project work, hourly", "Models, text tools, data pipelines", "Estimate (analytics up to $200/hr)", "$85-130/hr"),
    ]},
]

PRICE_NOTE = ("Set about 10-20% under published Henderson and Las Vegas ranges to stay competitive. Most local figures come from IT firms and agencies, "
              "which carry more overhead than a freelancer. Rows marked Estimate had no direct source. Nevada requires a business license for most work, "
              "and security reviews need a written scope. Raise prices as you collect reviews.")


def price_list() -> dict:
    return {"date": PRICE_LIST_DATE, "groups": PRICE_LIST, "note": PRICE_NOTE}
