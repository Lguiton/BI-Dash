"""Qualitative analysis: post-mortems, observations, strategy planning and a plain-text theme finder.

Qualitative work explains WHY (past) or frames WHAT TO DO (future) in words and judgement. The numbers here are only
bookkeeping (probability-weighted outcomes, word counts). Notes live in the app's state file, per workspace.
"""
from __future__ import annotations

import json
import math
import re
import uuid
from collections import Counter
from datetime import date

from app.services import state, stats_lab
from app.services.datasets import DataError, q
from app.services.db import fetch_all, get_cursor

MAX_ITEMS = 500
MAX_TEXT = 4000
MAX_LIST = 20
MAX_TEXT_IN = 200_000
MAX_DOCS = 5000

# kind -> {"horizon", "label", "blurb", "fields": [(name, type, label, hint)]}
KINDS: dict[str, dict] = {
    "postmortem": {"horizon": "past", "label": "Post-mortem", "blurb": "Why did a project, launch or process succeed or fail? Blameless: causes, not culprits.",
                   "fields": [("when", "date", "When it ended", ""), ("outcome", "enum:succeeded,mixed,failed", "Outcome", ""),
                              ("what_happened", "text", "What happened (facts, in order)", "Timeline, numbers, who did what."),
                              ("why", "text", "Why it happened (root causes)", "Ask 'why' five times; stop at something you can change."),
                              ("went_well", "list", "What went well", ""), ("went_wrong", "list", "What went wrong", ""),
                              ("lessons", "text", "Lessons", ""), ("actions", "list", "Actions to take next time", "")]},
    "observation": {"horizon": "past", "label": "Observation", "blurb": "Something you noticed in operations: context the numbers can't show.",
                    "fields": [("when", "date", "When", ""), ("area", "line", "Where / which process", ""),
                               ("note", "text", "What you saw", ""), ("so_what", "text", "Why it might matter", "")]},
    "swot": {"horizon": "future", "label": "SWOT", "blurb": "Strengths and weaknesses are inside you; opportunities and threats are outside.",
             "fields": [("strengths", "list", "Strengths", ""), ("weaknesses", "list", "Weaknesses", ""), ("opportunities", "list", "Opportunities", ""),
                        ("threats", "list", "Threats", ""), ("conclusion", "text", "So what? (what this says to do)", "")]},
    "scenario": {"horizon": "future", "label": "Scenario plan", "blurb": "Lay out options with a guessed chance and payoff each; the page computes the probability-weighted value.",
                 "fields": [("assumptions", "text", "Key assumptions", "What must be true for these numbers to hold?"), ("options", "options", "Scenarios", "")]},
    "premortem": {"horizon": "future", "label": "Pre-mortem", "blurb": "Imagine the plan failed a year from now. Why? Write the reasons now, while you can still prevent them.",
                  "fields": [("goal", "line", "The plan or goal", ""), ("failures", "risks", "Ways it could fail", ""), ("go_no_go", "text", "Decision after reading this", "")]},
    "pivot": {"horizon": "future", "label": "Pivot decision", "blurb": "A decision log for a change of direction: evidence on both sides, then the call and when to re-check.",
              "fields": [("current", "line", "Current direction", ""), ("proposed", "line", "Proposed pivot", ""), ("evidence_for", "list", "Evidence for", ""),
                         ("evidence_against", "list", "Evidence against", ""), ("decision", "enum:undecided,go,no-go,test-first", "Decision", ""),
                         ("review_on", "date", "Re-check on", ""), ("reasoning", "text", "Reasoning", "")]},
    "requirements": {"horizon": "future", "label": "BI project requirements", "blurb": "The requirements document for a BI project: who it is for, what it must do, how well, and who signed off. Fill it in with your stakeholders, then get approval before building (it prevents scope creep).",
                     "fields": [("status", "enum:draft,shared for feedback,signed off", "Status", ""),
                                ("stakeholders", "list", "Stakeholders (internal and external)", "Who you will ask and who decides."),
                                ("goals", "list", "Business goals", "e.g. increase sales, improve efficiency, better decisions."),
                                ("kpis", "list", "KPIs", "e.g. gross and net margin, uptime, customer retention."),
                                ("roadmap", "list", "Roadmap steps", "Plan, platform, data collection, governance."),
                                ("data_sources", "list", "Data sources", "Internal (databases, software) and external (APIs, web, third parties)."),
                                ("functional", "list", "Functional requirements", "What it does: integration, ETL, modeling, visuals, governance, collaboration, mobile, self-service."),
                                ("nonfunctional", "list", "Non-functional requirements", "How well: scalability, performance, security, privacy, availability, backup, support."),
                                ("governance", "text", "Data governance, cleansing and validation rules", ""),
                                ("etl", "text", "ETL methods and tools, and the data model", "How data moves from old systems; the entities and relationships."),
                                ("reports", "list", "Reports and dashboards needed", "One per task the end user must complete."),
                                ("analytics", "list", "Analytical capabilities", "Descriptive, diagnostic, predictive, prescriptive, statistical."),
                                ("security", "text", "Security: sign-in, permissions, access limits", ""),
                                ("performance", "text", "Performance: users, data volume, growth", ""),
                                ("integrations", "list", "Integrations with existing software", "ERP, CRM, finance."),
                                ("training", "list", "Training needed", "End users, administrators, support."),
                                ("assumptions", "list", "Assumptions", ""), ("risks", "list", "Risks", ""), ("deliverables", "list", "Deliverables", ""),
                                ("budget", "line", "Budget", ""), ("timeline", "line", "Timeline", ""),
                                ("change_process", "text", "How changes to requirements are handled", ""),
                                ("signed_by", "line", "Signed off by", ""), ("signed_on", "date", "Signed off on", "")]},
    "dataplan": {"horizon": "future", "label": "Data plan", "blurb": "Before you collect anything: what problem, what metric, which data, from where, for how long, how much, and how you will keep it trustworthy.",
                 "fields": [("where_now", "line", "Where you are now", "The problem or situation."),
                            ("where_to", "line", "Where you want to be", "The desired outcome."),
                            ("metric", "line", "What will be measured, and how", ""),
                            ("information", "list", "Information you need", "e.g. purchase history, age group, complaints, survey ratings."),
                            ("sources", "list", "Possible sources", "Internal systems, files, social media, third-party providers."),
                            ("timeframe", "enum:one-off period,ongoing,ongoing with real-time refresh", "Timeframe", ""),
                            ("dates", "line", "Start and end (or refresh rhythm)", ""),
                            ("volume", "line", "How much is enough for a credible answer", "A segment (all customers aged 21-30) or a count."),
                            ("methods", "list", "How you will collect it", "Export, import a file, API, manual entry, survey."),
                            ("dependencies", "list", "Dependencies and risks", ""), ("mitigation", "list", "What you will do about them", ""),
                            ("quality_checks", "list", "Quality checks: free of errors, accurate, complete, relevant, accessible", "Each check and when it runs."),
                            ("governance_privacy", "text", "Governance and privacy: confidentiality, licence to use, rules that apply", "Is it personal data? Are you allowed to use it? Where is the audit trail?"),
                            ("review_on", "date", "Review the plan on", "Plans change as you collect.")]},
    "dsproject": {"horizon": "future", "label": "Data science project", "blurb": "One page that follows the 10 stages of the data science methodology, for any business question: from understanding the problem to feedback after launch.",
                  "fields": [("goal", "line", "1. Business understanding: the goal behind the question", "What is the person asking really trying to achieve (cut cost? raise profit? keep customers?)."),
                             ("objectives", "list", "Objectives that support the goal, in priority order", ""),
                             ("sponsor", "line", "Sponsor and stakeholders", "Who sets direction and signs off."),
                             ("approach", "enum:descriptive,diagnostic,predictive,prescriptive,classification", "2. Analytic approach", "Pick from the question being asked."),
                             ("requirements", "list", "3. Data requirements: what data, in what form", ""),
                             ("collection", "list", "4. Data collection: sources and how you will receive it", "Gaps you must fill or buy."),
                             ("gaps", "list", "Data gaps and the plan for each", "Fill it, substitute something close, or defer it until early model results show it matters."),
                             ("understanding", "text", "5. Data understanding: does it represent the problem?", "Counts, ranges, missing values, what the first charts showed."),
                             ("preparation", "text", "6. Data preparation: cleaning and new columns", "Link to your Wrangling log."),
                             ("modeling", "list", "7. Modeling: the models you will compare", "Start simple; keep a baseline."),
                             ("evaluation", "text", "8. Evaluation: does the model answer the business question?", "Holdout results vs baseline; do you need to adjust the data?"),
                             ("deployment", "text", "9. Deployment: how it gets used", "A dashboard, a monthly report, a rule, a scheduled job."),
                             ("feedback", "text", "10. Feedback: what stakeholders and new data told you", "Then iterate."),
                             ("review_on", "date", "Review on", "")]},
    "deployment": {"horizon": "future", "label": "Deployment plan", "blurb": "Getting a model or analysis used: who needs it, how they will use it, a limited rollout first, training, and how you will watch and improve it. Works for any business.",
                   "fields": [("solution", "line", "What is being put to use", "The model, report or dashboard, and the decision it supports."),
                              ("owner", "line", "Solution owner", "Who is accountable that it works."),
                              ("stakeholders", "list", "Stakeholders and what each needs", "Owner, the people using it, marketing or sales, developers, IT or admin."),
                              ("delivery", "enum:report,dashboard,scheduled refresh,spreadsheet,in an app,manual review", "How people will get the answer", "Pick what the users already work in."),
                              ("rollout", "enum:pilot,test environment,all at once", "Rollout", "A limited pilot builds confidence before everyone relies on it."),
                              ("pilot_group", "line", "Who or what is in the pilot", ""),
                              ("data_flow", "text", "How fresh data reaches it", "Where it comes from, how it is prepared, how often it is scored."),
                              ("training", "list", "Training and guidance for users", "How to read the result and what action to take."),
                              ("success_measure", "line", "How you will know it is working", "The business number that should move."),
                              ("monitoring", "list", "What you will track after launch", "Results of the actions taken, drift in the incoming data, errors."),
                              ("feedback", "list", "How feedback gets back to you", "Who reports, how often, and what triggers a model refresh."),
                              ("review_on", "date", "Review on", "")]},
    "feedback": {"horizon": "past", "label": "Feedback review", "blurb": "After a model or analysis has been in use: what it changed, what users said, and what to refine. Feedback is what keeps a solution worth having.",
                 "fields": [("period", "line", "Review period", "e.g. first quarter after launch."),
                            ("measure", "line", "The business measure you watched", ""),
                            ("before", "line", "Before launch", "The number, and how you got it."),
                            ("after", "line", "After launch", "The number, and how you got it."),
                            ("method", "enum:before and after,control group,other", "How impact was compared", "Where a control group isn't possible or fair, compare before and after."),
                            ("verdict", "enum:worked,mixed,did not work,too early", "Verdict", ""),
                            ("user_feedback", "list", "What users and stakeholders said", ""),
                            ("refinements", "list", "Refinements to make", "Data you deferred and now want, variables to redefine, actions to adjust."),
                            ("redeploy_on", "date", "Redeploy the refined version on", "Feedback continues for the life of the solution."),
                            ("owner", "line", "Who owns the review", "")]},
    "wrangle": {"horizon": "past", "label": "Wrangling log", "blurb": "Document how raw data became analysis-ready, so you can repeat it and revisit your choices. Wrangling is iterative: update the log each round.",
                "fields": [("purpose", "line", "What the data is being prepared for", ""),
                           ("raw_sources", "list", "Raw data you started with", "Tables or files and where they came from."),
                           ("discovery", "text", "Discovery: what you learned about the data", "Shape, gaps, odd values, what must change for the use case."),
                           ("structuring", "list", "Structuring: joins, unions, reshaping", ""),
                           ("normalizing", "list", "Normalizing or denormalizing", ""),
                           ("cleaning", "list", "Cleaning: missing, duplicate, wrong, outlier handling", "Say what you removed or filled, and why."),
                           ("enriching", "list", "Enriching: added data or metadata", "e.g. public data, sentiment score, geo or weather."),
                           ("validation", "list", "Validation rules and results", "Checks for consistency, quality and security."),
                           ("published_as", "line", "Published as", "Table or file name for downstream use."),
                           ("metadata", "text", "Metadata about the published dataset", "Meaning of columns, date prepared, caveats."),
                           ("next_round", "text", "What to revisit next round", "")]},
    "architecture": {"horizon": "future", "label": "Data architecture plan", "blurb": "How data flows from its sources to the people and apps that use it: where it is pulled from, where it is stored, how it is organized and protected, and who gets it in what form.",
                     "fields": [("purpose", "line", "What business need does this serve?", ""),
                                ("sources", "list", "Data sources", "Databases, files, apps, event streams, devices, outside providers. Note the format of each."),
                                ("acquire", "text", "How data is pulled in", "Batch or streaming, how often, and what could make it unreliable."),
                                ("repository", "enum:database,warehouse,lake,lakehouse,undecided", "Where it will be stored", "Database for transactions, warehouse for reporting, lake for raw and varied data."),
                                ("organize", "text", "How it is cleaned and organized", "Layers, master data tables, standards and rules you must follow."),
                                ("consumers", "list", "Who uses it, and in what form", "Analysts want raw tables, managers want dashboards, apps want an API."),
                                ("security", "text", "Security, privacy and access", "Who may see what, personal data handling, encryption."),
                                ("availability", "text", "Backup, recovery and growth", "How fast must it come back, how much loss is acceptable, how it scales."),
                                ("risks", "list", "Risks and open questions", ""),
                                ("review_on", "date", "Review on", "")]},
    "warehouse": {"horizon": "future", "label": "Warehouse design", "blurb": "A star-schema design for reporting: the grain of the fact table, its measures, its dimensions, and how it is loaded and checked.",
                  "fields": [("business_process", "line", "Business process being measured", "For example orders, visits, claims, shipments."),
                             ("grain", "line", "Grain: what does one fact row mean?", "One row per order line per day. Decide this first."),
                             ("measures", "list", "Measures (numbers you add up)", "Additive ones can be summed over any dimension; ratios cannot."),
                             ("dimensions", "list", "Dimensions (how people slice it)", "Date, customer, product, location. Each gets a key."),
                             ("keys", "text", "Keys", "A surrogate key per dimension, and how the source ids map to them."),
                             ("load", "enum:full reload,incremental,change capture", "How it is loaded", ""),
                             ("history", "text", "History of changing attributes", "Overwrite, or keep old versions with dates (slowly changing dimension)."),
                             ("checks", "list", "Checks after each load", "Row counts, totals against the source, no orphan keys."),
                             ("refresh", "line", "Refresh schedule", ""),
                             ("review_on", "date", "Review on", "")]},
    "dmplan": {"horizon": "future", "label": "Data management plan", "blurb": "The rules for looking after your data: who owns it, quality standards, master data, retention, access, privacy and backups.",
               "fields": [("owner", "line", "Who is accountable for the data?", ""),
                          ("assets", "text", "Which data this covers", "Tables, files and systems."),
                          ("quality_rules", "list", "Quality rules", "Required fields, valid ranges, no duplicates, how fresh it must be."),
                          ("master_data", "text", "Master data and standards", "The one agreed list of customers, products, locations, and who maintains it."),
                          ("retention", "text", "Retention and disposal", "How long each kind is kept, and how it is removed."),
                          ("access", "text", "Who gets access", "Roles and the least access they need."),
                          ("privacy", "text", "Privacy and compliance", "Personal data, the rules that apply, how they are met."),
                          ("backup", "text", "Backup and restore", "How often, where kept, when a restore was last tested."),
                          ("monitoring", "list", "What is monitored", "Pipeline failures, data freshness, quality scores, growth."),
                          ("review_on", "date", "Review on", "")]},
    "dataops": {"horizon": "future", "label": "DataOps sprint", "blurb": "One sprint of the DataOps method: set the goal, deliver the data with tests and metadata, then record what to improve next time.",
                "fields": [("goal", "line", "Sprint goal: which business question or consumer need?", ""),
                           ("consumers", "list", "Who will use it", "Analysts, managers, applications."),
                           ("phase", "enum:establish,iterate,improve", "Phase you are in", "Establish sets up the organization; iterate delivers one sprint; improve feeds learnings back."),
                           ("data_needed", "list", "Data and sources needed", "Check each is relevant, reliable and traceable."),
                           ("pipeline_changes", "text", "Pipeline and model changes", "What you will build or change, kept in a code repository."),
                           ("tests", "list", "Automated tests and quality checks", "Run on every change, before anything is delivered."),
                           ("metadata", "text", "Metadata, catalog and lineage updates", ""),
                           ("security", "text", "Who may access it", "Permissions for each consumer."),
                           ("deploy", "text", "How it is delivered and monitored", ""),
                           ("metrics", "list", "How you will measure it", "Defects, cycle time, throughput, consumer satisfaction."),
                           ("learnings", "list", "What went well and what to improve", "Feed these into the next sprint."),
                           ("review_on", "date", "Review on", "")]},
    "toolchoice": {"horizon": "future", "label": "IT tool decision", "blurb": "Record why you picked an IT tool: the need, what you compared, what you tried and what it costs, so the next person (or you in a year) can see the reasoning.",
                   "fields": [("category", "enum:rmm,mdm,patch,assets,service_desk,remote_access,backup,network,edr,other", "Kind of tool", "Pick the closest."),
                              ("need", "text", "The problem this solves", "What goes wrong today without it?"),
                              ("requirements", "list", "Must-haves", "Devices and operating systems, number of users, compliance rules, integrations."),
                              ("shortlist", "list", "Tools compared", "Two or three, with the main reason each stayed on the list."),
                              ("trial", "text", "What you tried in a trial", "Install on a few test machines first; note what worked and what did not."),
                              ("cost", "text", "Cost and contract terms", "Price per device or user, minimum term, cancellation, training and support included."),
                              ("risks", "list", "Risks and exit plan", "Lock-in, data export, what happens if the vendor changes terms."),
                              ("decision", "line", "Decision", "The tool you chose, or not now."),
                              ("review_on", "date", "Review on", "")]},
    "virtplan": {"horizon": "future", "label": "Virtualization plan", "blurb": "Write down a virtualization build before you start: workload, hosts, networks, storage, features and how you will verify and recover.",
                 "fields": [("goal", "text", "What this environment is for", "Lab, small office, production? Which workloads?"),
                            ("hosts", "list", "Hosts", "Name, cores, RAM and role for each."),
                            ("networks", "list", "Networks", "Name, VLAN, subnet and purpose for management, vMotion, storage and VM traffic."),
                            ("storage", "text", "Shared storage", "Type (NFS, iSCSI, SAN, vSAN), size and who can reach it."),
                            ("features", "list", "Features to enable", "HA, DRS, vMotion: and the spare capacity you planned."),
                            ("verification", "list", "How you will verify", "Tests: vMotion a VM, fail a host, restore a backup."),
                            ("risks", "list", "Risks and recovery", "Licensing, single points of failure, backup and restore plan."),
                            ("status", "enum:planning,building,testing,live", "Status", "")]},
    "srs": {"horizon": "future", "label": "Software requirements (SRS)", "blurb": "Write the requirements before you build: who needs what and why, each one testable, with the tests that will prove it.",
            "fields": [("purpose", "text", "Purpose and scope", "What the software is for and what is out of scope."),
                       ("users", "list", "Users and stakeholders", "Who uses it, who pays, who approves."),
                       ("functional", "list", "Functional requirements", "As a [who] I want [what] so that [why]."),
                       ("nonfunctional", "list", "Non-functional requirements", "Performance, security, availability: each with a number."),
                       ("constraints", "list", "Constraints and assumptions", "Budget, date, platforms, rules."),
                       ("acceptance", "list", "Acceptance tests", "How the customer will confirm each requirement is met."),
                       ("status", "enum:draft,reviewed,signed off", "Status", "")]},
    "designdoc": {"horizon": "future", "label": "Software design document", "blurb": "Record how the system will be built: architecture, data, interfaces and the trade-offs you chose.",
                  "fields": [("overview", "text", "Overview", "What is being built and the main design idea."),
                             ("architecture", "text", "Architecture", "Tiers or services, and why this pattern."),
                             ("data", "list", "Data design", "Tables or entities and their keys."),
                             ("interfaces", "list", "Interfaces", "APIs, screens, files in and out."),
                             ("diagrams", "list", "Diagrams", "Class, sequence, state and flow diagrams you drew."),
                             ("tradeoffs", "list", "Trade-offs and rejected options", "What you gave up and why."),
                             ("status", "enum:draft,reviewed,approved", "Status", "")]},
    "testplan": {"horizon": "future", "label": "Test plan", "blurb": "Plan testing before the code is finished: levels, types, environments, who does what and when it passes.",
                 "fields": [("scope", "text", "What is and isn't tested", ""),
                            ("levels", "list", "Levels", "Unit, integration, system, acceptance: owner for each."),
                            ("types", "list", "Types", "Functional, regression, performance, security."),
                            ("environments", "list", "Environments and data", "Where each runs and what data it uses."),
                            ("cases", "list", "Key test cases", "Id, requirement covered, expected result."),
                            ("exit", "list", "Exit criteria", "What must be true to release."),
                            ("status", "enum:planning,running,done", "Status", "")]},
    "sop": {"horizon": "future", "label": "Standard operating procedure", "blurb": "Write a routine task as numbered steps so anyone does it the same way: purpose, who, tools, steps, checks and what to do if it fails.",
            "fields": [("purpose", "text", "Purpose", "Why this procedure exists."),
                       ("owner", "line", "Who does it and who approves", ""),
                       ("tools", "list", "Tools and access needed", ""),
                       ("steps", "list", "Steps", "Numbered, one action each."),
                       ("checks", "list", "How to check it worked", ""),
                       ("failure", "list", "If it fails", "Who to tell and how to roll back."),
                       ("review_on", "date", "Review on", "")]},
    "aiuse": {"horizon": "future", "label": "AI use case brief", "blurb": "Before you build with AI, write the problem, why AI fits, the data, how you will judge it and what could go wrong.",
              "fields": [("goal", "text", "Business goal and problem", "The result you want, in a sentence a customer would understand."),
                         ("approach", "enum:rules,classic ML,deep learning,LLM or RAG,RPA,not sure", "Approach", "Use the approach chooser in AI fundamentals."),
                         ("data", "list", "Data you have", "Source, size, labels, how clean."),
                         ("success", "list", "How you will measure it", "A metric and a baseline to beat."),
                         ("risks", "list", "Risks", "Wrong answers, bias, privacy, cost, who is accountable."),
                         ("human", "text", "Where a person stays in the loop", "Who reviews, and when the system hands over."),
                         ("status", "enum:idea,data check,pilot,live", "Status", "")]},
    "modelcard": {"horizon": "future", "label": "Model card", "blurb": "Document a model or AI feature so others know what it is for, how it was tested and where it fails.",
                  "fields": [("purpose", "text", "Intended use", "What it is for, and who uses it."),
                             ("out_of_scope", "list", "Not for", "Uses that are unsafe or untested."),
                             ("model", "line", "Model and version", "Provider, model, date you last checked it."),
                             ("data", "list", "Data it uses", "Training data if known, plus any documents or tables it can see."),
                             ("tests", "list", "How it was tested", "Test set size, metric, baseline, result."),
                             ("limits", "list", "Known failures and bias", "Where it is wrong, and for whom."),
                             ("oversight", "text", "Human oversight", "Who reviews outputs and who can switch it off."),
                             ("status", "enum:draft,reviewed,approved", "Status", "")]},
    "modelrelease": {"horizon": "future", "label": "Model release record", "blurb": "Record why a model version was promoted: the gate result, what it replaced, how to roll back and what to watch.",
                     "fields": [("model", "line", "Model and version", "Name and version number, and the version it replaces."),
                                ("gate", "list", "Gate and comparison results", "Checks passed, score against the champion or baseline."),
                                ("rollout", "enum:direct,shadow,canary,ab_test", "Rollout", ""),
                                ("rollback", "text", "Rollback plan", "Which version to go back to, who decides, how long it takes."),
                                ("watch", "list", "What we will watch", "Drift, error rate, latency, real outcomes, and how often."),
                                ("retrain", "text", "Retrain trigger", "Schedule or signal, and who is told."),
                                ("status", "enum:draft,approved,live,rolled_back", "Status", "")]},
    "changereq": {"horizon": "future", "label": "Change request", "blurb": "Ask for a change the way an IT team does: what, why, how risky, how to undo it, and who approves.",
                  "fields": [("purpose", "text", "Purpose of the change", "What problem it fixes or what it improves."),
                             ("scope", "text", "Scope and affected systems", "What changes, what could be affected, who is impacted."),
                             ("ctype", "enum:standard,normal,emergency", "Change type", ""),
                             ("risk", "enum:low,medium,high", "Risk level", ""),
                             ("window", "line", "Date, time and window", "Outside any change freeze."),
                             ("rollback", "text", "Rollback and backup plan", "How to undo it and what is backed up."),
                             ("testing", "list", "How it was tested", "Sandbox or spare machine; result."),
                             ("approvals", "list", "Approvals and acceptance", "Who approved, who tested, who accepted."),
                             ("status", "enum:draft,approved,done,rolled_back", "Status", "")]},
    "vendorreview": {"horizon": "future", "label": "Vendor review", "blurb": "Judge a vendor across the three phases of the relationship: before you sign, while they deliver, and after the contract ends.",
                     "fields": [("vendor", "line", "Vendor and what they supply", "Name and the product or service."),
                                ("history", "text", "Record and references", "Business history, security record, references you actually called."),
                                ("terms", "list", "Contract terms checked", "Price, term, SLA, data ownership, exit and data return."),
                                ("comms", "text", "Communication plan", "Who talks to whom, how often, how problems are escalated."),
                                ("risks", "list", "Risks and fallback", "Lock-in, single point of failure, what you do if they fail."),
                                ("phase", "enum:pre_contract,delivery,post_contract", "Phase", ""),
                                ("decision", "enum:undecided,sign,renew,replace,exit", "Decision", "")]},
    "datacard": {"horizon": "future", "label": "Data card", "blurb": "Describe a dataset used for analysis or AI: where it came from, what it contains, what it must not be used for.",
                 "fields": [("source", "text", "Source and owner", "Where it came from, who is accountable."),
                            ("contents", "list", "What it contains", "Tables or files, rows, key fields, time range."),
                            ("collection", "text", "How it was collected", "Method, consent, gaps and known bias."),
                            ("sensitive", "list", "Sensitive fields", "Personal or confidential data and how it is protected."),
                            ("quality", "list", "Known quality problems", "Missing values, duplicates, drift."),
                            ("allowed", "list", "Allowed and forbidden uses", ""),
                            ("refresh", "line", "Update and retention", "How often it changes and when it is deleted.")]},
    "aiincident": {"horizon": "past", "label": "AI incident review", "blurb": "Review a case where an AI feature gave a wrong, harmful or costly result: what happened, why, and what changes so it does not repeat.",
                   "fields": [("what", "text", "What happened", "Input, output and the effect."),
                              ("detected", "line", "How it was found", "User report, monitoring, review."),
                              ("impact", "text", "Who or what was affected", ""),
                              ("cause", "list", "Causes", "Prompt, data, retrieval, tool permission, missing check, model change."),
                              ("fixes", "list", "Fixes and tests added", "Add the case to the regression tests."),
                              ("prevent", "list", "What prevents a repeat", "Guardrail, approval step, monitoring."),
                              ("status", "enum:open,fixed,monitoring", "Status", "")]},
    "story": {"horizon": "future", "label": "Data story", "blurb": "Turn an analysis into a story people act on: who it is for, the one thing they should remember, the evidence, and what to do next.",
              "fields": [("audience", "line", "Who is it for, and what do they care about?", ""),
                         ("decision", "line", "The decision this should help with", ""),
                         ("headline", "line", "The one-sentence takeaway", "If they remember only this."),
                         ("context", "text", "Beginning: where things stood", "The situation and the normal."),
                         ("tension", "text", "Middle: what changed or went wrong", "The problem or surprise the data shows."),
                         ("evidence", "list", "Evidence: the numbers that prove it", "Each with where it came from, e.g. 'West margin fell 4 points (Trends, Oct)'."),
                         ("visuals", "list", "Charts to show", "One chart per point, and what each should make them see."),
                         ("resolution", "text", "End: what to do", "Your recommendation."),
                         ("ask", "line", "The specific ask", "Who does what by when."),
                         ("caveats", "list", "What the data can't tell you", "Limits, assumptions, things you are unsure of."),
                         ("review_on", "date", "Check back on", "")]},
    "report": {"horizon": "past", "label": "Findings report", "blurb": "The outline of a data findings report: write each section, then use it as the script for a paper report or slides.",
               "fields": [("format", "enum:brief (5 pages or fewer),detailed,slides", "Format and length", ""),
                          ("audience", "line", "Audience", "Shape the depth and words for them."),
                          ("author", "line", "Prepared by", ""), ("report_date", "date", "Report date", ""),
                          ("executive_summary", "text", "Executive summary (about three paragraphs)", "Stands alone and brings in nothing that isn't in the report."),
                          ("introduction", "text", "Introduction: the problem and the questions", "Set the context for someone new to the topic."),
                          ("methodology", "text", "Methodology: data sources and plan", "Where the data came from, new collection, variables and methods."),
                          ("results", "list", "Results: the charts and numbers, one point each", "Each with the chart that proves it."),
                          ("discussion", "text", "Discussion: the argument built on the results", "Use narrative to give the numbers meaning; refer back to the questions."),
                          ("conclusion", "text", "Conclusion: problem, summary, outcome, next steps", ""),
                          ("appendix", "list", "Appendix: references and original data", ""),
                          ("check_readable", "enum:not checked,checked,needs work", "Charts large and clearly labelled? (checked from the back of the room)", ""),
                          ("check_evidence", "enum:not checked,checked,needs work", "Key messages first, data only as evidence?", ""),
                          ("check_one_point", "enum:not checked,checked,needs work", "One point per chart?", ""),
                          ("check_relevant", "enum:not checked,checked,needs work", "Everything that doesn't support the message removed?", "")]},
}


