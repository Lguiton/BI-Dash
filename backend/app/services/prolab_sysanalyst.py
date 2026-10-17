"""Systems analyst depth: stories, diagrams, process lint, UAT, migration, vendor scoring, impact, business case, requirements."""
from __future__ import annotations

import re

from app.services.prolab import ProError, lab, lines, num, r, ref, tool, txt

T = "sysanalyst"
lab(T, "Systems analysis depth: requirements, diagrams, process, testing, migration, vendors, impact and business case")


def stories(a):
    rows = lines(a, "needs", "the needs")
    out = []
    for p in rows:
        if len(p) < 3:
            raise ProError("Each line needs: role, want, so that (reason).")
        role, want, why = p[0], p[1], ",".join(p[2:])
        out.append({"story": f"As a {role}, I want to {want}, so that {why}.", "acceptance_criteria": [f"Given a signed-in {role}, when they {want}, then the result is shown and saved.", f"Given invalid or missing input, when they try to {want}, then a clear message says what to fix and nothing is saved.", f"Given someone without permission, when they try to {want}, then access is refused and logged."], "questions": ["How often, and how many items at once?", "What happens if it fails half way?", "Who else needs to see or approve this?"]})
    return {"stories": out, "tips": ["INVEST: Independent, Negotiable, Valuable, Estimable, Small, Testable.", "If you cannot write a test for it, it is not a requirement yet."]}


tool(T, "user_stories", "User stories and acceptance criteria", "Turn needs into stories with testable criteria.", [("needs", "Lines of: role, want, reason", "office manager,export last month's invoices,I can send them to the accountant", "area")], stories)


def uml(a):
    kind = txt(a, "kind").lower()
    rows = lines(a, "items", "the items")
    if kind == "sequence":
        out = ["sequenceDiagram"]
        for p in rows:
            if len(p) < 3:
                raise ProError("Sequence lines: from, to, message.")
            out.append(f"    {p[0]}->>{p[1]}: {p[2]}")
    elif kind == "class":
        out = ["classDiagram"]
        for p in rows:
            if len(p) == 3 and p[1] in ("<|--", "*--", "o--", "-->", "..>"):
                out.append(f"    {p[0]} {p[1]} {p[2]}")
            else:
                out.append(f"    class {p[0]} {{")
                out += [f"        {x}" for x in p[1:]]
                out.append("    }")
    elif kind == "usecase":
        out = ["flowchart LR"]
        for p in rows:
            if len(p) < 2:
                raise ProError("Use case lines: actor, use case.")
            a_id, u_id = re.sub(r"\W", "_", p[0]), re.sub(r"\W", "_", p[1])
            out.append(f"    {a_id}([{p[0]}]) --> {u_id}({p[1]})")
    elif kind == "activity":
        out = ["flowchart TD"]
        for i, p in enumerate(rows):
            nid = f"s{i}"
            out.append(f"    {nid}[{p[0]}]" if not p[0].endswith("?") else f"    {nid}{{{p[0]}}}")
            if i:
                out.append(f"    s{i - 1} --> {nid}")
    else:
        raise ProError("Kind must be sequence, class, usecase or activity.")
    return {"mermaid": "\n".join(out), "how": "Paste into any Mermaid viewer (the Whiteboard and many editors render it).", "tips": ["Sequence shows who talks to whom in order; class shows structure; use case shows who does what; activity shows the flow.", "One diagram, one question. Split big ones."]}


tool(T, "diagram_gen", "Diagram generator (Mermaid)", "Sequence, class, use case or activity diagram text.", [("kind", "sequence, class, usecase or activity", "sequence"), ("items", "Lines (sequence: from, to, message)", "Customer,Shop,Place order\nShop,Payment,Charge card\nPayment,Shop,Approved\nShop,Customer,Confirmation", "area")], uml)


