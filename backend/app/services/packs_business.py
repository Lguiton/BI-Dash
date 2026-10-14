"""Business-side field packs: consulting, IT project management, digital marketing, revenue operations, revenue-system security, UI/UX."""
from __future__ import annotations

import colorsys
import re
import time
from datetime import date
from urllib.parse import urlencode, urlparse

from app.services import field_howto as fh
from app.services.fieldpacks import E, I, PackError, md, num, pack, page, rows, split, table_html, tool, txt

BIZ, ITPM, MKT, REV, RSEC, UX = "Business consulting", "IT project management", "Digital marketing", "Revenue operations", "Revenue-system security", "UI/UX and graphic design"
fh.AREAS.extend([BIZ, ITPM, MKT, REV, RSEC, UX])
g = fh._g

pack("biz", BIZ, "Project management", "SWOT, OKRs, decision matrix and SOP writer for consulting work.", "pm", "e.g. owner and staff disagree, growth has stalled", "business consulting leadership strategy swot okr decision matrix sop process owner")
pack("itpm", ITPM, "Project management", "Critical path, earned value, change requests and go-live checklist.", "pm", "e.g. project over budget, cutover plan", "it project manager critical path earned value change request go-live cutover schedule budget")
pack("mkt", MKT, "Cloud and design", "Campaign numbers, content calendar and tracked links.", "analyst", "e.g. ads cost too much, what to post", "digital marketing social media campaign ctr cpc roas content calendar utm ads")
pack("revops", REV, "Business intelligence", "Funnel, pipeline coverage and unit economics (LTV, CAC, payback).", "analyst", "e.g. deals stall, is growth profitable", "revenue operations revops funnel pipeline coverage ltv cac payback churn sales")
pack("revsec", RSEC, "Cybersecurity", "Defensive checks on who can touch money: access review, SaaS inventory, card-data scope.", "security", "e.g. who can approve refunds, card data scope", "revsecops revenue security access review separation of duties saas inventory pci payment billing crm")
pack("ux", UX, "Cloud and design", "Contrast checker, type and colour scales, usability test plan.", "fullstack", "e.g. text hard to read, test a design", "ui ux design graphic designer contrast wcag palette type scale usability test accessibility")

# ------------------------------------------------------------------ guides
g("biz-diagnose", BIZ, "A business is stuck and nobody agrees why", "diagnose problem root cause stuck stalled disagreement consulting discovery interviews", "Teams argue about solutions before they agree on the problem.", ["Interview 5 to 8 people in different roles with the same questions: what works, what hurts, what would you change.", "Write the problem as one sentence with a number (for example: quotes go out 9 days late, 30% are lost).", "Check the number against real data before believing anyone.", "Run the SWOT tool on the evidence, not opinions.", "Agree the problem in writing with the owner before proposing fixes."], "The owner can state the problem in one sentence with a number and agrees it is the right one.", 120, "", "SWOT builder")
g("biz-okr", BIZ, "Setting goals people actually follow", "okr goals objectives key results targets vague kpi alignment", "Goals without numbers cannot be missed or met.", ["Write one objective: a short, plain statement of what to achieve this quarter.", "Add 2 to 4 key results, each with a number, a starting point and a target.", "Use the OKR builder to flag vague words.", "Name one owner per key result.", "Review weekly: green, yellow or red, and what blocks it."], "Every key result passes the 'could someone prove it was done' test.", 45, "", "OKR builder")
g("biz-decide", BIZ, "Choosing between options without going in circles", "decision matrix choose options criteria weights compare vendor hire pick", "Gut feeling hides what you actually care about.", ["List the options (3 to 5) and the criteria that matter (4 to 6).", "Give each criterion a weight that adds up to what you want to stress.", "Score each option 1 to 5 per criterion, ideally by two people independently.", "Check: does the winner change if all weights are equal?", "If it does, talk about the weights, not the scores."], "The winner is stable under equal weights, or you know which weight decides it.", 40, "", "Decision matrix")
g("biz-sop", BIZ, "Writing a procedure staff will use", "sop standard operating procedure process document checklist handover training", "A procedure nobody follows is usually too long or out of date.", ["Watch the best person do the task and write what they actually do.", "Number the steps, one action each.", "Add who does it, what tool, and how to tell it is done right.", "Have someone new follow it without help and fix every place they get stuck.", "Put an owner and a review date on it."], "A new person completes the task correctly using only the document.", 90, "", "SOP writer")
g("biz-change", BIZ, "Staff resist a change", "change management resistance adoption staff pushback rollout communication leadership", "People resist loss and surprise more than the change itself.", ["Say plainly why, what changes for them, and what stays the same.", "Involve the people most affected before the decision is final.", "Start with a small pilot group and use their feedback.", "Give training at the moment of need, not weeks before.", "Check use after 2 and 6 weeks and remove obstacles."], "Most of the affected group uses the new way without being reminded.", 60)
g("biz-meetings", BIZ, "Meetings that go nowhere", "meetings agenda actions decisions facilitation leadership team cadence", "Without a decision or an action, a meeting is only conversation.", ["Write the purpose as a decision or an outcome.", "Send an agenda with who needs to decide what.", "Time-box each item and park side topics.", "End by reading back decisions, owners and dates.", "Cancel the meeting if the purpose can be met by a message."], "Everyone leaves knowing what was decided and who does what by when.", 20)