def schema() -> list[dict]:
    return [{"kind": k, "horizon": v["horizon"], "label": v["label"], "blurb": v["blurb"],
             "fields": [{"name": n, "type": t.split(":")[0], "choices": t.split(":")[1].split(",") if ":" in t else None, "label": lab, "hint": h} for n, t, lab, h in v["fields"]]}
            for k, v in KINDS.items()]


def _key() -> str:
    from app.services import workspaces
    return f"qual:{workspaces.active()}"


def _load() -> list[dict]:
    try:
        v = json.loads(state.kv_get(_key(), "[]") or "[]")
        return v if isinstance(v, list) else []
    except ValueError:
        return []


def _save(items: list[dict]) -> None:
    state.kv_set(_key(), json.dumps(items))


def _clean_text(v, limit=MAX_TEXT) -> str:
    return str(v or "").strip()[:limit]


def _clean_data(kind: str, data: dict) -> dict:
    out: dict = {}
    for name, typ, label, _ in KINDS[kind]["fields"]:
        v = (data or {}).get(name)
        base = typ.split(":")[0]
        if base in ("text", "line"):
            out[name] = _clean_text(v, MAX_TEXT if base == "text" else 200)
        elif base == "date":
            s = _clean_text(v, 10)
            if s:
                try:
                    date.fromisoformat(s)
                except ValueError as e:
                    raise DataError(f"'{label}' must be a date (YYYY-MM-DD).") from e
            out[name] = s
        elif base == "enum":
            choices = typ.split(":")[1].split(",")
            s = _clean_text(v, 20) or choices[0]
            if s not in choices:
                raise DataError(f"'{label}' must be one of {', '.join(choices)}.")
            out[name] = s
        elif base == "list":
            items = v if isinstance(v, list) else []
            out[name] = [_clean_text(x, 300) for x in items if _clean_text(x, 300)][:MAX_LIST]
        elif base == "options":
            opts = []
            for o in (v if isinstance(v, list) else [])[:MAX_LIST]:
                nm = _clean_text((o or {}).get("name"), 100)
                if not nm:
                    continue
                try:
                    pr, pay = float((o or {}).get("probability", 0)), float((o or {}).get("payoff", 0))
                except (TypeError, ValueError) as e:
                    raise DataError("Probability and payoff must be numbers.") from e
                if not (math.isfinite(pr) and math.isfinite(pay)) or not 0 <= pr <= 100:
                    raise DataError("Probability must be between 0 and 100.")
                opts.append({"name": nm, "probability": pr, "payoff": pay, "note": _clean_text((o or {}).get("note"), 300)})
            out[name] = opts
        elif base == "risks":
            rs = []
            for o in (v if isinstance(v, list) else [])[:MAX_LIST]:
                reason = _clean_text((o or {}).get("reason"), 300)
                if not reason:
                    continue
                lk = _clean_text((o or {}).get("likelihood"), 10) or "medium"
                im = _clean_text((o or {}).get("impact"), 10) or "medium"
                if lk not in ("low", "medium", "high") or im not in ("low", "medium", "high"):
                    raise DataError("Likelihood and impact must be low, medium or high.")
                rs.append({"reason": reason, "likelihood": lk, "impact": im, "mitigation": _clean_text((o or {}).get("mitigation"), 300)})
            out[name] = rs
    return out