def bpmn(a):
    rows = lines(a, "steps", "the steps")
    out, names = [], [p[0] for p in rows]
    if len(set(x.lower() for x in names)) < len(names):
        out.append("Two steps have the same name: names must be unique.")
    for i, p in enumerate(rows):
        n = p[0]
        owner = p[1] if len(p) > 1 else ""
        if not owner:
            out.append(f"\"{n}\": no owner (who does this step?).")
        if not re.match(r"^[A-Za-z]+\b", n) or len(n.split()) < 2 and not n.endswith("?"):
            out.append(f"\"{n}\": name steps as verb + noun, like Approve invoice.")
        if n.endswith("?") and (len(p) < 3 or not p[2]):
            out.append(f"\"{n}\": a decision needs its outcomes (for example Yes: Pay / No: Reject).")
    if not any(n.endswith("?") for n in names):
        out.append("No decision points: real processes have exceptions. What happens when it fails or is refused?")
    owners = [p[1] for p in rows if len(p) > 1 and p[1]]
    handoffs = sum(1 for x, y in zip(owners, owners[1:]) if x != y)
    return {"steps": len(rows), "handoffs": handoffs, "findings": out or ["No structure problems found."], "tips": ["Each handoff is a place for delay and error: count them and cut where you can.", "Mark the start and the end states.", "Record time and cost per step to see where to improve."]}


tool(T, "process_lint", "Process step lint", "Check a process for owners, decisions and handoffs.", [("steps", "Lines of: step, owner, outcomes", "Receive invoice,Clerk\nCheck against order?,Clerk,Yes: Approve / No: Query supplier\nApprove payment,Manager\nPay supplier,Accountant", "area")], bpmn)


def uat(a):
    feat = txt(a, "feature")
    rows = lines(a, "rules", "the rules")
    cases, n = [], 1
    for p in rows:
        rule = p[0]
        cases.append({"id": f"UAT-{n:02d}", "type": "happy path", "step": f"Use {feat} so that: {rule}", "expected": "Works as the rule says; the result is correct and saved."})
        n += 1
        cases.append({"id": f"UAT-{n:02d}", "type": "invalid input", "step": f"Break the rule: {rule} (blank, wrong format, too long, negative)", "expected": "A clear message; nothing wrong is saved."})
        n += 1
    cases.append({"id": f"UAT-{n:02d}", "type": "permission", "step": f"Try {feat} as a user who should not have access", "expected": "Refused."})
    cases.append({"id": f"UAT-{n + 1:02d}", "type": "recovery", "step": f"Interrupt {feat} halfway (close the browser, lose the connection) and return", "expected": "No half-saved data; user can retry safely."})
    return {"cases": cases, "count": len(cases), "sign_off": "Record tester, date, pass or fail, and defects found. The business owner signs when all high-priority cases pass.", "tips": ["Use real-looking data, not just test1.", "Let a real user run it with you watching but silent.", "Keep a defect list with severity: block go-live, fix soon, nice to have."]}


tool(T, "uat_cases", "UAT test cases", "Acceptance test cases from business rules.", [("feature", "Feature", "month-end invoice export"), ("rules", "Lines of business rules", "Only paid invoices appear\nTotals match the ledger\nDates use the company calendar", "area")], uat)


def mapping(a):
    rows = lines(a, "mapping", "the mapping")
    out, seen = [], {}
    for p in rows:
        if len(p) < 3:
            raise ProError("Each line needs: source field, target field, rule.")
        src, tgt, rule = p[0], p[1], ",".join(p[2:])
        if tgt in seen:
            out.append(f"Target {tgt} is filled by both {seen[tgt]} and {src}: decide which wins or combine.")
        seen[tgt] = src
        if not tgt or tgt == "-":
            out.append(f"{src}: no target. Drop on purpose and record why.")
        if not rule or rule.lower() in ("", "same", "copy"):
            if re.search(r"date|time|amount|price|phone|name", src, re.I):
                out.append(f"{src} to {tgt}: copied as is. Check formats (date style, currency, decimal sign, phone format, name case).")
    return {"fields": len(rows), "findings": out or ["No mapping problems found."],
            "cutover_checklist": ["Freeze or note the last change time in the old system.", "Back up both systems and test the restore.", "Run a trial migration and compare row counts and totals per table.", "Spot-check 20 real records by eye.", "Agree a go/no-go point with the business and a rollback plan.", "Migrate, then reconcile again; keep the old system read-only for a set time.", "Update links, logins and integrations; tell users the cutover time."]}


tool(T, "migration_map", "Data migration mapping check", "Find clashes and gaps, plus a cutover checklist.", [("mapping", "Lines of: source field, target field, rule", "cust_name,customer.name,trim and title case\ncust_phone,customer.phone,same\nbalance,account.balance,convert cents to dollars\nnotes,-,drop", "area")], mapping)


