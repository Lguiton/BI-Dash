"""Step-by-step how-to manuals, one per discipline.

Each manual is an ordered playbook: what to do, how, which tool to open, how you know you're done, and the mistakes
beginners make. The text is guidance written for this app's real features. Ticking a step is your own record; the app
doesn't verify it (the Company page is where progress is detected from data).

`tab` names the tab inside the discipline's dashboard that a step opens. VALID_TABS lists the real ones, and a test
fails if a manual points at a tab or page that doesn't exist.
"""
from __future__ import annotations

import json

from app.services import state

VALID_TABS = {
    "pm": {"board", "prio", "sprint", "flow", "schedule", "evm", "risk", "okr", "product", "time", "calendar", "rules"},
    "sysanalyst": {"req", "dict", "process", "calc", "feas"},
    "fullstack": {"api", "scaffold", "code", "stack"},
    "security": {"audit", "logs", "web", "ports", "crypto", "incident"},
    "network": {"subnet", "config", "capture", "diag", "calc", "ref"},
    "itsupport": {"tickets", "assets", "events", "checklists", "capacity", "cheats"},
    "engineering": {"pipeline", "dba", "gov", "gov/catalog", "gov/pii", "gov/lineage", "gov/controls", "gov/access"},
}


def S(sid, title, what, how, tool=None, done="", mistakes=(), ask=""):
    """tool = (label, href, tab|None). href is a top-level page or None (stay on this dashboard)."""
    t = None
    if tool:
        t = {"label": tool[0], "href": tool[1], "tab": tool[2] if len(tool) > 2 else None}
    return {"id": sid, "title": title, "what": what, "how": list(how), "tool": t, "done_when": done, "mistakes": list(mistakes), "ask": ask}


MANUALS: dict[str, dict] = {}

MANUALS["analyst"] = {
    "title": "Data Analyst: from a business question to a report people act on",
    "intro": "An analyst turns a vague worry ('are we making money?') into numbers, checks the numbers can be trusted, and tells a short story that ends in a decision.",
    "outcome": "A one-page report with 3 to 5 KPIs, one clear finding with its evidence, and a recommended action.",
    "steps": [
        S("question", "Frame the question", "Write the decision the numbers will support before you open any data.",
          ["Write: 'We need to decide ___, so we need to know ___.'", "List 3 candidate measures (e.g. net margin, cost vs budget, completion rate).", "Write what result would change your mind."],
          ("Open the dashboard", "/", None), "You can say the decision and the 3 measures in two sentences.",
          ["Starting with charts and hunting for a story.", "Measuring everything instead of what the decision needs."], "Help me turn a vague business worry into a decision and 3 measures."),
        S("quality", "Check the data can be trusted", "Bad data produces confident wrong answers, so test it before you analyse it.",
          ["Open Data quality and read every failing check, not only the score.", "For each failure decide: fix at the source, exclude, or note as a caveat.", "Write down the caveats; they go in the report."],
          ("Data quality", "/quality", None), "Every failing check has a decision next to it.",
          ["Ignoring a 'small' failure that affects the KPI you care about.", "Fixing data silently so nobody knows the rule you used."], "Look at my data quality results and tell me which failures matter for my KPIs."),
        S("shape", "Learn the shape of the data", "Know what one row means (the grain) and which columns are measures versus labels.",
          ["Open the Star schema page: find the fact table and the dimension tables.", "Say the grain in a sentence: 'one row per ___ per ___'.", "Mark which measures are additive (revenue) and which are not (margin, averages)."],
          ("Star schema", "/schema", None), "You can state the grain and name one non-additive measure.",
          ["Adding percentages together.", "Joining before knowing whether the key is unique."], "Explain the grain of my fact table and which measures are additive."),
        S("kpis", "Define the KPIs", "A KPI is a metric tied to a goal: a target, a direction and a warning band.",
          ["Open the KPI builder and pick a metric.", "Set direction (higher or lower is better), target, warning % and window.", "Create 3 to 5. Fewer is better than more."],
          ("KPI builder", "/kpis", None), "3+ KPIs exist with targets you can defend.",
          ["Targets chosen so everything shows green.", "Mixing a total and a ratio in one KPI."], "Suggest 3 KPIs with sensible targets for my data."),
        S("sql", "Investigate with SQL", "Answer the follow-up questions the KPIs raise.",
          ["Open SQL Lab. Start with SELECT ... GROUP BY on one dimension.", "For ratios, compute SUM(a)/SUM(b), never AVG of a ratio column.", "Save queries you will reuse."],
          ("SQL Lab", "/lab", None), "You have 2 queries that explain why a KPI is off target.",
          ["AVG of a margin column.", "Forgetting to filter to the period you report on."], "Write a SQL query to find which entities drive cost over budget."),
        S("visual", "Choose the right chart", "Pick the chart that answers the question, not the one that looks impressive.",
          ["Trend over time: line. Compare categories: bar. Two measures: scatter. Pattern across two categories: heatmap.", "Use the Chart gallery on the main dashboard to try them.", "Remove anything that does not help the reader."],
          ("Chart gallery", "/", None), "Each chart answers one stated question.",
          ["Pie charts with many slices.", "Truncated axes that exaggerate a change."], "Which chart type fits my question about change over time by entity?"),
        S("story", "Find the finding", "A finding is a claim plus evidence plus 'so what'.",
          ["Compare to a baseline: budget, last period, or a peer.", "Find the biggest driver: which entity or day explains most of the gap?", "Write: 'X is Y% over budget, driven by Z, costing $N. Recommend ___.'"],
          ("Insights", "/", None), "Your finding fits in two sentences with a number and a recommendation.",
          ["Reporting a difference without checking it is not noise (see Data Scientist).", "Burying the finding on page 3."], "Draft a two-sentence finding from my current numbers."),
        S("deliver", "Deliver the report", "The numbers only matter once someone reads them.",
          ["Use the report buttons on the main dashboard for PDF or Excel.", "Put the finding first, then evidence, then caveats from step 2.", "Say what you want the reader to do."],
          ("Report buttons", "/", None), "A person who was not in the room could act on it.",
          ["Sending a data dump.", "Hiding caveats."], "Draft the opening paragraph of my leadership report."),
        S("monitor", "Monitor and repeat", "A report is a snapshot; a KPI is a habit.",
          ["Re-check the KPI page on a schedule.", "When a KPI turns red, go back to step 5 and ask why.", "Revisit targets quarterly."],
          ("KPI builder", "/kpis", None), "You have a date for the next review.",
          ["Never re-checking targets.", "Treating every wobble as a crisis."], "Help me set a monitoring routine for my KPIs."),
    ],
}