g("pm2-late-cost", ITPM, "The IT project is over budget or behind", "earned value budget overrun schedule cpi spi behind forecast eac cost", "Spent money and finished work are different things.", ["Gather planned value (PV), earned value (EV, the value of work actually done) and actual cost (AC).", "Use the earned value tool: CPI under 1 means over cost, SPI under 1 means behind.", "Look for the work items causing the gap.", "Re-forecast the finish with EAC, and tell the sponsor early.", "Choose: cut scope, add time, or add money."], "A forecast cost and date the sponsor has seen and accepted.", 45, "", "Earned value")
g("pm2-critical", ITPM, "Which tasks decide the end date?", "critical path schedule dependencies float slack duration plan network", "Only tasks on the critical path delay the finish.", ["List tasks, durations and what each depends on.", "Run the critical path tool.", "Protect the critical tasks: best people first, no multitasking.", "Tasks with float can slip within it; do not waste worry there.", "Re-run when anything changes."], "You can name the critical tasks and the total duration.", 40, "", "Critical path")
g("pm2-change", ITPM, "Handling a change request properly", "change request control scope impact approve cost schedule risk cab", "Unrecorded changes are how projects quietly double.", ["Write what is asked and why.", "Estimate effect on cost, time, risk and other systems.", "Get a named approver to say yes or no in writing.", "Update the plan and baseline only after approval.", "Log it."], "Every change in the project has an approved request.", 25, "", "Change request")
g("pm2-golive", ITPM, "A go-live that does not go wrong", "go live cutover launch deployment rollback checklist freeze communication readiness", "Most launch failures were predictable.", ["Agree go and no-go criteria in advance.", "Rehearse the cutover once on a copy.", "Write the rollback steps and decide the point after which you cannot roll back.", "Tell users what changes and when; name the support contact.", "Staff the first days with people who built it."], "Rollback has been practised, and go/no-go criteria are signed off.", 90, "", "Go-live checklist")
g("pm2-raid", ITPM, "Tracking risks, assumptions, issues and dependencies", "raid log risks assumptions issues dependencies register owner review", "Four lists, one habit: review weekly.", ["Risks: might happen. Assumptions: believed true. Issues: happening now. Dependencies: needs others.", "Give each an owner and a next date.", "Turn a risk into an issue when it lands.", "Close items when resolved; do not let the list grow stale."], "Each item has an owner and a date.", 30)
g("pm2-handover", ITPM, "Handing a system over to support", "handover support operations documentation runbook training warranty transition", "Support cannot fix what they were never shown.", ["Write a runbook: how to start, check, restart and recover.", "List who to call for what.", "Train the support team on real failure cases.", "Agree a warranty period and what counts as a defect.", "Get a signed acceptance."], "Support has resolved a test incident alone using the runbook.", 90)

g("mkt-costly", MKT, "Ads cost too much for what they bring", "ads expensive cpa roas cost conversions campaign profitable break even paid media", "Cost per sale only matters compared with profit per sale.", ["Work out profit margin per sale; break-even ROAS is 1 divided by margin.", "Use the campaign calculator on real spend and conversions.", "If ROAS is below break-even, check the landing page conversion rate before changing ads.", "Pause the worst 20% of ads and audiences.", "Test one change at a time for at least a week."], "ROAS is above break-even for two weeks in a row.", 45, "", "Campaign metrics")
g("mkt-calendar", MKT, "Not knowing what to post", "content calendar social media posts ideas schedule plan consistency platforms", "Consistency beats bursts, and planning removes the daily guessing.", ["Pick 3 to 4 themes your customers care about.", "Choose 1 to 2 platforms where they actually are.", "Use the calendar tool to rotate themes across weeks.", "Batch-write a week at a time.", "Check what got replies or clicks monthly and repeat it."], "A month of posts is written before the month starts.", 60, "", "Content calendar")
g("mkt-track", MKT, "Not knowing which post or ad brought the customer", "utm tracking links attribution analytics campaign source medium google analytics", "Without tagged links, all traffic looks the same.", ["Use one naming style: lowercase, no spaces.", "Build each link with source, medium and campaign.", "Use the tagged link in the post, email or ad.", "Check the campaign shows up in your analytics within a day."], "Your analytics lists each campaign by name.", 20, "", "UTM link builder")
g("mkt-lowconv", MKT, "Lots of clicks, almost no sales", "conversion rate landing page checkout abandonment form friction trust clicks no sales", "The ad worked; the page did not.", ["Check the page loads in under 3 seconds on a phone.", "Make the first screen say what you do and what to click.", "Cut form fields to the minimum.", "Add proof: reviews, photos, guarantees.", "Test one change, measure conversion rate."], "Conversion rate rises over two weeks without more spend.", 60)
g("mkt-brand", MKT, "Posts look inconsistent", "brand voice style guide colors fonts tone consistent templates social", "A small style sheet saves hours.", ["Choose 2 colors, 1 or 2 fonts and one logo placement.", "Write three tone words and one example sentence.", "Make templates for your three most common posts.", "Keep them in one shared folder."], "Anyone can make an on-brand post from the templates.", 90)
g("mkt-privacy", MKT, "Email and tracking rules", "email marketing consent unsubscribe privacy cookies gdpr can-spam compliance list", "Rules differ by country; breaking them costs more than the marketing earns.", ["Only email people who asked or are clients.", "Put an unsubscribe link and a real address in every email.", "Honor unsubscribes within days.", "Tell visitors about tracking cookies where required.", "Ask a lawyer about rules in your market."], "Every email has a working unsubscribe, and your list has consent records.", 40, "This is general information, not legal advice.")

g("rev-stall", REV, "Deals stall in the pipeline", "pipeline stalled deals velocity stage conversion funnel drop sales stuck", "A funnel shows where deals die; guessing wastes effort.", ["Count deals at each stage.", "Use the funnel tool to find the stage with the biggest drop.", "Read ten lost deals at that stage and note the reason.", "Add one clear exit rule for the stage.", "Re-measure in 4 weeks."], "The worst stage's conversion improves.", 60, "", "Funnel and coverage")
g("rev-coverage", REV, "Will we hit the revenue target?", "pipeline coverage quota forecast target win rate gap revenue plan", "Pipeline needed equals target divided by win rate.", ["Use your real win rate over the last 6 months.", "Run the coverage calculator.", "If coverage is under what is needed, add pipeline or cut the target now."], "You know the pipeline needed and the gap.", 20, "", "Funnel and coverage")
g("rev-econ", REV, "Is growth actually profitable?", "unit economics ltv cac payback churn gross margin profitable subscription saas", "Growth that costs more than a customer is worth loses money faster.", ["Compute LTV from revenue per customer, margin and churn.", "Compute payback: months to earn back the cost of winning a customer.", "LTV:CAC below 3, or payback over 12 to 18 months, is a warning sign for small subscription businesses.", "Reduce churn or CAC before buying more growth."], "LTV:CAC and payback are written down for each channel.", 40, "", "Unit economics")
g("rev-data", REV, "Sales, billing and marketing numbers do not match", "data mismatch crm billing marketing source of truth definitions revenue reconcile", "Each system defines 'customer' and 'revenue' differently.", ["Write one definition for each key term.", "Choose a system of record for each.", "Reconcile one month by hand and list the differences.", "Fix the biggest cause first."], "One month reconciles to within an agreed margin.", 90)
g("rev-handoff", REV, "Leads fall between marketing and sales", "lead handoff routing sla follow up marketing sales alignment scoring response time", "Slow follow-up is the cheapest leak to fix.", ["Define what a qualified lead is, in writing.", "Set a response-time target (hours, not days).", "Route automatically and alert when the target is missed.", "Review weekly which leads sales rejected and why."], "Median response time is within the target.", 45)