def vendor(a):
    crit = lines(a, "criteria", "the criteria")
    ws = {p[0]: float(p[1]) for p in crit}
    tw = sum(ws.values())
    if tw <= 0:
        raise ProError("Weights must add up to more than zero.")
    rows = lines(a, "scores", "the scores")
    out = []
    for p in rows:
        if len(p) != len(ws) + 1:
            raise ProError(f"{p[0]}: give {len(ws)} scores in the same order as the criteria.")
        sc = sum(float(x) * w for x, w in zip(p[1:], ws.values())) / tw
        out.append({"option": p[0], "weighted_score": r(sc, 2)})
    out.sort(key=lambda x: -x["weighted_score"])
    gap = out[0]["weighted_score"] - out[1]["weighted_score"] if len(out) > 1 else None
    return {"ranking": out, "gap_between_first_two": r(gap, 2) if gap is not None else None, "verdict": "Too close to call on score alone: test both with your real data." if gap is not None and gap < 0.3 else "A clear leader on these weights.", "tips": ["Set the weights before looking at the options.", "Try different weights: if the winner flips, the choice depends on what you value.", "Score 1 to 5. Add must-have criteria as pass or fail first."]}


tool(T, "vendor_score", "Vendor weighted scoring", "Rank options by weighted criteria.", [("criteria", "Lines of: criterion, weight", "Cost,5\nFit to needs,5\nSupport,3\nSecurity,4", "area"), ("scores", "Lines of: option, scores (same order, 1-5)", "Vendor A,4,3,5,4\nVendor B,3,5,3,5\nVendor C,5,2,2,3", "area")], vendor)


def impact(a):
    rows = lines(a, "deps", "the dependencies")
    users: dict[str, list[str]] = {}
    for p in rows:
        if len(p) < 2:
            raise ProError("Each line needs: component, depends on.")
        users.setdefault(p[1], []).append(p[0])
    change = txt(a, "change")
    seen, queue, depth = {}, [(change, 0)], {}
    while queue:
        cur, d = queue.pop(0)
        for u in users.get(cur, []):
            if u not in seen:
                seen[u] = cur
                depth[u] = d + 1
                queue.append((u, d + 1))
    return {"changing": change, "directly_affected": sorted(u for u, dd in depth.items() if dd == 1), "indirectly_affected": sorted(u for u, dd in depth.items() if dd > 1), "total_affected": len(seen),
            "test_first": sorted(seen, key=lambda u: depth[u])[:5], "tips": ["Retest everything affected, not only what you changed.", "Tell the owners of each affected system before the change.", "Components with many dependents are the riskiest to change."]}


tool(T, "change_impact", "Change impact analysis", "What else is affected if this changes?", [("change", "Component to change", "Customer database"), ("deps", "Lines of: component, depends on", "Billing app,Customer database\nWebsite,Customer database\nReports,Billing app\nEmail tool,Website", "area")], impact)


def bcase(a):
    cost, benefit, yrs, rate, ann_cost = num(a, "upfront_cost", lo=0), num(a, "annual_benefit", lo=0), int(num(a, "years", lo=1, hi=30)), num(a, "discount_pct", lo=0, hi=100) / 100, num(a, "annual_running_cost", lo=0)
    net = benefit - ann_cost
    npv = -cost + sum(net / (1 + rate) ** t for t in range(1, yrs + 1))
    cum, payback = -cost, None
    for t in range(1, yrs + 1):
        if cum + net >= 0 and payback is None and net > 0:
            payback = t - 1 + (-cum) / net
        cum += net
    return {"annual_net_benefit": r(net, 2), "npv": r(npv, 2), "payback_years": r(payback, 2) if payback is not None else "not within the period", "roi_pct": r(100 * (net * yrs - cost) / cost, 1) if cost else None,
            "verdict": "Positive value at this discount rate." if npv > 0 else "Does not pay back at this discount rate: check the benefits or look at non-money reasons.",
            "tips": ["Count benefits you can measure (hours saved x cost, errors avoided), not hopes.", "Test the case with benefits 30% lower.", "Include training, support and the time of your own people in the cost."]}


tool(T, "business_case", "Business case (NPV and payback)", "Is the project worth doing?", [("upfront_cost", "Upfront cost", 12000), ("annual_benefit", "Annual benefit", 9000), ("annual_running_cost", "Annual running cost", 1500), ("years", "Years", 5), ("discount_pct", "Discount rate (%)", 8)], bcase)