MANUALS["scientist"] = {
    "title": "Data Scientist: is the pattern real, and how big is it?",
    "intro": "A scientist separates real effects from luck. The work is hypotheses, careful tests, honest effect sizes, and saying 'we can't tell yet' when that is true.",
    "outcome": "A short write-up: question, test, result with effect size and uncertainty, limits, and a recommendation.",
    "steps": [
        S("hypothesis", "Write a testable hypothesis", "A claim you can be wrong about.",
          ["State the null (no difference) and the alternative.", "Choose the outcome measure and the groups before looking.", "Write the smallest difference that would matter to the business."],
          ("Open the workbench", None, None), "H0, H1, the measure and the 'matters' threshold are written down.",
          ["Choosing the question after seeing the result.", "No minimum meaningful effect."], "Help me write a null and alternative hypothesis for weekend versus weekday revenue."),
        S("suitable", "Check the data is suitable", "A test needs enough observations in each group.",
          ["Look at the readiness strip on this page: weekend and weekday day counts.", "Check data quality on the Data quality page.", "If a group has under ~5 days, collect more data instead of testing."],
          ("Data quality", "/quality", None), "Both groups have enough days and the quality checks pass.",
          ["Testing 2 days against 20.", "Ignoring duplicates."], "Is my data big enough for a weekend versus weekday test?"),
        S("describe", "Describe before you test", "Look at the distributions and relationships first.",
          ["Read the correlations and segments panels on the workbench.", "Open notebook 11 for hands-on examples.", "Look for outliers that could drive the result."],
          ("Notebooks", "/python", None), "You can describe each group's centre and spread in a sentence.",
          ["Jumping to a test with an outlier unexamined.", "Reading correlation as cause."], "Explain the correlations panel in plain words."),
        S("test", "Run the test and read it properly", "The Welch t-test compares two group means without assuming equal spread.",
          ["Read the weekend test panel: both means, the difference, the p-value, and the confidence interval.", "A small p-value says 'unlikely to be luck', not 'important'.", "Compare the effect size to your 'matters' threshold from step 1."],
          ("Open the workbench", None, None), "You can state the difference in dollars and its interval.",
          ["Treating p < 0.05 as proof.", "Reporting only the p-value."], "Interpret my weekend test result: is it real and does it matter?"),
        S("segments", "Segment and cluster", "Different groups may behave differently.",
          ["Read the entity segments panel.", "Open notebook 12 to cluster entities yourself.", "Name each cluster in business terms."],
          ("Notebooks", "/python", None), "Each segment has a name and one action.",
          ["Too many clusters to explain.", "Clusters that only restate size."], "Describe the segments in my data and what to do about each."),
        S("causation", "Challenge your own conclusion", "Look for what else could explain the result.",
          ["List confounders (e.g. weekends have different entities).", "Check the effect holds within segments.", "Say what an experiment would need to prove cause."],
          None, "You listed at least two alternative explanations.",
          ["Claiming cause from observational data.", "Not saying what you didn't test."], "What confounders could explain my weekend result?"),
        S("writeup", "Write it up", "Make it usable by someone who skips the maths.",
          ["Lead with the answer in business terms.", "Give the effect size with its interval.", "State limits and a next step."],
          None, "A non-technical reader could repeat your conclusion correctly.",
          ["Jargon without a plain sentence beside it."], "Draft the conclusion paragraph of my analysis."),
    ],
}

