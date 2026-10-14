"""AI implementation planner: is a workflow ready for AI, how much autonomy should the AI get, and what can you honestly claim?

From a one-page guide on moving from an AI demo to a measured result (five readiness dimensions, a seven-stage method, four levels
of human-AI division of labour, three measurement horizons). The scales, thresholds and caps below are my own starting rules of thumb,
chosen so you can practise the reasoning. The guide gives none, and they are not standards.
"""
from __future__ import annotations

import math


class ImplError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


DIMENSIONS = [
    ("value", "Business value", "Does this move a number leadership cares about?", "Unclear or nobody owns the number", "A named number and executive owner", "Process repair is not the issue; get an owner and a target first"),
    ("frequency", "Frequency", "Is there enough volume to measure quickly?", "A few cases a month", "Hundreds of cases a month", "Pick a busier workflow, or pool similar ones"),
    ("stability", "Process stability", "Is the work consistent, not contradictory?", "Everyone does it differently; the SOP is ignored", "One agreed way with known exceptions", "Process repair: agree and write the real workflow before automating"),
    ("measurability", "Measurability", "Can you state current cycle time and error rates?", "No numbers today", "Timed and counted for the last 3 months", "Measure first: time 30 recent cases and count errors"),
    ("risk", "Risk level", "Is the impact of an error contained and correctable?", "An error is costly or cannot be undone", "An error is small and fixed the next day", "Governance: keep a human on every action or choose a safer workflow"),
]
LEVELS = {1: ("Assist", "AI suggests; the human acts."), 2: ("Supervised", "AI acts; the human reviews every result before it takes effect."),
          3: ("Bounded", "AI acts within limits; humans audit a sample."), 4: ("Broad", "AI handles the case end to end; humans handle exceptions.")}


def questions() -> dict:
    return {"dimensions": [{"id": k, "name": n, "question": q, "score_1": lo, "score_5": hi} for k, n, q, lo, hi, _ in DIMENSIONS], "scale": "Score each from 1 (worst) to 5 (best)."}


def readiness(scores: dict) -> dict:
    if not isinstance(scores, dict):
        raise ImplError("Send the scores as an object.")
    ids = {d[0] for d in DIMENSIONS}
    bad = [k for k in scores if k not in ids]
    if bad:
        raise ImplError(f"Unknown dimension '{bad[0]}'.")
    missing = [d[1] for d in DIMENSIONS if d[0] not in scores]
    if missing:
        raise ImplError(f"Score every dimension; missing {', '.join(missing)}.")
    rows = []
    for k, name, _, _, _, fix in DIMENSIONS:
        v = scores[k]
        if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 5:
            raise ImplError(f"'{name}' must be a whole number from 1 to 5.")
        rows.append({"dimension": name, "score": v, "diagnosis": "ready" if v >= 4 else "needs work" if v == 3 else "blocker", "work_needed": "" if v >= 4 else fix})
    total = sum(r["score"] for r in rows)
    blockers = [r for r in rows if r["score"] <= 2]
    if blockers and any(r["dimension"] in ("Risk level", "Process stability") for r in blockers):
        verdict = "Not yet. Repair first."
    elif blockers:
        verdict = "Not yet: fix the blockers, then re-score."
    elif total >= 20:
        verdict = "A good first workflow: start a small, measured trial."
    else:
        verdict = "Close. Do the listed work during discovery, then trial."
    return {"total": total, "out_of": 25, "verdict": verdict, "dimensions": rows, "do_first": [r["work_needed"] for r in sorted(rows, key=lambda r: r["score"]) if r["work_needed"]][:3],
            "lesson": "A low score is a diagnosis, not a verdict: it tells you which work stands between you and implementation.",
            "limit": "Equal weights and 1 to 5 scoring are this app's choice; the source gives no scale. Add cost to run, privacy and staff readiness before you commit."}


STAGES = [("outcome", "Outcome", "The business result as a sentence with numbers and an executive owner, e.g. cut invoice cycle time from 5 days to 2."),
          ("process", "Process observation", "Watch the real workflow at the desk: screen-shares and recent case logs, not the flowchart."),
          ("exceptions", "Exception mapping", "Separate predictable cases from judgment calls; give every failure state a human owner."),
          ("readiness", "Data and security readiness", "Audit the data and constraints. Test it: could a new employee do the job from these sources?"),
          ("allocation", "Allocation of work", "Agree who does what at each step (autonomy level), in writing, with the owning team."),
          ("trial", "Trial", "Run inside the live workflow with a limited blast radius and written stop conditions."),
          ("expand", "Evaluate and expand", "Scale only on sustained, measured improvement against the baseline; review failures weekly.")]