def _decorate(it: dict) -> dict:
    """Add computed values (never stored) so the page and tests see one source of truth."""
    it = dict(it)
    d = it.get("data", {})
    if it["kind"] == "scenario":
        opts = d.get("options", [])
        tot = sum(o["probability"] for o in opts)
        ev = sum(o["probability"] / 100 * o["payoff"] for o in opts)
        it["computed"] = {"probability_total": round(tot, 2), "expected_value": round(ev, 2),
                          "balanced": abs(tot - 100) < 0.5 if opts else False,
                          "best": max(opts, key=lambda o: o["payoff"])["name"] if opts else None,
                          "worst": min(opts, key=lambda o: o["payoff"])["name"] if opts else None,
                          "spread": round(max(o["payoff"] for o in opts) - min(o["payoff"] for o in opts), 2) if opts else None,
                          "warning": None if not opts or abs(tot - 100) < 0.5 else f"Probabilities add to {tot:g}%, not 100%. The expected value is only meaningful when they do."}
    elif it["kind"] == "premortem":
        score = {"low": 1, "medium": 2, "high": 3}
        rs = sorted(d.get("failures", []), key=lambda r: -score[r["likelihood"]] * score[r["impact"]])
        it["computed"] = {"ranked": [{**r, "score": score[r["likelihood"]] * score[r["impact"]]} for r in rs],
                          "unmitigated_high": sum(1 for r in rs if score[r["likelihood"]] * score[r["impact"]] >= 6 and not r["mitigation"])}
    elif it["kind"] == "swot":
        it["computed"] = {"counts": {k: len(d.get(k, [])) for k in ("strengths", "weaknesses", "opportunities", "threats")}}
    return it