MANUALS["ml"] = {
    "title": "Machine Learning: a model is only good if it beats a simple guess",
    "intro": "ML work is mostly careful evaluation. You build a baseline, split data honestly, compare models, and record every experiment so results are reproducible.",
    "outcome": "A logged experiment showing a model versus its baseline on held-out data, with a clear ship / don't-ship decision.",
    "steps": [
        S("target", "Define the target and the metric", "What exactly will the model predict, and how will you score it?",
          ["Pick the target (e.g. daily revenue or cost).", "Pick an error metric the business understands (MAE in dollars).", "Decide what 'good enough' means."],
          ("ML Lab", "/ml", None), "Target, metric and the pass mark are written down.",
          ["Optimising a metric nobody cares about."], "Help me choose a target and metric for my data."),
        S("ready", "Check you have enough data", "Time-series models need history.", ["See the readiness strip: 100+ records and 20+ distinct days.", "If short, import more data on My data first."],
          ("My data", "/data", None), "Readiness shows green.", ["Training on a handful of rows."], "Is my dataset big enough to train a model?"),
        S("baseline", "Build the baseline first", "The simplest possible guess (e.g. the average) is the bar to beat.",
          ["Open the ML Lab: every run reports a baseline score next to the model score.", "If the model barely beats the baseline, it isn't worth the complexity."],
          ("ML Lab", "/ml", None), "You know the baseline score.", ["Skipping the baseline.", "Comparing a model to nothing."], "Why does a baseline matter and what is mine?"),
        S("split", "Split by time, not randomly", "Training on the future and testing on the past is leakage.",
          ["The lab splits chronologically: earlier days train, later days test.", "Never let the test set influence choices."],
          ("ML Lab", "/ml", None), "You can explain why the split is by time.", ["Random splits on time series.", "Tuning on the test set."], "Explain data leakage using my dataset."),
        S("features", "Choose features", "Inputs the model can use at prediction time.",
          ["Pick the features offered in the ML Lab.", "Ask: would I know this value when I need the prediction?", "Start small."],
          ("ML Lab", "/ml", None), "Every feature is available at prediction time.", ["Using the target (or a copy) as a feature."], "Which features are safe to use and which leak?"),
        S("train", "Train and compare", "Run more than one model.", ["Train each model in the ML Lab.", "Compare test score versus baseline and train versus test.", "A big gap between train and test means overfitting."],
          ("ML Lab", "/ml", None), "At least 2 models compared on the same split.", ["Picking by train score."], "Compare my model runs and say which to prefer."),
        S("log", "Log and review experiments", "If it isn't recorded, it didn't happen.", ["Every run is stored in the experiment log.", "Note what you changed between runs."],
          ("ML Lab", "/ml", None), "The log shows what you tried and why.", ["Changing three things at once."], "Summarise my experiment log."),
        S("decide", "Decide: ship or not", "A decision with reasons.", ["Does it beat the baseline by more than noise?", "What happens when it's wrong?", "How will you notice drift?", "Note: models in this lab are for learning; they aren't deployed anywhere."],
          None, "You wrote ship / don't ship and the reason.", ["Shipping without a monitoring plan."], "Help me write the ship or don't-ship decision."),
    ],
}

MANUALS["engineering"] = {
    "title": "Data Engineering, Database Admin and Data Governance",
    "intro": "Three jobs in one track: move data reliably (pipelines), keep the database healthy and recoverable (DBA), and make sure data has an owner and is handled safely (governance).",
    "outcome": "A pipeline that runs repeatably, a verified backup, every table owned and classified, and personal data protected.",
    "steps": [
        S("layers", "Understand bronze, silver and gold", "Raw data lands untouched (bronze), is cleaned (silver) and then shaped for reporting (gold).",
          ["Open the Pipeline tab and read the layer cards.", "Bad rows go to quarantine, not into silver."], ("Pipeline", None, "pipeline"), "You can say what each layer is for.", ["Cleaning data in place so you can't re-run."], "Explain the medallion layers using my pipeline."),
        S("run", "Run the pipeline", "Run it end to end on a chosen source.", ["Choose a source (clean, messy or your uploaded data) and run.", "Read the layer counts."],
          ("Pipeline", None, "pipeline"), "A run completed and the counts make sense.", ["Not reading the counts."], "Walk me through my last pipeline run."),
        S("quarantine", "Read the quarantine and health checks", "Rejected rows tell you what is wrong upstream.", ["Open the quarantine reasons.", "Decide per reason: fix at source, add a rule, or accept."],
          ("Pipeline", None, "pipeline"), "Every quarantine reason has a decision.", ["Dropping bad rows without recording why."], "Which quarantine reasons should I fix first?"),
        S("idempotent", "Prove it is idempotent", "Running twice must give the same result.", ["Run the pipeline twice in a row.", "The silver counts must not change."],
          ("Pipeline", None, "pipeline"), "Two runs, identical silver counts.", ["Appending duplicates on re-run."], "Why does idempotency matter in a pipeline?"),
        S("import", "Bring in real data", "Import your own CSV and map its columns.", ["Open My data and import.", "Map columns to the expected names.", "Run the data-quality page afterwards."],
          ("My data", "/data", None), "Real data is loaded and quality-checked.", ["Importing into Practice by mistake."], "Help me map my CSV columns."),
        S("dba-baseline", "DBA: take a health baseline", "Know what normal looks like.", ["Open Database admin: size, free blocks, tables, constraints.", "Read every finding and its suggested action."],
          ("Database admin", None, "dba"), "You know your database size and have read the findings.", ["Ignoring a 'no backups' finding."], "Explain my database health findings."),
        S("dba-backup", "DBA: back up and prove the restore", "A backup you have not restored is a hope.", ["Take a backup in Settings & backups.", "Back in Database admin press Verify latest backup.", "Set an automatic backup schedule for Real."],
          ("Settings & backups", "/settings", None), "A backup exists and verification passed.", ["Never testing a restore."], "What is RPO and RTO for my setup?"),
        S("dba-perf", "DBA: benchmark and read plans", "Find slow queries before users do.", ["Run query benchmarks.", "Open Query plans and look for full scans.", "Re-run after importing more data and compare."],
          ("Database admin", None, "dba"), "You know your slowest query and why.", ["Optimising without measuring."], "Which of my benchmark queries is slowest and what would speed it up?"),
        S("dba-maintain", "DBA: checkpoint and watch growth", "Keep the WAL small and size predictable.", ["Run CHECKPOINT.", "Check the growth chart over days."],
          ("Database admin", None, "dba"), "You have a rule for when to checkpoint.", ["Ignoring a growing WAL."], "When should I checkpoint and how do I forecast growth?"),
        S("gov-catalog", "Governance: own and classify every table", "Unowned data is nobody's problem until it breaks.", ["Open Data governance > Catalog.", "Set owner, steward and classification (public / internal / confidential / restricted).", "Add a retention rule where data should expire."],
          ("Catalog", None, "gov/catalog"), "Every table has an owner and a class.", ["Classifying everything 'internal' to finish quickly."], "Suggest an owner and classification for each of my tables."),
        S("gov-pii", "Governance: find and protect personal data", "Find personal columns and keep them away from AI.", ["Run the PII scan.", "Press Protect from AI for each real finding.", "Remember: a clean scan means 'nothing obvious', not 'nothing'."],
          ("PII scan", None, "gov/pii"), "No unprotected personal columns remain.", ["Trusting the scan blindly."], "Explain my PII scan results."),
        S("gov-lineage", "Governance: document lineage", "Where does data come from and who reads it?", ["Open Lineage.", "Check each consumer reads from the right layer."],
          ("Lineage", None, "gov/lineage"), "You can trace one KPI back to its source.", ["Undocumented copies of data."], "Trace my revenue KPI back to its source."),
        S("gov-controls", "Governance: review controls and access", "Evidence that data is handled on purpose.", ["Open Controls and fix gaps in order.", "Open Access to see what left the computer and what failed."],
          ("Controls", None, "gov/controls"), "6+ of 8 controls are in place.", ["Treating this checklist as a compliance certificate: it isn't."], "Which governance control gaps should I fix first?"),
    ],
}