g("rsec-sod", RSEC, "One person can create and approve their own payments", "separation of duties access review refund invoice approve fraud billing permissions", "The risk is one person doing both halves of a money action.", ["List who has which permission in billing, CRM and payment tools.", "Run the access review tool.", "Split any conflicting pair across two people.", "If you cannot split it (small team), add a second-person review of the report.", "Repeat quarterly."], "No one holds both sides of a conflicting pair, or a compensating control is written down.", 60, "", "Access review")
g("rsec-saas", RSEC, "Nobody knows what apps hold customer or money data", "saas inventory shadow it apps owners sso mfa vendor review data customer billing", "You cannot protect what you have not listed.", ["List every app, its owner and the data it holds.", "Note whether sign-in is protected by MFA or SSO.", "Run the inventory tool to see risk and overdue reviews.", "Close accounts of apps nobody uses.", "Review yearly."], "Every app with money or customer data has an owner, MFA and a recent review.", 90, "", "SaaS inventory")
g("rsec-pci", RSEC, "Taking card payments safely", "pci card data payment scope saq stripe hosted checkout cardholder compliance", "The less card data touches your systems, the smaller your obligations.", ["Use a payment provider's hosted checkout or hosted fields.", "Never store card numbers or security codes yourself.", "Use the scope tool for a first idea of your level.", "Confirm the actual requirement with your payment provider or an assessor."], "Card numbers never appear in your systems, logs or emails.", 45, "A rough guide only: your payment provider decides your actual requirement.", "PCI scope helper")
g("rsec-keys", RSEC, "Keys and webhooks for billing systems", "api keys webhook secret rotation stripe billing integration leak rotate", "A leaked billing key can move real money.", ["Keep keys in a secrets store or environment variables.", "Use restricted keys with only the permissions needed.", "Verify webhook signatures.", "Rotate keys when staff leave and once a year.", "Alert on unusual refunds or payouts."], "Keys are restricted and not in code, chat or email.", 40)
g("rsec-fraud", RSEC, "Chargebacks and refund abuse", "chargeback fraud refund abuse dispute rate monitoring billing risk", "Disputes cost more than the sale and can end your merchant account.", ["Track dispute and refund rates per week.", "Keep clear receipts, delivery proof and terms.", "Flag unusual patterns: many refunds by one person or to one card.", "Respond to disputes within the deadline with evidence."], "Dispute rate is tracked and under your provider's threshold.", 45)

g("ux-contrast", UX, "Text is hard to read", "contrast wcag accessibility text color background readable aa aaa low vision", "Low contrast excludes many readers and fails accessibility rules.", ["Measure the text and background colors with the contrast checker.", "Aim for at least 4.5:1 for normal text and 3:1 for large text.", "Darken the text or lighten the background until it passes.", "Check on a phone outdoors."], "Contrast ratio reaches at least 4.5 to 1 for body text.", 15, "", "Contrast checker")
g("ux-type", UX, "Typography looks off", "typography type scale font size hierarchy line height spacing readable headings", "A consistent scale makes pages look planned.", ["Pick a base size (16 px for body text).", "Pick one ratio (1.25 is a good start).", "Generate the scale and use only those sizes.", "Use line height around 1.5 for body text.", "Limit lines to about 60 to 75 characters."], "Only scale sizes are used across the design.", 30, "", "Type scale")
g("ux-palette", UX, "Choosing a color palette", "color palette brand tints shades primary neutral accessible theme dark mode", "Start from one brand color and derive steps, then check contrast.", ["Pick one brand color.", "Generate lighter and darker steps.", "Use steps for backgrounds, borders and text.", "Check every text-on-background pair for contrast.", "Test dark mode separately."], "Every text pair passes contrast.", 30, "", "Palette builder")
g("ux-test", UX, "Not knowing if people can use it", "usability test users tasks think aloud five users observation feedback prototype", "Five people reveal most major problems.", ["Write 3 to 5 realistic tasks (not instructions).", "Recruit 5 people like your real users.", "Ask them to think aloud; do not help.", "Record success, time and where they hesitated.", "Fix the top problems and test again."], "Most testers complete the main task without help.", 120, "", "Usability test plan")
g("ux-hand", UX, "Handing a design to developers", "handoff design developers specs components spacing assets states responsive figma", "Missing states and sizes become guesses in code.", ["Name components and reuse them.", "Show every state: empty, loading, error, hover, disabled.", "Give spacing from one scale.", "Export assets at the sizes needed.", "Review the build against the design with the developer."], "The developer built it without needing to ask about missing states.", 60)
g("ux-brief", UX, "Starting a design job without a clear brief", "design brief client goals audience brand deliverables feedback rounds scope graphic", "Unclear briefs lead to endless revisions.", ["Ask: who is it for, what should they do, what exists, what must be avoided.", "Agree deliverables, formats, sizes and number of revision rounds.", "Collect examples the client likes and dislikes.", "Get the brief approved before starting."], "The client signed the brief including revision rounds.", 30)

# ------------------------------------------------------------------ tools: business consulting
@tool("biz", "swot", "SWOT builder", "Lists strengths, weaknesses, opportunities and threats, and checks that they are specific, not slogans.",
      [I("name", "Business or project"), I("s", "Strengths (one per line)", "area"), I("w", "Weaknesses (one per line)", "area"), I("o", "Opportunities (one per line)", "area"), I("t", "Threats (one per line)", "area")])
def swot(v):
    name = txt(v, "name", 80, True)
    q = {k: rows(v, k, 12) for k in "swot"}
    if not any(q.values()):
        raise PackError("Fill in at least one box.")
    vague = [x for k in q for x in q[k] if len(x.split()) < 3 or not re.search(r"\d", x) and len(x.split()) < 5]
    notes = []
    if vague:
        notes.append(f"{len(vague)} item(s) are short and may be slogans. Add evidence or a number: {', '.join(repr(x) for x in vague[:3])}.")
    if not all(q.values()):
        notes.append("One or more boxes are empty: a SWOT with only strengths is a sales pitch, not a diagnosis.")
    sec = [("Strengths", q["s"] or ["(none)"]), ("Weaknesses", q["w"] or ["(none)"]), ("Opportunities", q["o"] or ["(none)"]), ("Threats", q["t"] or ["(none)"]),
           ("Next step", ["Use strengths to take the biggest opportunity.", "Fix the weakness that makes the biggest threat worse.", "Pick at most three actions, each with an owner and date."])]
    return {"says": f"SWOT for {name}: {sum(map(len, q.values()))} points.", "notes": notes, "markdown": md(f"SWOT: {name}", sec)}