def checklist(done: dict) -> dict:
    if not isinstance(done, dict):
        raise ImplError("Send the checklist as an object of stage id to true or false.")
    ids = [s[0] for s in STAGES]
    bad = [k for k in done if k not in ids]
    if bad:
        raise ImplError(f"Unknown stage '{bad[0]}'.")
    rows = [{"stage": n, "done": bool(done.get(i)), "what_it_means": d} for i, n, d in STAGES]
    todo = [i for i, _, _ in STAGES if not done.get(i)]
    names = {i: n for i, n, _ in STAGES}
    first_id = todo[0] if todo else None
    first = names[first_id] if first_id else None
    ready = all(done.get(i) for i in ids[:5])
    if ready:
        verdict = "Ready to start the trial." if not done.get("trial") else "Trial done: expand only on sustained, measured improvement."
    elif first_id in ids[:5]:
        verdict = f"Not ready: finish '{first}' before moving on."
    else:
        verdict = "Finish the earlier stages first."
    return {"stages": rows, "done_count": 7 - len(todo), "next_stage": first, "ready_for_trial": ready,
            "stop_conditions_needed": not done.get("trial"), "verdict": verdict,
            "lesson": "Skipping a stage does not save time; the cost shows up in production."}


def _wilson_low(k: int, n: int, z: float = 1.96) -> float:
    if n == 0:
        return 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - m) / d


def autonomy(error_cost: str, reversible: str, regulated: bool, correct: int, reviewed: int, exception_pct: float) -> dict:
    """How much autonomy the evidence supports. Rule of thumb: the cap comes from the cost of a mistake, the level from measured accuracy."""
    if error_cost not in ("low", "medium", "high"):
        raise ImplError("Error cost must be low, medium or high.")
    if reversible not in ("easy", "hard", "irreversible"):
        raise ImplError("Reversible must be easy, hard or irreversible.")
    for nm, v in (("correct", correct), ("reviewed", reviewed)):
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise ImplError(f"{nm.capitalize()} must be a whole number, zero or more.")
    if correct > reviewed:
        raise ImplError("Correct cannot be more than reviewed.")
    if not isinstance(exception_pct, (int, float)) or not 0 <= exception_pct <= 100:
        raise ImplError("Exception share must be 0 to 100.")
    cap, why = 4, []
    if error_cost == "high" or reversible == "irreversible" or regulated:
        cap = 2
        why.append("A mistake is costly, cannot be undone or is regulated, so a human must review before it takes effect (level 2 at most).")
    elif error_cost == "medium" or reversible == "hard":
        cap = 3
        why.append("A mistake has a real cost or is hard to undo, so keep humans auditing (level 3 at most).")
    lb = _wilson_low(correct, reviewed)
    if reviewed < 30:
        earned, ev = 1, "Fewer than 30 reviewed cases is too little evidence: stay at assist."
    elif lb >= 0.98 and reviewed >= 300 and exception_pct <= 10:
        earned, ev = 4, "Lower bound of accuracy is at least 98% on 300+ cases with few exceptions."
    elif lb >= 0.95 and reviewed >= 100:
        earned, ev = 3, "Lower bound of accuracy is at least 95% on 100+ cases."
    elif lb >= 0.85:
        earned, ev = 2, "Lower bound of accuracy is at least 85%: AI can act if a human reviews each result."
    else:
        earned, ev = 1, "Accuracy is not yet high enough for the AI to act."
    lvl = min(cap, earned)
    why.append(ev)
    if exception_pct > 10 and lvl >= 4:
        lvl = 3
    nxt = None
    if lvl < cap and lvl < 4:
        nxt = f"To reach level {lvl + 1}: raise the accuracy lower bound or review more cases, then hold it for several weeks of live use with weekly failure review."
    name, desc = LEVELS[lvl]
    return {"level": lvl, "name": name, "description": desc, "capped_by_risk": earned > cap, "accuracy_observed": round(100 * correct / reviewed, 1) if reviewed else None,
            "accuracy_lower_bound": round(100 * lb, 1), "reasons": why, "to_go_up": nxt,
            "reminder": "'The AI decided' is never an acceptable answer: name the human who owns the outcome at every level.",
            "limit": "Thresholds (30/100/300 cases, 85/95/98%) are this app's rules of thumb, not a standard. Real risk decisions need your domain and legal context."}