MANUALS["ai"] = {
    "title": "AI Engineering: useful assistants with known limits",
    "intro": "AI engineering is building features around a model: giving it the right tools, checking its answers, controlling cost, and limiting what it may see.",
    "outcome": "An assistant over your data that you've tested, whose answers you can verify, with privacy limits set.",
    "steps": [
        S("setup", "Check providers and keys", "No key, no model.", ["Open the AI Lab status panel.", "Keys live in backend/.env, never in the browser.", "Run scripts/check_ai_keys.py if a provider shows not ready."],
          ("AI Lab", "/ai", None), "At least one provider shows ready.", ["Committing keys to git."], "Which AI provider should I use first and why?"),
        S("privacy", "Set the privacy mode first", "Decide what the model may see before the first question.", ["Open Settings: off, summaries only, or full.", "Add blocked columns for personal data (the Governance PII scan helps).", "Remember: a guardrail, not a vault."],
          ("Settings", "/settings", None), "The Real workspace mode is a deliberate choice.", ["Leaving full access on for real data by habit."], "Which privacy mode fits my Real data?"),
        S("ask", "Ask a data question and read the steps", "Watch how the agent loop works.", ["Ask a simple question in the AI Lab.", "Open the steps: get_schema, run_sql, answer.", "Check the SQL it ran makes sense."],
          ("AI Lab", "/ai", None), "You read the SQL behind one answer.", ["Trusting the sentence without the SQL."], "Show me how an agent answers a data question."),
        S("verify", "Verify answers independently", "Models can be confidently wrong.", ["Re-run the numbers in SQL Lab.", "Ask a question whose answer you know.", "Note any mismatch."],
          ("SQL Lab", "/lab", None), "You caught or confirmed at least one answer.", ["Never checking."], "How do I check an AI answer is right?"),
        S("route", "Understand routing, cost and limits", "Different questions need different models.", ["Read the route shown with each answer.", "Check daily caps and rate limits.", "Use the simple/complex override."],
          ("AI Lab", "/ai", None), "You can explain why one question went to one provider.", ["Using the biggest model for everything."], "Explain model routing and cost control."),
        S("injection", "Test prompt injection", "Data can contain instructions.", ["Run ai_engineering/05_prompt_injection.py.", "See how tool results are treated as data."],
          None, "You can describe one injection attack and the defence.", ["Giving the model a tool that can change data."], "Explain prompt injection with an example."),
        S("build", "Build the pieces yourself", "Learn by rebuilding.", ["Work through ai_engineering exercises 01 to 04: structured output, RAG, evals, MCP server.", "Run the tests in ai_engineering/tests."],
          None, "All four exercises run.", ["Skipping evals."], "What should my first eval for a data agent check?"),
    ],
}

