"""Project management depth: schedule risk, critical path, RACI, stakeholders, loading, status, pricing, PERT."""
from __future__ import annotations

import math
import random

from app.services.prolab import ProError, lab, lines, num, r, ref, tool, txt

T = "pm"
lab(T, "Project management depth: schedule risk, critical path, RACI, stakeholders, resources, reporting and pricing")


def _pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p / 100 * len(xs)))]


def montecarlo(a):
    rows = lines(a, "tasks", "the tasks")
    seed, n = int(num(a, "seed", lo=0)), int(num(a, "runs", lo=100, hi=20000))
    t = []
    for p in rows:
        if len(p) < 4:
            raise ProError("Each line needs: task, best, likely, worst (in days).")
        lo, ml, hi = float(p[1]), float(p[2]), float(p[3])
        if not lo <= ml <= hi:
            raise ProError(f"{p[0]}: needs best <= likely <= worst.")
        t.append((p[0], lo, ml, hi))
    rnd = random.Random(seed)
    tot = [sum(rnd.triangular(lo, hi, ml) for _, lo, ml, hi in t) for _ in range(n)]
    plan = sum(ml for _, _, ml, _ in t)
    p50, p80, p90 = _pct(tot, 50), _pct(tot, 80), _pct(tot, 90)
    target = a.get("target_days", "").strip()
    out = {"tasks_in_sequence": len(t), "sum_of_likely_days": r(plan, 1), "p50_days": r(p50, 1), "p80_days": r(p80, 1), "p90_days": r(p90, 1), "buffer_for_p80_days": r(p80 - plan, 1)}
    if target:
        out["chance_to_finish_by_target_pct"] = r(100 * sum(1 for x in tot if x <= float(target)) / n, 1)
    out["how"] = "Each task takes a random time between best and worst, most often near likely (triangular). The total is repeated thousands of times. Tasks run in a row; for parallel paths use the critical path tool. The seed makes the result repeatable."
    out["tip"] = "Quote P80 to a client, not the sum of likely values: the plain sum usually has only about a 50% chance."
    return out


tool(T, "schedule_risk", "Schedule risk (Monte Carlo)", "Chance of finishing by a date, with P50, P80 and P90.", [("tasks", "Lines of: task, best, likely, worst (days)", "Design,3,5,9\nBuild,8,12,25\nTest,3,5,12\nLaunch,1,2,5", "area"), ("target_days", "Target total days (optional)", 25), ("runs", "Runs", 5000), ("seed", "Seed", 7)], montecarlo)


def cpm(a):
    rows = lines(a, "tasks", "the tasks")
    d, pred = {}, {}
    for p in rows:
        if len(p) < 2:
            raise ProError("Each line needs: id, days, predecessors separated by spaces (optional).")
        d[p[0]] = float(p[1])
        pred[p[0]] = p[2].split() if len(p) > 2 and p[2] else []
    for k, ps in pred.items():
        for x in ps:
            if x not in d:
                raise ProError(f"{k} depends on {x}, which is not a task.")
    order, seen, temp = [], set(), set()

    def visit(k):
        if k in seen:
            return
        if k in temp:
            raise ProError("The tasks depend on each other in a loop.")
        temp.add(k)
        for x in pred[k]:
            visit(x)
        temp.discard(k)
        seen.add(k)
        order.append(k)
    for k in d:
        visit(k)
    es, ef = {}, {}
    for k in order:
        es[k] = max([ef[x] for x in pred[k]], default=0)
        ef[k] = es[k] + d[k]
    end = max(ef.values())
    succ = {k: [j for j in d if k in pred[j]] for k in d}
    lf, ls = {}, {}
    for k in reversed(order):
        lf[k] = min([ls[x] for x in succ[k]], default=end)
        ls[k] = lf[k] - d[k]
    rows_ = [{"task": k, "start": r(es[k], 1), "finish": r(ef[k], 1), "float_days": r(ls[k] - es[k], 1), "critical": abs(ls[k] - es[k]) < 1e-9} for k in order]
    crit = [x["task"] for x in rows_ if x["critical"]]
    return {"project_days": r(end, 1), "critical_path": " > ".join(crit), "schedule": rows_, "tips": ["Anything on the critical path delays the project one for one.", "Float is how long a task can slip without delaying the end.", "Shorten the project only by shortening the critical path (add people, cut scope, run in parallel); the path can then change."]}