def exceptions(text: str) -> dict:
    rows = []
    for ln in (text or "").splitlines():
        if not ln.strip() or ln.strip().startswith("#"):
            continue
        p = [x.strip() for x in ln.split("|")]
        if len(p) < 3:
            raise ImplError(f"'{ln.strip()[:50]}' needs: case type | share of cases % | rule-based (yes/no) | human owner | what failure looks like")
        p += [""] * (5 - len(p))
        try:
            share = float(p[1])
        except ValueError:
            raise ImplError(f"'{p[1]}' for {p[0]}: share must be a number.") from None
        if not 0 <= share <= 100:
            raise ImplError(f"Share for {p[0]} must be between 0 and 100.")
        if p[2].lower() not in ("yes", "no"):
            raise ImplError(f"'{p[2]}' for {p[0]}: rule-based must be yes or no.")
        rows.append({"case": p[0], "share": share, "rule_based": p[2].lower() == "yes", "owner": p[3], "failure": p[4]})
    if not rows or len(rows) > 100:
        raise ImplError("Give between 1 and 100 case types.")
    total = sum(r["share"] for r in rows)
    pred = sum(r["share"] for r in rows if r["rule_based"])
    judg = [r for r in rows if not r["rule_based"]]
    issues = []
    if abs(total - 100) > 5:
        issues.append(f"The shares add up to {total:.0f}%, not about 100%. The map is incomplete or double-counted.")
    for r in rows:
        if not r["owner"]:
            issues.append(f"'{r['case']}' has no human owner.")
        if not r["rule_based"] and not r["failure"]:
            issues.append(f"'{r['case']}' is a judgment call with no description of what failure looks like.")
    return {"cases": len(rows), "total_share": round(total, 1), "predictable_share": round(pred, 1), "judgment_share": round(total - pred, 1),
            "judgment_calls": [{"case": r["case"], "share": r["share"], "owner": r["owner"] or "(none)"} for r in sorted(judg, key=lambda r: -r["share"])], "issues": issues,
            "verdict": f"About {pred:.0f}% of cases look predictable; {total - pred:.0f}% need judgment and stay with a human at first.",
            "lesson": "Automate the predictable share first; every exception needs a named person."}


def value_check(baseline: dict, current: dict, adoption_pct: float | None, escalation_pct: float | None, accuracy_pct: float | None,
                tool_cost_per_month: float = 0.0, volume_per_month: float = 0.0) -> dict:
    """What can you claim? The four things people conflate: model works, fits the workflow, people use it, the business metric moved."""
    def num(d, k):
        v = d.get(k) if isinstance(d, dict) else None
        if v in (None, ""):
            return None
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
            raise ImplError(f"'{k}' must be a number, zero or more.")
        return float(v)
    for nm, v in (("Adoption", adoption_pct), ("Escalation", escalation_pct), ("Accuracy", accuracy_pct)):
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 100):
            raise ImplError(f"{nm} must be 0 to 100.")
    for nm, v in (("Tool cost", tool_cost_per_month), ("Volume", volume_per_month)):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
            raise ImplError(f"{nm} must be a number, zero or more.")
    metrics = []
    for k, label, lower_better in (("cycle_hours", "Cycle time (hours)", True), ("error_pct", "Error rate (%)", True), ("cost_per_txn", "Cost per transaction", True)):
        b, c = num(baseline, k), num(current, k)
        if b is None or c is None:
            metrics.append({"metric": label, "baseline": b, "now": c, "change_pct": None, "note": "No baseline recorded: you cannot prove improvement." if b is None else "No current value."})
        else:
            ch = round(100 * (c - b) / b, 1) if b else None
            metrics.append({"metric": label, "baseline": b, "now": c, "change_pct": ch, "better": (c < b) if lower_better else (c > b), "note": ""})
    cb, cc = num(baseline, "cost_per_txn"), num(current, "cost_per_txn")
    money = None
    if cb is not None and cc is not None and volume_per_month:
        gross = (cb - cc) * volume_per_month
        money = {"gross_saving_per_month": round(gross, 2), "tool_cost_per_month": tool_cost_per_month, "net_per_month": round(gross - tool_cost_per_month, 2), "net_per_year": round(12 * (gross - tool_cost_per_month), 2)}
    measured = [m for m in metrics if m["change_pct"] is not None]
    moved = [m for m in measured if m.get("better") and abs(m["change_pct"]) >= 10]
    claims = [("The model can do the task", accuracy_pct is not None, "Needs accuracy on real cases, not a demo."),
              ("It fits the workflow", escalation_pct is not None, "Needs the escalation or override rate."),
              ("People use it", adoption_pct is not None and adoption_pct >= 60, "Needs adoption of at least about 60% by the people who own the work (this app's rule of thumb)."),
              ("The business metric improved", bool(moved), "Needs a baseline and a current value that moved by 10% or more.")]
    return {"metrics": metrics, "money": money,
            "what_you_can_claim": [{"claim": c, "supported": ok, "evidence_needed": "" if ok else need} for c, ok, need in claims],
            "verdict": "Business result shown." if claims[3][1] and claims[2][1] else "Not proven: some of the four links are missing evidence.",
            "horizons": {"Weeks 1 to 4": "Is it used? Is it safe? Review weekly.", "Months 1 to 3": "Is the workflow improving against the baseline?", "Months 3 to 12": "What is the return? The final checkpoint."},
            "limit": "Windows and the 60% and 10% thresholds are rules of thumb. One good month is not proof; look for a sustained change."}