def list_items() -> dict:
    items = sorted(_load(), key=lambda i: i.get("created", ""), reverse=True)
    return {"schema": schema(), "items": [_decorate(i) for i in items]}


def create(kind: str, title: str, data: dict, tags: list[str] | None = None) -> dict:
    if kind not in KINDS:
        raise DataError("Unknown kind of note.")
    title = _clean_text(title, 140)
    if not title:
        raise DataError("Give it a title.")
    items = _load()
    if len(items) >= MAX_ITEMS:
        raise DataError(f"You have {MAX_ITEMS} notes already; delete some first.")
    it = {"id": uuid.uuid4().hex[:10], "kind": kind, "horizon": KINDS[kind]["horizon"], "title": title, "data": _clean_data(kind, data),
          "tags": [_clean_text(t, 30) for t in (tags or []) if _clean_text(t, 30)][:8], "created": state.now(), "updated": state.now()}
    items.append(it)
    _save(items)
    state.audit("qual.create", f"{kind}: {title}")
    return _decorate(it)


def update(item_id: str, title: str | None, data: dict | None, tags: list[str] | None) -> dict:
    items = _load()
    it = next((i for i in items if i["id"] == item_id), None)
    if not it:
        raise DataError("That note no longer exists.", 404)
    if title is not None:
        t = _clean_text(title, 140)
        if not t:
            raise DataError("Give it a title.")
        it["title"] = t
    if data is not None:
        it["data"] = _clean_data(it["kind"], data)
    if tags is not None:
        it["tags"] = [_clean_text(t, 30) for t in tags if _clean_text(t, 30)][:8]
    it["updated"] = state.now()
    _save(items)
    return _decorate(it)