tool(T, "critical_path", "Critical path (CPM)", "Earliest finish, float and critical tasks.", [("tasks", "Lines of: id, days, predecessors (space separated)", "A,3\nB,5,A\nC,2,A\nD,4,B C\nE,1,D", "area")], cpm)


def pert(a):
    o, m, p = num(a, "best", lo=0), num(a, "likely", lo=0), num(a, "worst", lo=0)
    if not o <= m <= p:
        raise ProError("Needs best <= likely <= worst.")
    e = (o + 4 * m + p) / 6
    sd = (p - o) / 6
    return {"expected": r(e, 2), "std_dev": r(sd, 2), "range_68pct": f"{r(e - sd, 1)} to {r(e + sd, 1)}", "range_95pct": f"{r(e - 2 * sd, 1)} to {r(e + 2 * sd, 1)}", "how": "Expected = (best + 4 x likely + worst) / 6. Standard deviation = (worst - best) / 6."}


tool(T, "pert", "PERT estimate", "Three-point estimate.", [("best", "Best case", 4), ("likely", "Most likely", 7), ("worst", "Worst case", 16)], pert)


def raci(a):
    rows = lines(a, "matrix", "the RACI matrix", 2)
    head = rows[0]
    people = head[1:]
    issues = []
    for row in rows[1:]:
        cells = [c.upper() for c in row[1:]]
        if len(cells) != len(people):
            issues.append(f"{row[0]}: has {len(cells)} entries for {len(people)} people.")
            continue
        for c in cells:
            if c not in ("R", "A", "C", "I", "", "-", "AR", "RA"):
                issues.append(f"{row[0]}: \"{c}\" is not R, A, C or I.")
        acc = sum(1 for c in cells if "A" in c)
        res = sum(1 for c in cells if "R" in c)
        if acc == 0:
            issues.append(f"{row[0]}: nobody is Accountable.")
        if acc > 1:
            issues.append(f"{row[0]}: {acc} people are Accountable (exactly one).")
        if res == 0:
            issues.append(f"{row[0]}: nobody is Responsible.")
    load = {p: sum(1 for row in rows[1:] if len(row) == len(head) and "R" in row[1 + i].upper()) for i, p in enumerate(people)}
    heavy = max(load, key=load.get)
    return {"tasks": len(rows) - 1, "issues": issues or ["Every task has one Accountable and at least one Responsible."], "responsible_count": load, "most_loaded": heavy, "key": "R does the work, A answers for it (one only), C is consulted before, I is told after."}


tool(T, "raci_check", "RACI validator", "One accountable owner per task, no gaps.", [("matrix", "First line: Task, then people. Then a row per task with R, A, C or I.", "Task,PM,Dev,Client\nScope,A,C,R\nBuild,A,R,I\nSign-off,R,I,A", "area")], raci)


def stake(a):
    rows = lines(a, "people", "the stakeholders")
    out = []
    for p in rows:
        if len(p) < 3:
            raise ProError("Each line needs: name, power 1-5, interest 1-5.")
        pw, it = float(p[1]), float(p[2])
        q = "Manage closely" if pw >= 3 and it >= 3 else "Keep satisfied" if pw >= 3 else "Keep informed" if it >= 3 else "Monitor"
        out.append({"stakeholder": p[0], "power": pw, "interest": it, "approach": q})
    out.sort(key=lambda x: -(x["power"] * x["interest"]))
    return {"map": out, "tips": ["Manage closely: frequent one-to-one updates and early say in decisions.", "Keep satisfied: short, high-level updates; no surprises.", "Keep informed: regular newsletter or dashboard; ask for feedback.", "Review the map each phase: people move."]}


tool(T, "stakeholder_map", "Stakeholder map", "Power and interest grid with an approach for each.", [("people", "Lines of: name, power 1-5, interest 1-5", "Owner,5,5\nAccountant,4,2\nStaff,2,5\nSupplier,1,1", "area")], stake)