def reqs(a):
    cls = txt(a, "data_class").lower()
    m = {"public": ["Integrity controls so it is not altered.", "Availability target."],
         "internal": ["Sign-in required; role-based access.", "Encrypted in transit (TLS).", "Backups and tested restore."],
         "personal": ["Lawful reason and consent or notice (privacy law such as CCPA or GDPR where they apply).", "Encrypt in transit and at rest; limit who can see it.", "Audit log of who viewed or changed it.", "Retention period and a way to delete on request.", "Breach response steps and who to tell."],
         "payment": ["Do not store card numbers yourself: use a PCI-compliant processor and tokens.", "Encrypt everything, strong access control, multi-factor for admins.", "Logging and regular review.", "Quarterly scans and an annual PCI self-assessment as your level requires."],
         "health": ["HIPAA may apply: minimum necessary access, business associate agreements, audit logs, encryption.", "Strict role-based access and breach notification procedure.", "Check with a qualified compliance professional."]}.get(cls)
    if not m:
        raise ProError("Data class must be public, internal, personal, payment or health.")
    return {"data_class": cls, "requirements": m, "also": ["Write each as a testable statement with an owner.", "Ask: who may see it, who may change it, how long we keep it, what if it leaks.", "General guidance only: confirm legal duties for your place and industry."]}


tool(T, "data_requirements", "Security and privacy requirements", "Starting requirements by type of data.", [("data_class", "public, internal, personal, payment or health", "personal")], reqs)


def integ(a):
    real = txt(a, "timing").lower()
    vol, coupling = txt(a, "volume").lower(), txt(a, "coupling").lower()
    if real not in ("immediate", "minutes", "daily"):
        raise ProError("Timing must be immediate, minutes or daily.")
    if vol not in ("low", "high"):
        raise ProError("Volume must be low or high.")
    if coupling not in ("tight", "loose"):
        raise ProError("Coupling must be tight or loose.")
    if real == "immediate" and coupling == "tight":
        p, why = "Synchronous API call (REST)", "The caller needs the answer now. Add timeouts, retries and a fallback."
    elif real == "immediate":
        p, why = "Events with a message broker or webhook", "Systems react as things happen without knowing each other."
    elif real == "minutes":
        p, why = "Queue or change-data polling", "Near real time without keeping a call open; retries are easy."
    elif vol == "high":
        p, why = "Batch file or bulk load (ETL)", "Move big volumes cheaply on a schedule; validate and reconcile counts."
    else:
        p, why = "Scheduled export and import (CSV or API pull)", "Simple and cheap; fine for low volume."
    return {"pattern": p, "why": why, "always": ["Make it safe to run twice (idempotent).", "Log every message or file with an id for tracing.", "Decide what happens when the other side is down.", "Agree the data format and version in writing."]}


tool(T, "integration_pattern", "Integration pattern chooser", "Pick how two systems should talk.", [("timing", "immediate, minutes or daily", "daily"), ("volume", "low or high", "high"), ("coupling", "tight or loose", "loose")], integ)

ref(T, "togaf", "Enterprise architecture (TOGAF-lite)", [
    {"title": "Four layers to describe", "head": ["Layer", "Question", "Example"], "rows": [["Business", "What do we do and who does it?", "Order to cash process"], ["Data", "What information matters and where is it kept?", "Customer, order, invoice"], ["Application", "Which systems support it?", "Shop site, accounting package"], ["Technology", "What do they run on?", "Cloud hosting, laptops, network"]]},
    {"title": "Use it simply", "items": ["Draw today's picture (as-is) and the target (to-be).", "List the gaps and order them by value and risk into a roadmap.", "Set a few principles (for example buy before build, one source of truth per fact).", "Keep it short enough that people read it."]}])
ref(T, "elicit", "Requirements elicitation", [
    {"title": "Techniques", "items": ["Interviews: open questions, ask for a recent real example, ask what goes wrong.", "Observation: watch the real work, not the described work.", "Workshops: get decision makers and users together to settle conflicts.", "Document review: forms, reports, spreadsheets people really use.", "Prototype: show a rough screen early and watch reactions."]},
    {"title": "Good requirements", "items": ["Clear, testable, one thing each, traceable to a business need.", "Separate needs (what) from solutions (how).", "Write down assumptions, constraints and what is out of scope.", "Get a named person to approve; track changes."]}])