def delete(item_id: str) -> dict:
    items = _load()
    keep = [i for i in items if i["id"] != item_id]
    if len(keep) == len(items):
        raise DataError("That note no longer exists.", 404)
    _save(keep)
    state.audit("qual.delete", item_id)
    return {"deleted": item_id}


# ------------------------------------------------------------------ theme finder
STOP = set("""a about above after again all also am an and any are as at be because been before being below between both but by can could did do does doing down during each few for from further had has have having he her here hers him his how i if in into is it its itself just me more most my myself no nor not now of off on once only or other our ours out over own same she should so some such than that the their theirs them then there these they this those through to too under until up very was we were what when where which while who whom why will with would you your yours yourself im ive id dont didnt doesnt cant cannot wont isnt wasnt arent get got one two also still even really much many may might must let lets us per via""".split())
POS = set("""good great excellent love loved loving happy helpful fast quick easy saved saves thanks thank amazing awesome best better smooth reliable perfect pleased nice friendly wonderful fantastic improved improve works working solved resolved clear simple useful faster glad enjoy enjoyed recommend impressed super quick""".split())
NEG = set("""bad slow broken broke error errors fail failed failing failure frustrated frustrating angry problem problems issue issues terrible awful worst late delay delayed delays missing lost never refund cancel cancelled complaint complain charged twice wrong poor difficult hard confusing crash crashed down offline disconnect disconnecting disconnects flickers loud shuts risk phishing suspicious unhappy disappointed useless stuck outage overcharged overcharge expensive""".split())
NEGATORS = {"not", "no", "never", "cant", "cannot", "dont", "doesnt", "didnt", "wont", "isnt", "wasnt", "arent", "hardly"}
TOKEN = re.compile(r"[a-z][a-z'\-]{1,}")