def loading(a):
    cap = num(a, "hours_per_person_per_week", lo=1)
    rows = lines(a, "work", "the work")
    tot, who = {}, {}
    for p in rows:
        if len(p) < 3:
            raise ProError("Each line needs: person, week number, hours.")
        wk = int(float(p[1]))
        tot[(p[0], wk)] = tot.get((p[0], wk), 0) + float(p[2])
        who.setdefault(p[0], set()).add(wk)
    out = [{"person": k[0], "week": k[1], "hours": v, "load_pct": r(100 * v / cap, 0), "status": "OVER" if v > cap else "ok"} for k, v in sorted(tot.items())]
    over = [x for x in out if x["status"] == "OVER"]
    return {"loading": out, "overloaded": len(over), "advice": ["Move work to a lighter week or person.", "Do not plan people at 100%: meetings, email and rework take 15 to 25%.", "Sustained overload cuts quality and raises risk."] if over else ["Nobody is over capacity."]}


tool(T, "resource_load", "Resource loading", "Find overloaded people by week.", [("hours_per_person_per_week", "Capacity (hours per week)", 32), ("work", "Lines of: person, week, hours", "Ana,1,20\nAna,1,18\nBo,1,10\nAna,2,12\nBo,2,30", "area")], loading)


def status(a):
    done, tot, spent, budget, planned_pct = num(a, "percent_complete", lo=0, hi=100), num(a, "total_days", lo=0, strict=True), num(a, "spent", lo=0), num(a, "budget", lo=0, strict=True), num(a, "planned_percent", lo=0, hi=100)
    ev, pv, ac = budget * done / 100, budget * planned_pct / 100, spent
    cpi_ = ev / ac if ac else None
    spi = ev / pv if pv else None
    eac = budget / cpi_ if cpi_ else None
    rag = "GREEN" if (spi or 1) >= 0.95 and (cpi_ or 1) >= 0.95 else "AMBER" if (spi or 1) >= 0.85 and (cpi_ or 1) >= 0.85 else "RED"
    rep = [f"Status: {rag}", f"Progress: {done:g}% complete against {planned_pct:g}% planned.", f"Cost: {spent:,.0f} spent against {ev:,.0f} of value earned (CPI {r(cpi_, 2) if cpi_ else 'n/a'}).", f"Forecast at completion: {eac:,.0f} versus a budget of {budget:,.0f}." if eac else "Forecast: not enough spend to forecast."]
    blk = txt(a, "blockers", required=False)
    rep.append("Blockers and asks: " + (blk if blk else "none"))
    return {"rag": rag, "spi": r(spi, 2) if spi else None, "cpi": r(cpi_, 2) if cpi_ else None, "forecast_at_completion": r(eac, 0) if eac else None, "variance_at_completion": r(budget - eac, 0) if eac else None, "report_text": "\n".join(rep),
            "how": "Earned value = budget x percent complete. SPI = earned / planned (under 1 is behind). CPI = earned / actual cost (under 1 is over budget). Forecast = budget / CPI."}


tool(T, "status_report", "Earned value and status report", "SPI, CPI, forecast and a ready status note.", [("percent_complete", "Percent complete", 40), ("planned_percent", "Planned percent by now", 50), ("budget", "Total budget", 50000), ("spent", "Spent so far", 24000), ("total_days", "Total planned days", 60), ("blockers", "Blockers (optional)", "Waiting on client logins", "area")], status)


def pricing(a):
    hrs, rate, cost_rate, buf, expenses, margin = num(a, "hours", lo=0, strict=True), num(a, "rate", lo=0), num(a, "cost_rate", lo=0), num(a, "contingency_pct", lo=0, hi=200) / 100, num(a, "expenses", lo=0), num(a, "target_margin_pct", lo=0, hi=95) / 100
    h2 = hrs * (1 + buf)
    cost = h2 * cost_rate + expenses
    fixed = (cost / (1 - margin)) if margin < 1 else 0
    tm = h2 * rate + expenses
    return {"planned_hours_with_contingency": r(h2, 1), "your_cost": r(cost, 2), "fixed_price_for_target_margin": r(fixed, 2), "time_and_materials_total": r(tm, 2), "margin_on_t_and_m_pct": r(100 * (tm - cost) / tm, 1) if tm else None,
            "tips": ["Fixed price moves the overrun risk to you: add contingency and write down what is out of scope.", "Time and materials is safer for unclear scope; add a cap or a not-to-exceed estimate.", "Change requests get their own price."]}