@tool("biz", "okr", "OKR builder", "Checks that each key result has a number and flags vague words.", [I("objective", "Objective"), I("krs", "Key results (one per line)", "area", help="e.g. Raise repeat orders from 22% to 30%")])
def okr(v):
    obj = txt(v, "objective", 150, True)
    krs = rows(v, "krs", 6)
    if not krs:
        raise PackError("Add at least one key result.")
    vague_words = re.compile(r"\b(improve|better|more|increase|enhance|optimi[sz]e|good|great|strong|best|leverage|support)\b", re.I)
    out, notes = [], []
    for i, k in enumerate(krs, 1):
        nums = re.findall(r"\d+(?:[.,]\d+)?%?", k)
        has_target = len(nums) >= 2 or (len(nums) == 1 and re.search(r"\bby\b|\bto\b|\bat least\b|\bunder\b|\bover\b", k, re.I))
        flags = []
        if not nums:
            flags.append("no number")
        elif not has_target:
            flags.append("no starting point or target")
        if vague_words.search(k) and not nums:
            flags.append("vague word")
        out.append({"key_result": k, "ok": not flags, "flags": ", ".join(flags) or "measurable"})
        if flags:
            notes.append(f"KR{i} ({', '.join(flags)}): rewrite as 'from X to Y by date'.")
    if len(krs) > 4:
        notes.append("More than 4 key results usually means the objective is too wide.")
    good = sum(r["ok"] for r in out)
    return {"says": f"{good} of {len(out)} key results are measurable.", "results": out, "notes": notes,
            "markdown": md(f"Objective: {obj}", [("Key results", [f"{r['key_result']} ({r['flags']})" for r in out]), ("Rhythm", ["Review weekly: green, yellow or red, and what blocks it.", "Score at the end of the quarter and write one lesson."])])}


@tool("biz", "matrix", "Decision matrix", "Weighted scoring that also tells you whether the winner depends on your weights.",
      [I("criteria", "Criteria: name, weight (one per line)", "area", "Cost, 5\nQuality, 4\nSpeed, 3"), I("scores", "Scores: option, then a 1-5 score per criterion in order (one option per line)", "area", "Vendor A, 3, 4, 5\nVendor B, 5, 3, 2")])
def matrix(v):
    crit = []
    for ln in rows(v, "criteria", 10):
        c = split(ln)
        if len(c) < 2:
            raise PackError(f"Criterion '{ln[:30]}' needs a name and a weight.")
        try:
            crit.append((c[0], float(c[1])))
        except ValueError:
            raise PackError(f"Weight for {c[0]} must be a number.") from None
    if len(crit) < 2 or any(w < 0 for _, w in crit) or sum(w for _, w in crit) <= 0:
        raise PackError("Give at least two criteria with weights of 0 or more.")
    opts = []
    for ln in rows(v, "scores", 10):
        c = split(ln)
        if len(c) != len(crit) + 1:
            raise PackError(f"'{c[0][:30]}' needs {len(crit)} scores, one for each criterion.")
        try:
            sc = [float(x) for x in c[1:]]
        except ValueError:
            raise PackError(f"Scores for {c[0]} must be numbers.") from None
        if any(not 0 <= s <= 10 for s in sc):
            raise PackError(f"Scores for {c[0]} must be between 0 and 10.")
        opts.append((c[0], sc))
    if len(opts) < 2:
        raise PackError("Give at least two options.")
    tw = sum(w for _, w in crit)
    res = sorted(({"option": n, "weighted_score": round(sum(s * w for s, (_, w) in zip(sc, crit)) / tw, 2), "equal_weights_score": round(sum(sc) / len(sc), 2)} for n, sc in opts), key=lambda r: -r["weighted_score"])
    eq_best = max(res, key=lambda r: r["equal_weights_score"])["option"]
    stable = eq_best == res[0]["option"]
    gap = res[0]["weighted_score"] - res[1]["weighted_score"]
    notes = [] if stable else [f"With equal weights, {eq_best} would win instead. Your weights decide this choice, so talk about the weights first."]
    if gap < 0.25:
        notes.append("The top two are within 0.25 points: treat it as a tie and decide on something the matrix does not capture.")
    return {"says": f"{res[0]['option']} scores highest ({res[0]['weighted_score']} out of 10 scale), {'and it also wins on equal weights' if stable else 'but it does not win on equal weights'}.", "ranking": res, "notes": notes}