SAMPLE = {"readiness": {"value": 4, "frequency": 5, "stability": 2, "measurability": 2, "risk": 4},
          "exceptions": "Standard invoice, PO matches | 62 | yes | AP clerk | wrong amount paid\nPO missing | 14 | no | AP lead | paid without approval\nPartial delivery | 12 | no | | \nNew supplier | 8 | no | Procurement | fraud\nCredit note | 4 | yes | AP clerk | duplicate credit",
          "baseline": {"cycle_hours": 96, "error_pct": 6, "cost_per_txn": 11.0}, "current": {"cycle_hours": 60, "error_pct": 4, "cost_per_txn": 8.0}}
SLIPS = [
    "AI implementation guide: the five readiness dimensions have no scale, weights or pass mark, yet it says 'a low score is a diagnosis'. A score needs an agreed scale. This app uses 1 to 5 with equal weights; that is its own choice.",
    "AI implementation guide: 'Fix the process first, integrate AI second' is stated as a rule. It is a good default, but not absolute: AI is also used to discover how the process really runs (for example by reading case logs), and waiting for a perfect process can delay value. Fix contradictions that block automation; do not wait for perfection.",
    "AI implementation guide: the 'Readiness' stage (data and security) shares a name with the earlier 'Is this workflow ready for AI?' diagnostic, and the diagnostic sits before stage 1 without saying how the two relate. Treat the diagnostic as choosing the workflow and stage 4 as auditing its data.",
    "AI implementation guide: level 3 says humans 'audit samples'. A sample finds common errors, not rare severe ones. How big and how often the sample is, and who is accountable, decides whether level 3 is safe.",
    "AI implementation guide: 'Governance metrics' lists adoption rates, but adoption measures use, not safety. Escalation rate is a safety and fit signal; adoption belongs with the business and change metrics.",
    "AI implementation guide: the measurement windows (weeks 1 to 4, months 1 to 3, months 3 to 12) are given as fact. They are plausible defaults, not findings. A workflow with low volume needs longer to show a change.",
    "AI implementation guide: the opening story and 'skipping stages defers the cost to production' have no data behind them, and the page ends with a sales offer from the publisher. It also omits cost to run, privacy and legal review, staff training, a rollback plan and vendor lock-in.",
]
NOT_BUILT = ["Observing a real workflow (screen-shares, case logs), interviewing staff and getting executive sign-off: people work this app cannot do. The planner organises what you find.",
             "Running or integrating an AI system in a live workflow. The ML and AI tracks teach evaluation, and the AI governance lab covers registry, policy and spend."]


def reference() -> dict:
    return {"stages": [{"id": i, "name": n, "what": d} for i, n, d in STAGES], "levels": [{"level": k, "name": v[0], "what": v[1]} for k, v in LEVELS.items()],
            "questions": questions(), "slips": SLIPS, "not_built": NOT_BUILT}