MANUALS["pm"] = {
    "title": "Project & Product Management: decide, plan, deliver, measure",
    "intro": "A PM keeps three things honest: what is worth building (value), when it will be done (schedule), and what it costs (budget), while managing risk and measuring whether the product works.",
    "outcome": "A prioritised backlog, a sprint plan, a schedule with a critical path, budget tracking with earned value, a risk register, and OKRs.",
    "steps": [
        S("okr", "Set the goal as OKRs", "An Objective is the outcome you want; Key Results are the measurable proof.", ["Open OKRs and add an objective with 2 to 4 key results.", "Each KR has a start, a target and a current value.", "KRs measure outcomes, not tasks."],
          ("OKRs", None, "okr"), "Every objective has measurable KRs.", ["KRs written as tasks ('launch X')."], "Draft OKRs for my project."),
        S("backlog", "Build the backlog", "List the work as items: epic, story, task, bug, milestone.", ["Open the Board and add items with a clear title and owner.", "Add points (effort) as a rough size.", "Load the example project in Practice to see a complete one."],
          ("Board", None, "board"), "10+ items exist.", ["Vague titles.", "Epics that never get split."], "Break this goal into backlog items."),
        S("prioritise", "Prioritise by value", "Rank by value per effort, not by who shouts loudest.", ["For each item enter reach, impact, confidence (0 to 1) and effort for RICE.", "Or value, time criticality, risk reduction and points for WSJF.", "Tag Must/Should/Could/Won't; Musts should stay near 60% of points."],
          ("Prioritisation", None, "prio"), "5+ items are scored and ranked.", ["Confidence set to 1 everywhere.", "Everything is a Must."], "Which of my items should I do first and why?"),
        S("schedule", "Plan the schedule and find the critical path", "Dependencies decide the finish date.", ["Give items a start date, duration (days) and dependencies (ids).", "Open Schedule: items with zero float are critical.", "To finish sooner, shorten a critical item, not a slack one."],
          ("Schedule", None, "schedule"), "You can name the critical path.", ["Circular dependencies.", "Ignoring float."], "What is on my critical path and what would shorten it?"),
        S("sprint", "Plan a sprint", "A sprint is a fixed time-box with a goal.", ["Add a sprint (2 weeks is common) with a goal.", "Assign items to it when you add or edit them.", "Do not commit more than your velocity."],
          ("Sprints", None, "sprint"), "A sprint has a goal and assigned items.", ["Committing to 30 points when velocity is 13."], "How much should I commit to this sprint?"),
        S("flow", "Run the work and watch flow", "Move cards across the board and watch cycle time and WIP.", ["Move items from todo to doing to done on the Board.", "Open Flow: cycle time, throughput, cumulative flow, Little's law.", "If WIP is above what Little's law expects, stop starting and start finishing."],
          ("Flow", None, "flow"), "You know your median cycle time and WIP.", ["Too many items in doing."], "Is my work in progress too high?"),
        S("budget", "Track budget with earned value", "Planned value, earned value and actual cost tell you if you are on track.", ["Enter planned and actual cost on items, or log your hours in the Time tab with an hourly rate: logged hours then replace the typed actual cost.", "Open Earned value: CPI under 1 means over budget; SPI under 1 means behind.", "Read EAC for the likely final cost."],
          ("Earned value", None, "evm"), "You can say whether you are over budget and behind.", ["Planned cost missing on most items."], "Explain my CPI and SPI in plain words."),
        S("risk", "Manage risks", "A risk is a possible problem: probability times impact is its expected cost.", ["Open Risks and add each risk with probability (0 to 1) and cost.", "Write a mitigation and an owner.", "Use total exposure as a starting contingency reserve."],
          ("Risks", None, "risk"), "3+ risks with owners and mitigations.", ["Risks with no owner.", "Never revisiting the register."], "What risks am I probably missing?"),
        S("product", "Measure the product", "Is anyone using it, and do they come back?", ["Open Product analytics: stickiness (DAU/MAU), status funnel, retention cohorts.", "Entities stand in for accounts; records for activity."],
          ("Product analytics", None, "product"), "You know retention after month 1.", ["Reading a few rows as a trend."], "What does my retention table say about the product?"),
        S("review", "Review and adjust", "Use the numbers in the retro.", ["Check velocity trend, forecast, and risks.", "Decide one thing to change next sprint."],
          ("Sprints", None, "sprint"), "You wrote one change for next sprint.", ["Retros that change nothing."], "Run a retrospective on my last sprint."),
    ],
}