@tool("biz", "sop", "SOP writer", "Turns your steps into a numbered procedure with an owner, a check and a review date.", [I("title", "Task name"), I("owner", "Owner"), I("purpose", "Why it matters", "area"), I("steps", "Steps (one per line)", "area"), I("tools", "Tools or materials (optional)", "area")])
def sop(v):
    title, steps = txt(v, "title", 100, True), rows(v, "steps", 40)
    if not steps:
        raise PackError("Add at least one step.")
    long = [s for s in steps if len(s.split()) > 30]
    sec = [("Purpose", txt(v, "purpose", 400) or "(why this matters)"), ("Owner", txt(v, "owner", 80) or "(name)"), ("Tools and materials", rows(v, "tools", 15) or ["(none)"]),
           ("Steps", "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))), ("How to know it is done right", ["(write the visible result)", "(write one check someone else can do)"]), ("Review", [f"Review on {time.strftime('%Y-%m-%d', time.localtime(time.time() + 180 * 86400))} or after any change."])]
    return {"says": f"SOP with {len(steps)} steps.", "notes": ([f"{len(long)} step(s) are long: split them to one action each."] if long else []), "markdown": md(f"SOP: {title}", sec)}


# ------------------------------------------------------------------ IT project management
@tool("itpm", "critical", "Critical path", "Finds the tasks that decide the end date and how much slack the others have.",
      [I("tasks", "Tasks: id, name, days, depends on (separate with ;) (one per line)", "area", "A, Plan, 3,\nB, Build, 8, A\nC, Test, 4, B\nD, Docs, 5, A\nE, Launch, 1, C;D")])
def critical(v):
    tasks, order = {}, []
    for ln in rows(v, "tasks", 80):
        c = split(ln)
        if len(c) < 3:
            raise PackError(f"'{ln[:30]}' needs an id, a name and days.")
        tid = c[0]
        if tid in tasks:
            raise PackError(f"Id {tid} is used twice.")
        try:
            d = float(c[2])
        except ValueError:
            raise PackError(f"Days for {tid} must be a number.") from None
        if d < 0:
            raise PackError(f"Days for {tid} cannot be negative.")
        tasks[tid] = {"name": c[1], "d": d, "deps": [x.strip() for x in (c[3] if len(c) > 3 else "").split(";") if x.strip()]}
        order.append(tid)
    if not tasks:
        raise PackError("Add at least one task.")
    for t, x in tasks.items():
        for dp in x["deps"]:
            if dp not in tasks:
                raise PackError(f"{t} depends on {dp}, which is not in the list.")
    es, ef, state = {}, {}, {}

    def visit(t):
        if state.get(t) == 2:
            return
        if state.get(t) == 1:
            raise PackError("The dependencies form a loop, so no end date can be worked out.")
        state[t] = 1
        for dp in tasks[t]["deps"]:
            visit(dp)
        es[t] = max((ef[dp] for dp in tasks[t]["deps"]), default=0.0)
        ef[t] = es[t] + tasks[t]["d"]
        state[t] = 2
    for t in order:
        visit(t)
    end = max(ef.values())
    succ = {t: [u for u in tasks if t in tasks[u]["deps"]] for t in tasks}
    lf, ls = {}, {}
    for t in sorted(tasks, key=lambda x: -ef[x]):
        lf[t] = min((ls[s] for s in succ[t]), default=end)
        ls[t] = lf[t] - tasks[t]["d"]
    res = [{"id": t, "task": tasks[t]["name"], "days": tasks[t]["d"], "earliest_start": es[t], "earliest_finish": ef[t], "slack": round(ls[t] - es[t], 2), "critical": abs(ls[t] - es[t]) < 1e-9} for t in order]
    crit = [r["id"] for r in sorted((r for r in res if r["critical"]), key=lambda r: r["earliest_start"])]
    return {"says": f"The project takes {end:g} days. Critical tasks: {', '.join(crit)}.", "tasks": res, "notes": ["Any delay to a critical task delays the whole project day for day.", "Durations are your estimates; use the three-point estimator for uncertain ones."]}


@tool("itpm", "evm", "Earned value", "Cost and schedule health from planned value, earned value and actual cost.", [I("bac", "Budget at completion (total planned cost)", "number"), I("pv", "Planned value (work scheduled to date, in money)", "number"), I("ev", "Earned value (work really done to date, in money)", "number"), I("ac", "Actual cost to date", "number")])
def evm(v):
    bac, pv, ev, ac = num(v, "bac", 0.01), num(v, "pv", 0), num(v, "ev", 0), num(v, "ac", 0)
    if ev > bac * 1.0001 or pv > bac * 1.0001:
        raise PackError("Earned or planned value cannot be more than the total budget.")
    cpi = ev / ac if ac else None
    spi = ev / pv if pv else None
    eac = bac / cpi if cpi else None
    out = {"cost_variance": round(ev - ac, 2), "schedule_variance": round(ev - pv, 2), "cpi": round(cpi, 2) if cpi else None, "spi": round(spi, 2) if spi else None,
           "forecast_total_cost": round(eac, 2) if eac else None, "forecast_overrun": round(eac - bac, 2) if eac else None, "work_left_cost_forecast": round(eac - ac, 2) if eac else None}
    bits = []
    if cpi is not None:
        bits.append(f"each dollar spent has earned ${cpi:.2f} of work ({'over' if cpi < 1 else 'on or under'} budget)")
    if spi is not None:
        bits.append(f"you have done {spi:.0%} of the planned work ({'behind' if spi < 1 else 'on or ahead'})")
    out["says"] = "At this pace, " + " and ".join(bits) + ("; forecast cost " + f"${eac:,.0f} against a ${bac:,.0f} budget." if eac else ".") if bits else "Add actual cost or planned value to see the indexes."
    out["notes"] = ["The forecast assumes the cost trend so far continues. If a one-off cause explains the overrun, forecast actual cost plus the remaining budget instead.", "Earned value is only as honest as the 'percent done' behind it."]
    return out


@tool("itpm", "change", "Change request", "A one-page change request with impact fields and an approval block.", [I("project", "Project"), I("title", "Change"), I("why", "Why", "area"), I("cost", "Extra cost"), I("days", "Extra days"), I("risk", "Risks and other systems affected", "area"), I("requester", "Requested by")])
def change(v):
    pr, ti = txt(v, "project", 100, True), txt(v, "title", 150, True)
    body = ("<table>" + "".join(f"<tr><th>{E(k)}</th><td>{E(x) or '<i>not filled in</i>'}</td></tr>" for k, x in [("Change", ti), ("Requested by", txt(v, "requester", 80)), ("Why", txt(v, "why", 500)), ("Extra cost", txt(v, "cost", 40)), ("Extra days", txt(v, "days", 40)), ("Risks and systems affected", txt(v, "risk", 500))]) + "</table>"
            "<h2>Decision</h2><p>&#9744; Approved &nbsp; &#9744; Rejected &nbsp; &#9744; More information needed</p><p>Approver: ____________________ Date: __________</p><p>Update the schedule, budget and risk log only after approval.</p>")
    return {"says": f"Change request for {pr}.", "html": page(f"Change request: {pr}", body)}


@tool("itpm", "golive", "Go-live checklist", "A cutover and rollback checklist for a launch.", [I("system", "System going live"), I("date", "Planned date"), I("rollback_owner", "Rollback decision owner"), I("users", "Who is affected", "area")])
def golive(v):
    s = txt(v, "system", 100, True)
    sec = [("Before (one week out)", ["Go and no-go criteria written and agreed", "Cutover rehearsed on a copy with timings noted", "Backups taken and a restore tested", "Users told what changes, when and who to call", "Support staffed for the first days"]),
           ("Cutover day", ["Freeze changes", "Take a final backup", "Run the steps in order and tick each one", "Run the smoke tests", "Decision point: go or roll back (by " + (txt(v, "rollback_owner", 60) or "the named owner") + ")"]),
           ("After", ["Watch errors and complaints hourly on day one", "Daily check for a week", "Collect issues in one list", "Hold a short review within two weeks"])]
    return {"says": f"Go-live checklist for {s}.", "markdown": md(f"Go-live: {s} ({txt(v, 'date', 30) or 'date to be set'})", sec)}


# ------------------------------------------------------------------ digital marketing
@tool("mkt", "campaign", "Campaign metrics", "Click rate, cost per click, cost per sale and return on ad spend, compared with break-even.",
      [I("spend", "Ad spend", "number"), I("impressions", "Impressions", "number"), I("clicks", "Clicks", "number"), I("conversions", "Sales or sign-ups", "number"), I("revenue", "Revenue from them", "number"), I("margin", "Profit margin on a sale (%)", "number", "40")])
def campaign(v):
    sp, im, cl, co, rev, mg = num(v, "spend", 0), num(v, "impressions", 0), num(v, "clicks", 0), num(v, "conversions", 0), num(v, "revenue", 0), num(v, "margin", 0.1, 100)
    if cl > im and im:
        raise PackError("Clicks cannot be more than impressions.")
    if co > cl and cl:
        raise PackError("Conversions cannot be more than clicks.")
    ratio = lambda a, b: round(a / b, 4) if b else None  # noqa: E731
    roas = ratio(rev, sp)
    be = round(100 / mg, 2)
    profit = round(rev * mg / 100 - sp, 2)
    out = {"ctr_pct": round(100 * cl / im, 2) if im else None, "cpc": ratio(sp, cl), "cpm": round(1000 * sp / im, 2) if im else None, "conversion_rate_pct": round(100 * co / cl, 2) if cl else None, "cost_per_sale": ratio(sp, co), "roas": roas, "break_even_roas": be, "profit_after_ads": profit}
    out["says"] = (f"Return on ad spend is {roas:.2f} against break-even {be:.2f}: " + ("this campaign makes money." if roas and roas >= be else "this campaign loses money at the current margin.")) if roas is not None else "Enter a spend above zero to see return."
    out["notes"] = ["Low click rate points to the ad; plenty of clicks but few sales points to the page or offer.", "Numbers from one week can be noise. Wait for enough sales before changing things."]
    return out


@tool("mkt", "calendar", "Content calendar", "Rotates your themes across platforms and weeks.", [I("topics", "Themes or topics (one per line)", "area"), I("platforms", "Platforms (comma separated)", "text", "Instagram, LinkedIn"), I("weeks", "Weeks", "number", "4"), I("per_week", "Posts per week per platform", "number", "3"), I("start", "Start date (YYYY-MM-DD)")])
def calendar(v):
    tp, pl = rows(v, "topics", 20), [p.strip() for p in str(v.get("platforms") or "").split(",") if p.strip()][:5]
    wk, pw = int(num(v, "weeks", 1, 12)), int(num(v, "per_week", 1, 14))
    if not tp or not pl:
        raise PackError("Give at least one topic and one platform.")
    try:
        d0 = date.fromisoformat(txt(v, "start", 10)) if txt(v, "start", 10) else date.today()
    except ValueError:
        raise PackError("Start date must look like 2026-11-02.") from None
    days = [0, 2, 4, 1, 3, 5, 6]
    out, k = [], 0
    for w in range(wk):
        for p in pl:
            for j in range(pw):
                day = d0.toordinal() + w * 7 + days[j % 7]
                out.append({"date": date.fromordinal(day).isoformat(), "platform": p, "theme": tp[k % len(tp)], "idea": "(write the post)"})
                k += 1
    out.sort(key=lambda r: (r["date"], r["platform"]))
    return {"says": f"{len(out)} posts planned across {wk} weeks.", "posts": out, "notes": ["Keep a mix: help, show, prove, ask. One in five posts can sell directly.", "Check which themes got replies after a month and plan more of those."]}


@tool("mkt", "utm", "UTM link builder", "Makes tagged links so analytics shows which post or ad brought each visitor.", [I("url", "Page address"), I("source", "Source (e.g. instagram)"), I("medium", "Medium (e.g. social, email, cpc)"), I("campaign", "Campaign name"), I("content", "Content or variant (optional)")])
def utm(v):
    u = txt(v, "url", 400, True)
    p = urlparse(u if "://" in u else "https://" + u)
    if p.scheme not in ("http", "https") or "." not in p.netloc:
        raise PackError("Enter the page address like example.com/offer.")
    params = {}
    for k in ("source", "medium", "campaign", "content"):
        x = re.sub(r"[^a-z0-9_\-]+", "-", txt(v, k, 60).lower()).strip("-")
        if k != "content" and not x:
            raise PackError(f"{k.capitalize()} is needed.")
        if x:
            params["utm_" + k] = x
    sep = "&" if p.query else "?"
    link = p._replace(fragment="").geturl() + sep + urlencode(params) + (f"#{p.fragment}" if p.fragment else "")
    return {"says": "Tagged link ready.", "link": link, "notes": ["Names are lowercased and cleaned so the same campaign is not split across spellings.", "Use the same source and medium names every time."]}


# ------------------------------------------------------------------ revenue operations
@tool("revops", "funnel", "Funnel and pipeline coverage", "Stage-to-stage conversion, the biggest leak, and the pipeline you need to hit a target.",
      [I("stages", "Stages: name, count (top to bottom, one per line)", "area", "Leads, 400\nQualified, 160\nProposal, 60\nWon, 18"), I("target", "Revenue target (optional)", "number", ""), I("avg_deal", "Average deal size (optional)", "number", ""), I("pipeline", "Open pipeline value now (optional)", "number", "")])
def funnel(v):
    st = []
    for ln in rows(v, "stages", 10):
        c = split(ln)
        if len(c) < 2:
            raise PackError(f"'{ln[:30]}' needs a stage name and a count.")
        try:
            st.append((c[0], float(c[1])))
        except ValueError:
            raise PackError(f"Count for {c[0]} must be a number.") from None
    if len(st) < 2:
        raise PackError("Give at least two stages.")
    if any(b > a for (_, a), (_, b) in zip(st, st[1:])):
        raise PackError("A later stage cannot have more items than the one before it.")
    steps = [{"from": a, "to": b, "conversion_pct": round(100 * nb / na, 1) if na else None, "lost": na - nb} for (a, na), (b, nb) in zip(st, st[1:])]
    worst = min((s for s in steps if s["conversion_pct"] is not None), key=lambda s: s["conversion_pct"])
    overall = round(100 * st[-1][1] / st[0][1], 2) if st[0][1] else None
    out = {"steps": steps, "overall_conversion_pct": overall, "says": f"Weakest step: {worst['from']} to {worst['to']} ({worst['conversion_pct']}% move on). Overall {overall}% of {st[0][0].lower()} reach {st[-1][0].lower()}."}
    notes = ["Compare against your own past months. Rates vary a lot by industry, so no single benchmark is shown."]
    if v.get("target") not in (None, ""):
        tg, ad = num(v, "target", 0), num(v, "avg_deal", 0.01, label="Average deal size")
        wr = st[-1][1] / st[-2][1] if st[-2][1] else None
        deals = tg / ad
        need = deals / (st[-1][1] / st[0][1]) if st[0][1] and st[-1][1] else None
        if need:
            out["deals_needed"] = round(deals, 1)
            out["top_of_funnel_needed"] = round(need)
        if wr and v.get("pipeline") not in (None, ""):
            pv = num(v, "pipeline", 0)
            win_val = pv * wr
            out["expected_from_open_pipeline"] = round(win_val)
            out["gap_to_target"] = round(tg - win_val)
            notes.append(f"Using your last-stage rate of {wr:.0%}, the open pipeline is expected to bring about ${win_val:,.0f}.")
    out["notes"] = notes
    return out


@tool("revops", "econ", "Unit economics", "Lifetime value, payback and LTV to CAC for a subscription or repeat-customer business.",
      [I("arpa", "Revenue per customer per month", "number"), I("margin", "Gross margin (%)", "number", "70"), I("churn", "Monthly churn (% of customers lost)", "number", "3"), I("cac", "Cost to win one customer", "number")])
def econ(v):
    a, m, ch, cac = num(v, "arpa", 0.01), num(v, "margin", 1, 100), num(v, "churn", 0.1, 100), num(v, "cac", 0.01)
    gm = a * m / 100
    life = 100 / ch
    ltv = gm * life
    ratio, pay = ltv / cac, cac / gm
    verdict = "healthy" if ratio >= 3 and pay <= 12 else "watch" if ratio >= 1.5 and pay <= 24 else "weak"
    return {"says": f"A customer is worth about ${ltv:,.0f} over {life:.0f} months and costs ${cac:,.0f} to win: LTV to CAC is {ratio:.1f} and payback is {pay:.1f} months ({verdict}).", "monthly_gross_profit_per_customer": round(gm, 2), "expected_lifetime_months": round(life, 1), "ltv": round(ltv, 2), "ltv_to_cac": round(ratio, 2), "payback_months": round(pay, 1), "verdict": verdict,
            "notes": ["Rule of thumb for small subscription businesses: LTV to CAC of 3 or more and payback under 12 to 18 months. Your market may differ.", "This assumes churn stays constant. Check the numbers by acquisition channel."]}


# ------------------------------------------------------------------ revenue-system security (defensive)
CONFLICTS = [({"create_invoice", "edit_invoice"}, {"approve_payment", "approve_refund", "issue_refund"}, "creates charges and also approves money going out"), ({"edit_price", "create_quote"}, {"approve_discount"}, "sets prices and approves their own discounts"),
             ({"create_vendor", "edit_bank_details"}, {"pay_vendor", "approve_payment"}, "can add a payee and also pay them"), ({"issue_refund"}, {"approve_refund"}, "requests and approves the same refund"),
             ({"admin"}, {"approve_payment", "approve_refund", "issue_refund", "pay_vendor"}, "is an administrator and also handles money")]


@tool("revsec", "access", "Access review", "Finds people who hold both halves of a risky money action across billing, CRM and payment tools.",
      [I("grants", "Access: person, system, permission (one per line)", "area", "ana, billing, create_invoice\nana, billing, approve_refund\nben, crm, export_customers\nben, billing, admin\nben, billing, pay_vendor"), I("note", "Permissions seen: create_invoice, edit_invoice, approve_payment, approve_refund, issue_refund, edit_price, create_quote, approve_discount, create_vendor, edit_bank_details, pay_vendor, export_customers, admin", "text", "")])
def access(v):
    perms: dict[str, set] = {}
    n = 0
    for ln in rows(v, "grants", 500):
        c = split(ln)
        if len(c) < 3:
            raise PackError(f"'{ln[:30]}' needs person, system and permission.")
        perms.setdefault(c[0].lower(), set()).add(c[2].lower().replace(" ", "_"))
        n += 1
    if not n:
        raise PackError("Add at least one line of access.")
    findings = []
    for person, ps in perms.items():
        for a, b, why in CONFLICTS:
            ha, hb = ps & a, ps & b
            if ha and hb:
                findings.append({"severity": "high", "person": person, "says": f"{person} {why}: has {', '.join(sorted(ha))} and {', '.join(sorted(hb))}. Split these between two people or add a second-person review."})
    exp = [p for p, ps in perms.items() if "export_customers" in ps]
    adm = [p for p, ps in perms.items() if "admin" in ps]
    notes = []
    if exp:
        notes.append(f"{len(exp)} person(s) can export customer lists ({', '.join(exp)}): confirm each needs it and that exports are logged.")
    if len(adm) > 2:
        notes.append(f"{len(adm)} administrators is a lot for a small team. Keep two and give others lower roles.")
    return {"says": f"{len(findings)} conflict(s) among {len(perms)} people.", "findings": findings, "notes": notes, "caution": "Only as complete as the access you listed. Re-run after each quarterly review and keep the report as evidence."}


@tool("revsec", "saas", "SaaS inventory and risk", "Lists apps that hold customer or money data and flags missing sign-in protection and overdue reviews.",
      [I("apps", "Apps: name, owner, data (money, customers, none), MFA (yes/no), last review (YYYY-MM-DD) (one per line)", "area", "Stripe, Ana, money, yes, 2026-03-01\nHubSpot, Ben, customers, no, 2025-06-01\nCanva, Ana, none, yes, ")])
def saas(v):
    out, find = [], []
    today = date.today()
    for ln in rows(v, "apps", 200):
        c = split(ln) + [""] * 5
        name, owner, data, mfa, last = c[:5]
        if not name:
            continue
        data, mfa = data.lower(), mfa.lower() in ("yes", "y", "true", "on")
        age = None
        if last:
            try:
                age = (today - date.fromisoformat(last)).days
            except ValueError:
                raise PackError(f"Review date for {name} must look like 2026-03-01.") from None
        score = (3 if data == "money" else 2 if data == "customers" else 0) + (0 if mfa else 2) + (2 if age is None or age > 365 else 0) + (1 if not owner else 0)
        risk = "high" if score >= 5 else "medium" if score >= 3 else "low"
        out.append({"app": name, "owner": owner or "none", "data": data or "unknown", "mfa": "yes" if mfa else "no", "last_review_days_ago": age if age is not None else "never", "risk": risk})
        if data in ("money", "customers") and not mfa:
            find.append({"severity": "high", "says": f"{name} holds {data} data without MFA. Turn it on this week."})
        if age is None or age > 365:
            find.append({"severity": "medium", "says": f"{name} has not been reviewed in over a year. Check who still has access."})
        if not owner:
            find.append({"severity": "medium", "says": f"{name} has no owner."})
    if not out:
        raise PackError("Add at least one app.")
    out.sort(key=lambda r: {"high": 0, "medium": 1, "low": 2}[r["risk"]])
    return {"says": f"{sum(r['risk'] == 'high' for r in out)} of {len(out)} apps are high risk.", "apps": out, "findings": find}


@tool("revsec", "pci", "Card-data scope helper", "A rough guide to how much card-payment security paperwork applies to you.",
      [I("how", "How do customers pay?", "select", "hosted", [{"id": "hosted", "label": "Redirected to my payment provider's page"}, {"id": "embedded", "label": "Provider's fields embedded in my page"}, {"id": "own", "label": "My own form sends card data to my server"}, {"id": "terminal", "label": "In person on a provider's terminal"}]), I("store", "Do you store card numbers anywhere (spreadsheets, email, notes)?", "select", "no", [{"id": "no", "label": "No"}, {"id": "yes", "label": "Yes, or I am not sure"}])])
def pci(v):
    how, st = txt(v, "how", 20), txt(v, "store", 5)
    lvl = {"hosted": "likely the simplest self-assessment (SAQ A)", "embedded": "likely a short self-assessment that includes your page's security (SAQ A or A-EP, depending on the integration)", "terminal": "likely a simple terminal-based self-assessment", "own": "likely the longest assessment (SAQ D): card data touches your own systems"}.get(how)
    if not lvl:
        raise PackError("Choose how customers pay.")
    notes = ["Your payment provider or acquirer tells you the exact form and any deadlines. Ask them."]
    if st == "yes":
        notes.insert(0, "Stored card numbers move you to a much heavier scope. Delete them now (including from email and spreadsheets) and use the provider's tokens instead.")
    if how == "own":
        notes.insert(0, "Switching to hosted checkout is usually the cheapest way to shrink your scope.")
    return {"says": f"Based on your answers: {lvl}.", "notes": notes, "caution": "A rough guide only, not an assessment or legal advice. Your payment provider decides which requirements apply."}


# ------------------------------------------------------------------ UI / UX
def _hex(s: str) -> tuple[int, int, int]:
    s = s.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", s):
        raise PackError("Colors must be hex like #1a73e8.")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def _lum(rgb) -> float:
    f = lambda c: (c / 255 / 12.92) if c / 255 <= 0.03928 else (((c / 255) + 0.055) / 1.055) ** 2.4  # noqa: E731
    r, g_, b = (f(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g_ + 0.0722 * b


def _ratio(a, b) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


@tool("ux", "contrast", "Contrast checker", "Measures text-to-background contrast against the WCAG accessibility thresholds.", [I("fg", "Text color (hex)", "text", "#767676"), I("bg", "Background color (hex)", "text", "#ffffff")])
def contrast(v):
    f, b = _hex(txt(v, "fg", 9, True)), _hex(txt(v, "bg", 9, True))
    r = _ratio(f, b)
    return {"says": f"Contrast ratio {r:.2f} to 1. Body text: {'passes AA' if r >= 4.5 else 'fails AA'}. Large text: {'passes' if r >= 3 else 'fails'}.", "ratio": round(r, 2), "normal_text_aa": r >= 4.5, "normal_text_aaa": r >= 7, "large_text_aa": r >= 3, "large_text_aaa": r >= 4.5, "interface_parts_aa": r >= 3,
            "notes": ["Large text means 24 px, or 19 px bold, and up. Thresholds come from WCAG 2.x.", "Passing the number does not guarantee readability: check thin fonts and busy backgrounds by eye."]}


@tool("ux", "typescale", "Type scale", "A consistent set of font sizes from a base size and a ratio.", [I("base", "Base size (px)", "number", "16"), I("ratio", "Ratio", "select", "1.25", [{"id": "1.125", "label": "1.125 (subtle)"}, {"id": "1.2", "label": "1.2"}, {"id": "1.25", "label": "1.25 (balanced)"}, {"id": "1.333", "label": "1.333"}, {"id": "1.5", "label": "1.5 (dramatic)"}]), I("up", "Steps larger", "number", "5"), I("down", "Steps smaller", "number", "2")])
def typescale(v):
    b, r, up, dn = num(v, "base", 8, 40), num(v, "ratio", 1.05, 2), int(num(v, "up", 0, 10)), int(num(v, "down", 0, 4))
    steps = [{"step": "base" if k == 0 else (f"+{k}" if k > 0 else str(k)), "px": round(b * r ** k, 1), "rem": round(b * r ** k / 16, 3), "line_height_px": round(b * r ** k * (1.5 if k <= 0 else 1.3 if k < 3 else 1.15))} for k in range(up, -dn - 1, -1)]
    return {"says": f"{len(steps)} sizes from {steps[-1]['px']} px to {steps[0]['px']} px.", "scale": steps, "notes": ["Use only these sizes. Body text between 16 and 18 px reads well on most screens.", "Larger sizes need tighter line height, shown above."]}


@tool("ux", "palette", "Palette builder", "Lighter and darker steps from one color, each checked for contrast.", [I("base", "Brand color (hex)", "text", "#1a73e8")])
def palette(v):
    r, g_, b = _hex(txt(v, "base", 9, True))
    h, l, s = colorsys.rgb_to_hls(r / 255, g_ / 255, b / 255)
    out = []
    for step, light in zip((50, 100, 200, 300, 400, 500, 600, 700, 800, 900), (0.96, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.12)):
        rr, gg, bb = (round(c * 255) for c in colorsys.hls_to_rgb(h, light, s))
        rgb = (rr, gg, bb)
        out.append({"step": step, "hex": f"#{rr:02x}{gg:02x}{bb:02x}", "contrast_with_white": round(_ratio(rgb, (255, 255, 255)), 2), "contrast_with_black": round(_ratio(rgb, (0, 0, 0)), 2)})
    return {"says": "Ten steps built from your color.", "steps": out, "notes": ["Use a step as text on white only when 'contrast with white' is 4.5 or more.", "Steps are mathematical, so check them by eye: some hues need hand tuning."]}


@tool("ux", "usability", "Usability test plan", "A facilitator script and scoring sheet for a five-person test.", [I("product", "What is being tested"), I("tasks", "Tasks (one per line, phrased as a goal)", "area", "Find the price of the large size\nBook an appointment for Friday"), I("people", "Number of participants", "number", "5")])
def usability(v):
    pr, tasks, n = txt(v, "product", 100, True), rows(v, "tasks", 8), int(num(v, "people", 1, 20))
    if not tasks:
        raise PackError("Add at least one task.")
    notes = []
    if n < 5:
        notes.append("Fewer than five participants misses many problems. Aim for five per kind of user.")
    if any(re.search(r"\b(click|tap|press|select)\b", t, re.I) for t in tasks):
        notes.append("A task that says 'click' or 'tap' tells people how. Describe the goal instead.")
    sec = [("Before", ["Tell them you are testing the design, not them.", "Ask them to think aloud.", "Do not help or explain; note where they hesitate."]), ("Tasks", "\n".join(f"{i}. {t}" for i, t in enumerate(tasks, 1))),
           ("Score each task", ["Completed without help: yes, with hints, or no", "Time taken", "Where they hesitated or went the wrong way", "Ease, 1 (hard) to 7 (easy)"]), ("After", ["What was most confusing?", "What would you change first?", "Fix the top problems and test again with fresh people."])]
    return {"says": f"Plan for {n} participants and {len(tasks)} tasks.", "notes": notes, "markdown": md(f"Usability test: {pr}", sec)}