tool(T, "project_price", "Price and margin", "Fixed price versus time and materials.", [("hours", "Estimated hours", 40), ("contingency_pct", "Contingency (%)", 20), ("rate", "Hourly rate you charge", 85), ("cost_rate", "Your cost per hour", 40), ("expenses", "Expenses (parts, licences)", 150), ("target_margin_pct", "Target margin (%)", 45)], pricing)

ref(T, "pmbok", "Process groups and the PMP path", [
    {"title": "Five process groups", "head": ["Group", "Purpose", "Typical outputs"], "rows": [["Initiating", "Authorize the project", "Charter, stakeholder register"], ["Planning", "Define scope, schedule, cost, quality, risk", "Scope statement, WBS, schedule, budget, risk register"], ["Executing", "Do the work", "Deliverables, work performance data"], ["Monitoring and controlling", "Track, compare, change", "Status reports, change log, forecasts"], ["Closing", "Finish and learn", "Acceptance, lessons learned, archive"]]},
    {"title": "Certification path (check current rules at pmi.org)", "items": ["CAPM: entry level, no experience needed.", "PMP: needs documented project experience and 35 hours of training; the exam mixes predictive and agile questions.", "Agile options: PMI-ACP, Scrum Master (PSM or CSM).", "Practice with scenario questions: pick the answer that follows the process and talks to people first."]}])
ref(T, "retro", "Retrospectives", [
    {"title": "A simple format (45 minutes)", "items": ["Set the stage: what is the goal and the rule (no blame).", "Gather: what went well, what did not, what puzzled us.", "Group the notes and vote for the top two.", "Decide: one or two concrete actions with an owner and a date.", "Next time start by checking last time's actions."]}])
ref(T, "roadmap", "Roadmapping and prioritisation", [
    {"title": "Methods", "head": ["Method", "Use when", "How"], "rows": [["MoSCoW", "Fixed deadline", "Must, Should, Could, Won't this time"], ["RICE", "Many ideas", "Reach x Impact x Confidence / Effort"], ["Weighted scoring", "Several criteria", "Score each 1-5, multiply by weights"], ["Kano", "Customer delight", "Basic, performance and delighter features"]]},
    {"title": "Roadmap tips", "items": ["Plan Now / Next / Later rather than dates for the far future.", "Show outcomes, not just features.", "Review every quarter and say what was dropped."]}])
ref(T, "agile", "Agile and scaling", [
    {"title": "Basics", "items": ["Scrum: sprint of 1 to 4 weeks, planning, daily stand-up, review, retrospective; roles: product owner, scrum master, team.", "Kanban: visualise work, limit work in progress, improve flow; measure cycle time.", "Estimate by relative size (story points) and use the team's own velocity to forecast.", "Definition of done makes finished mean finished."]},
    {"title": "Scaling", "items": ["Keep teams small and independent; reduce dependencies before adding process.", "Frameworks (SAFe, LeSS, Scrum of Scrums) coordinate several teams; adopt only what a real problem needs."]}])
ref(T, "contracts", "Procurement and contracts", [
    {"title": "Contract types", "head": ["Type", "Who carries cost risk", "Good for"], "rows": [["Fixed price", "Seller", "Clear scope"], ["Time and materials", "Buyer", "Unclear scope, short work"], ["Cost plus", "Buyer", "Research, long uncertain work"], ["Retainer", "Shared", "Ongoing support"]]},
    {"title": "Include", "items": ["Scope and what is not included, deliverables and acceptance criteria.", "Price, payment schedule, expenses, late fees.", "Change process, timeline, assumptions about client duties.", "Ownership of work, confidentiality, liability limits, ending the contract.", "This is general information, not legal advice: have a lawyer review contracts that matter."]}])
ref(T, "change", "Change management", [
    {"title": "Make change stick", "items": ["Explain why in plain words, from someone people trust.", "Involve the people affected early; they know what will break.", "Train just in time and give a place to ask questions.", "Pilot with a small group, fix, then widen.", "Measure adoption (not just go-live) and celebrate visible wins.", "Keep the old way available only as long as needed, with a date to retire it."]}])