MANUALS["sysanalyst"] = {
    "title": "Systems Analyst: what the system must do, and proof that it does",
    "intro": "An analyst bridges the business and the builders: gathers requirements, models data and process, sizes the system, checks feasibility, and traces every requirement to a test.",
    "outcome": "A testable requirements list traced to tests, a data dictionary and ER diagram, sizing numbers, a cost-benefit case and a feasibility verdict.",
    "steps": [
        S("problem", "Write the problem statement and list stakeholders", "Everything is judged against the problem.", ["One paragraph: who has what problem, and what it costs.", "List stakeholders and what each cares about; use the Source field on requirements for this."],
          ("Requirements", None, "req"), "A reader could tell if a proposal solves the problem.", ["Writing the solution instead of the problem."], "Help me write a problem statement."),
        S("elicit", "Capture requirements", "Each requirement is one testable statement.", ["Open Requirements and add each as 'The system shall...'.", "Mark type (functional, non-functional, constraint) and priority (MoSCoW).", "Write an acceptance criterion someone could check."],
          ("Requirements", None, "req"), "8+ requirements with acceptance criteria.", ["Vague words: fast, easy, user-friendly.", "Two requirements in one."], "Draft requirements for this system."),
        S("data", "Model the data", "The dictionary says what every field means.", ["Open Data dictionary: tables, columns, keys, null % and distinct counts.", "Check relationships and orphans.", "Copy the Mermaid diagram into mermaid.live."],
          ("Data dictionary", None, "dict"), "Every table has a description and orphans are 0.", ["Undocumented columns."], "Describe each table in my data dictionary."),
        S("process", "Model the process", "Find where time goes.", ["Open Process analysis: duration percentiles, variability, bottleneck.", "High variability (CV above 1) means unpredictable delivery."],
          ("Process analysis", None, "process"), "You can name the bottleneck.", ["Optimising a step that isn't the bottleneck."], "Where is my process bottleneck and why?"),
        S("size", "Size the system", "Queueing, availability and capacity.", ["Queueing: enter arrival and service rates; keep utilisation under about 80%.", "Availability: set an SLO; read error budget; combine components serial or parallel.", "Capacity: enter load, capacity, growth; read months to full."],
          ("Calculators", None, "calc"), "You have a number for staffing, uptime and capacity.", ["Rates in different time units.", "Sizing to 100% utilisation."], "How many servers or staff do I need?"),
        S("cba", "Make the cost-benefit case", "Will it pay back?", ["Enter upfront cost, annual benefit and cost, years, discount rate.", "Read NPV, ROI, IRR, payback.", "Test with a lower benefit."],
          ("Calculators", None, "calc"), "NPV is positive even with pessimistic benefit.", ["Counting benefits twice."], "Stress-test my cost-benefit numbers."),
        S("feasible", "Score feasibility (TELOS)", "Technical, Economic, Legal, Operational, Schedule.", ["Score each 1 to 5 with a note of evidence.", "A single score below 3 caps the verdict."],
          ("Feasibility", None, "feas"), "A verdict and a named weakest area.", ["Scoring without evidence."], "Challenge my feasibility scores."),
        S("trace", "Trace requirements to tests", "Proof the system does what was agreed.", ["Set status as items are built then tested.", "Fill the test reference.", "Read the gaps list until empty."],
          ("Requirements", None, "req"), "80%+ of built requirements have a test.", ["Marking tested without a test."], "Which requirements lack a test?"),
    ],
}

MANUALS["fullstack"] = {
    "title": "Full Stack Developer: one vertical slice, table to screen",
    "intro": "A full stack developer owns a feature through every layer: table, API, UI, tests, release. Build one thin slice completely before building wide.",
    "outcome": "A working resource: table, validated API, typed UI, tests, and a release checklist run.",
    "steps": [
        S("map", "Map the API you have", "Know the contract before changing it.", ["Open API map & tester and browse groups.", "Use a GET on one endpoint and read the JSON.", "Open /docs on the backend for the OpenAPI view."],
          ("API map & tester", None, "api"), "You can describe 3 endpoints without looking.", ["Changing an endpoint nobody mapped."], "Explain how this API is organised."),
        S("design", "Design the resource", "Columns, types, keys.", ["Open the Star schema page for the existing model.", "Decide columns, types and a primary key for the new table.", "Prototype the queries in SQL Lab."],
          ("SQL Lab", "/lab", None), "A table definition you could defend.", ["No primary key."], "Design a table for this feature."),
        S("scaffold", "Scaffold the layers", "Generate a first draft of every layer.", ["Open Scaffold from a table and pick a table.", "Read each generated file.", "Check every value is a ? parameter, never glued into SQL."],
          ("Scaffold", None, "scaffold"), "You read and understood each file.", ["Pasting generated code you haven't read."], "Review this generated router for problems."),
        S("register", "Register and run it", "Wire the router into the app.", ["Paste the router into backend/app/routers.", "Add include_router in app/main.py.", "Restart the backend."],
          None, "The endpoint appears in the API map.", ["Forgetting to restart."], "How do I register a router?"),
        S("try", "Try it and break it", "Test happy and failing paths.", ["Use the tester: GET, POST, PUT, DELETE (Practice only).", "Send a bad body and read the 422.", "Check a missing id returns 404."],
          ("API map & tester", None, "api"), "You saw 2xx, 404 and 422.", ["Only testing the happy path."], "What bad inputs should I try?"),
        S("test", "Write real tests", "Tests protect the next change.", ["Use the generated pytest skeleton.", "Assert the status and the data.", "Run pytest from backend."],
          ("Codebase", None, "code"), "A failing test exists for a broken case, then passes.", ["Assertions that can't fail."], "What should my tests assert?"),
        S("ui", "Build the screen", "Handle loading, empty, error and success.", ["Use the generated React panel as a start.", "Copy its pattern from PmPanel.tsx.", "Add the TypeScript type."],
          None, "The screen shows all four states.", ["No error state."], "Review my React panel for missing states."),
        S("review", "Review code health", "Look for the file doing too many jobs.", ["Open Codebase: largest files and test ratio."], ("Codebase", None, "code"), "You noted the largest file and one split.", ["Ignoring a 1,000-line file."], "How could I split my largest file?"),
        S("release", "Run the release checklist", "Ship on purpose.", ["Open Stack & config; read each fact.", "Tests green, backup taken, .env ignored, CORS has no wildcard."],
          ("Stack & config", None, "stack"), "Every item checked.", ["Releasing with failing tests."], "Walk me through a release checklist."),
    ],
}