def _tokens(text: str) -> list[str]:
    return [t.strip("'-").replace("'", "") for t in TOKEN.findall(text.lower())]


def _split_docs(text: str) -> list[str]:
    parts = re.split(r"\n\s*(?:-{3,}|={3,})\s*\n|\n\s*\n", text.strip())
    return [p.strip() for p in parts if len(p.strip()) >= 3]


def themes(text: str | None = None, source: str | None = None, text_col: str | None = None, include_notes: bool = False, top: int = 15) -> dict:
    docs: list[str] = []
    origin = []
    if text and text.strip():
        if len(text) > MAX_TEXT_IN:
            raise DataError(f"Paste at most {MAX_TEXT_IN:,} characters at a time.")
        docs += _split_docs(text)
        origin.append("pasted text")
    if source and text_col:
        ident, cols = stats_lab.resolve(source)
        stats_lab._need(cols, text_col, ("text",), "text column")
        with get_cursor() as cur:
            rows = fetch_all(cur, f"SELECT CAST({q(text_col)} AS VARCHAR) AS t FROM {q(ident)} WHERE {q(text_col)} IS NOT NULL LIMIT {MAX_DOCS}")
        docs += [r["t"].strip() for r in rows if r["t"] and r["t"].strip()]
        origin.append(f"column {text_col}")
    if include_notes:
        for it in _load():
            blob = " ".join(str(v) if not isinstance(v, list) else " ".join(x if isinstance(x, str) else " ".join(str(y) for y in x.values()) for x in v) for v in it["data"].values())
            if blob.strip():
                docs.append(f"{it['title']}. {blob}")
        origin.append("your saved notes")
    if not docs:
        raise DataError("Paste some text, pick a text column, or include your notes.")
    docs = docs[:MAX_DOCS]
    tdocs = [[t for t in _tokens(d) if t not in STOP and len(t) > 2] for d in docs]
    tf, df, bi = Counter(), Counter(), Counter()
    for toks in tdocs:
        tf.update(toks)
        df.update(set(toks))
        bi.update(set(zip(toks, toks[1:])))
    n = len(docs)
    terms = [{"term": t, "count": c, "docs": df[t], "doc_pct": round(df[t] / n * 100, 1)} for t, c in tf.most_common(top)]
    pairs = [{"phrase": f"{a} {b}", "docs": c} for (a, b), c in bi.most_common(top * 2) if c >= 2][:top]
    # sentiment: word lists with simple negation handling
    labelled, pos_w, neg_w = [], Counter(), Counter()
    for d, raw in zip(docs, (_tokens(x) for x in docs)):
        p = ng = 0
        for i, t in enumerate(raw):
            neg_before = any(x in NEGATORS for x in raw[max(0, i - 2):i])
            if t in POS:
                if neg_before:
                    ng += 1; neg_w[f"not {t}"] += 1
                else:
                    p += 1; pos_w[t] += 1
            elif t in NEG:
                if neg_before:
                    p += 1; pos_w[f"not {t}"] += 1
                else:
                    ng += 1; neg_w[t] += 1
        score = p - ng
        labelled.append({"snippet": re.sub(r"\s+", " ", d)[:160], "positive": p, "negative": ng, "label": "positive" if score > 0 else "negative" if score < 0 else "neutral"})
    counts = Counter(x["label"] for x in labelled)
    # examples for each of the top terms
    examples = {}
    for t in [x["term"] for x in terms[:8]]:
        for d, toks in zip(docs, tdocs):
            if t in toks:
                examples[t] = re.sub(r"\s+", " ", d)[:200]
                break
    sentences = [f"{n:,} piece(s) of text from {', '.join(origin)}. Most common topics: {', '.join(x['term'] for x in terms[:5])}."]
    if counts.get("negative", 0) + counts.get("positive", 0):
        sentences.append(f"By a simple word list, {counts.get('positive', 0)} lean positive, {counts.get('negative', 0)} lean negative, {counts.get('neutral', 0)} neutral.")
    return {"documents": n, "origin": origin, "terms": terms, "phrases": pairs, "sentiment": {"counts": {k: counts.get(k, 0) for k in ("positive", "neutral", "negative")},
            "top_positive": pos_w.most_common(6), "top_negative": neg_w.most_common(6), "items": labelled[:30]}, "examples": examples, "sentences": sentences,
            "lesson": ("Theme finding turns free text into counts: which words and phrases come up in how many pieces of text. It is a starting point for reading, not a replacement: "
                       "a word-list sentiment score misses sarcasm and context, so always read the examples.")}