MANUALS["security"] = {
    "title": "Cybersecurity: secure what you own, then learn to spot and handle trouble",
    "intro": "Security is risk reduction, not perfection. Fix the cheap, common problems first, watch the logs, and have a plan for the day something goes wrong. Everything here is defensive and runs against your own app or public sites.",
    "outcome": "A clean self-audit, one log investigation written up as an incident, and a short playbook you could follow under stress.",
    "steps": [
        S("audit", "Audit your own setup", "Most breaches start with a leaked key or an open door you forgot about.",
          ["Open the Self-audit tab and run it.", "Fix every red item: .env in .gitignore, no secrets in tracked files, tight CORS.", "Run it again and note the score."],
          ("Self-audit", None, "audit"), "Score is up and no red item is left unexplained.", ["Fixing nothing because 'it is only personal'.", "Committing a key, then deleting it (it stays in history; rotate it)."], "Which self-audit failures matter most for me?"),
        S("logs", "Read the logs for patterns", "Attacks leave repeated, boring traces.",
          ["Open the Logs tab and load the sample.", "Read each detection and the lines behind it.", "Decide for each: attack, noise or a mistake by a real user."],
          ("Log analysis", None, "logs"), "You can explain one detection and the evidence for it.", ["Treating a detection as proof.", "Ignoring a success after many failures from the same address."], "Explain this brute-force detection and what I should check."),
        S("web", "Check what a site shows the world", "Headers and certificates are the cheapest protections.",
          ["Open Web checks and enter a public site you own.", "Read the missing headers and what each one prevents.", "Note the certificate expiry date."],
          ("Web checks", None, "web"), "You have a list of missing headers ranked by importance.", ["Testing sites you don't own."], "Which missing header should I add first?"),
        S("ports", "Know what your machine exposes", "A service you forgot about is an open door.",
          ["Open Ports and run the local check.", "For each open port, name the program and why it is needed.", "Close or firewall the rest."],
          ("Local ports", None, "ports"), "Every open port has a reason.", ["Assuming a database port is only reachable locally."], "What does an open port 5432 mean?"),
        S("crypto", "Understand hashes, passwords and 2FA", "Never store passwords; store salted slow hashes. Add a second factor.",
          ["Hash a word in the Crypto tab and change one letter.", "Test a few passwords for strength and read the assumption behind the crack time.", "Set up the TOTP lab and match the code."],
          ("Crypto labs", None, "crypto"), "You can say why a hash is not encryption.", ["Believing a long common phrase is strong.", "Using SHA-256 alone for passwords."], "Why are fast hashes bad for passwords?"),
        S("incident", "Handle an incident on paper", "In a real incident you won't think clearly; the checklist thinks for you.",
          ["Open Incidents and log one from the sample log.", "Work through the playbook checklist for its category.", "Close it with a note on what you would change."],
          ("Incidents", None, "incident"), "A closed incident with lessons learned.", ["Deleting evidence while cleaning up.", "No written timeline."], "Walk me through the first hour of a suspected key leak."),
    ],
}


MANUALS["network"] = {
    "title": "Network Engineer: addressing, segmentation and layered fault-finding",
    "intro": "Networks fail in predictable layers. Learn to address and segment cleanly, read a config for mistakes, recognise normal and odd traffic, and walk the layers in order. Everything here runs on text you paste or on public hosts.",
    "outcome": "A clean addressing plan with no overlaps, a reviewed config, one capture explained, and a layered troubleshooting runbook.",
    "steps": [
        S("subnet", "Plan the addressing", "Good addressing is boring: no overlaps, room to grow, one block per purpose.",
          ["Open Subnet and VLSM and subnet 192.168.10.0/26: read the usable hosts and the broadcast address.", "Plan an office in 10.20.0.0/22 with the VLSM planner: 60 staff, 20 guests, 10 servers, two point-to-point links.", "Paste your planned networks into the overlap check, then summarise the routes."],
          ("Subnet and VLSM", None, "subnet"), "A plan whose subnets don't overlap and each has spare room.", ["Sizing a subnet to exactly today's hosts.", "Forgetting the network and broadcast addresses."], "How many hosts fit in a /27 and why is it 30, not 32?"),
        S("config", "Review a device config", "Most breaches of network gear are default passwords, telnet and open management.",
          ["Open Config review and load the sample.", "Read each high finding and say what an attacker would do with it.", "Write the fix for each, then paste your fixed version and run it again."],
          ("Config review", None, "config"), "No high findings, and you can explain each fix.", ["Treating 'no findings' as 'secure'.", "Fixing the symptom and not the habit that caused it."], "Why is SNMP community 'public' a problem?"),
        S("capture", "Read what is on the wire", "Traffic has shapes: handshakes, resets, scans, ARP chatter.",
          ["Open Packet capture and load the sample.", "Find the completed TCP handshake, then the burst of SYNs to many ports.", "Decide: scan, monitoring or a broken client, and what you'd check next."],
          ("Packet capture", None, "capture"), "You can explain the finding and one alternative explanation.", ["Calling one pattern an attack without context.", "Capturing on a network you don't own."], "What does a SYN without a SYN-ACK tell me?"),
        S("diag", "Test the path", "Names, then addresses, then ports: one layer at a time.",
          ["Open DNS and reachability and look up a site you use.", "Test TCP 443 on it, then a closed port, and compare the results.", "Say which layer each result rules in or out."],
          ("DNS and reachability", None, "diag"), "You can say what 'open', 'closed' and 'filtered' mean.", ["Testing hosts you don't own at scale.", "Blaming the network for a DNS problem."], "If ping to an IP works but the name fails, what is wrong?"),
        S("calc", "Size the pipe", "Bandwidth isn't throughput: window, latency and overhead decide the speed.",
          ["Open Calculators and find how long 200 GB takes over 100 Mbps at 85% efficiency.", "Enter 1000 Mbps and 80 ms with a 64 KB window and read the limit.", "Decide what you'd change to fill the link."],
          ("Calculators", None, "calc"), "You can explain why a fast link can still be slow.", ["Using megabits and megabytes interchangeably."], "Why can one TCP stream fail to fill a long fast link?"),
        S("ref", "Keep a method and a reference", "The method is the skill; the table is just memory.",
          ["Open Reference and read the troubleshooting method.", "Write your own one-page runbook for 'the internet is down', layer by layer.", "Look up five ports and what each should never be exposed for."],
          ("Reference", None, "ref"), "A runbook someone else could follow.", ["Skipping the physical layer.", "Changing three things at once."], "Walk me through troubleshooting 'I can't reach the file server'."),
    ],
}

MANUALS["itsupport"] = {
    "title": "IT Specialist: fix it, protect it, know what you own, write it down",
    "intro": "Support work is a method: ask what changed, check the cheap causes first, change one thing at a time, confirm with the person and document. These trackers let you practise that loop and the admin routines around it.",
    "outcome": "A worked ticket history, an inventory with warranty dates, one event log read, completed checklists and a storage forecast.",
    "steps": [
        S("tickets", "Work a ticket properly", "A ticket is a short story: symptom, checks, fix, confirmation.",
          ["Open Helpdesk and log a Wi-Fi ticket. Tick the checklist items as you try them.", "Add a note for each thing you change, then resolve it.", "Open an urgent ticket and watch the SLA clock."],
          ("Helpdesk", None, "tickets"), "A resolved ticket with a timeline someone else could follow.", ["Closing without confirming with the person.", "No notes on what was changed."], "A user can't print: what do I check first?"),
        S("assets", "Know what you own", "You can't patch, insure or retire what you haven't listed.",
          ["Open Inventory and add every computer, phone and printer you manage.", "Enter warranty end dates and read which are expiring.", "Mark retired devices instead of deleting them."],
          ("Inventory", None, "assets"), "Every device is listed with an owner and a warranty date.", ["Keeping the list in your head.", "Deleting retired devices so there's no history."], "Which fields matter most in an asset record?"),
        S("events", "Read the event log", "The log shows the story: who signed in, from where, and what changed.",
          ["Open Event log reader and load the sample.", "Read the failed-logon burst and the success after it.", "Rank the findings and write what you would do first."],
          ("Event log reader", None, "events"), "You can explain the top finding and the evidence for it.", ["Ignoring a success that follows many failures.", "Clearing logs while investigating."], "What does event 4625 followed by 4624 from the same address mean?"),
        S("checklists", "Use checklists for routines", "Onboarding and offboarding are where access mistakes hide.",
          ["Open Checklists and run Onboard for an imaginary new hire.", "Run Offboard for a leaver and note which step people forget.", "Adapt one list to your own environment."],
          ("Checklists", None, "checklists"), "Both lists run to the end and you've edited one for your world.", ["Deleting a leaver's account on day one instead of disabling it."], "What should happen first when someone leaves?"),
        S("capacity", "Forecast and protect", "Disks fill and hardware fails on a schedule you can estimate.",
          ["Open Capacity and RAID and forecast a 1 TB disk at 70% used growing 25 GB a month.", "Work out the downtime allowed at 99.9% availability.", "Compare RAID 1, 5, 6 and 10 for four 4 TB disks."],
          ("Capacity and RAID", None, "capacity"), "You can say when to order storage and why RAID is not a backup.", ["Treating RAID as a backup.", "Ordering storage when the disk is already full."], "Why isn't RAID a backup?"),
        S("cheats", "Build your own toolbox", "A short list of safe, tested commands beats memory at 2 a.m.",
          ["Open Cheat sheets and read the PowerShell and Active Directory lists.", "Try three read-only commands on your own machine.", "Start a personal notes file of fixes that worked."],
          ("Cheat sheets", None, "cheats"), "A notes file with five fixes and the commands behind them.", ["Pasting a command you don't understand into a production machine."], "Which commands are safe to run first when a PC is slow?"),
    ],
}


def manual_for(track: str) -> dict | None:
    return MANUALS.get(track)


def _all_done() -> dict[str, list[str]]:
    raw = state.kv_get("manual_done")
    return json.loads(raw) if raw else {}


def get(track: str) -> dict | None:
    m = MANUALS.get(track)
    if not m:
        return None
    return {"track": track, **m, "done": _all_done().get(track, [])}


def set_done(track: str, step: str, done: bool) -> dict | None:
    m = MANUALS.get(track)
    if not m or step not in {s["id"] for s in m["steps"]}:
        return None
    allv = _all_done()
    cur = set(allv.get(track, []))
    (cur.add if done else cur.discard)(step)
    allv[track] = sorted(cur)
    state.kv_set("manual_done", json.dumps(allv))
    return get(track)
