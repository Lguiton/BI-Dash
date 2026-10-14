"""AI software vendor scorecard.

From a vendor's 25-question buying checklist for small businesses. The original adds up "yes" answers with equal weight. This version
keeps those 25 questions, adds 7 the checklist leaves out (marked extra), lets you weight them, treats "don't know yet" separately from
"no", and applies must-pass gates, because 20 yeses can hide a failed security section. Weights, gates and bands are my own rules of thumb.
"""
from __future__ import annotations


class VendorError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


# (id, section, question, weight 1-3, gate, extra)
Q = [
    ("n1", "Needs", "Have you mapped the specific repetitive tasks you want AI to automate?", 2, False, False),
    ("n2", "Needs", "Do you know the time and cost savings those tasks could give (hours a week x hourly rate)?", 2, False, False),
    ("d1", "Documents", "Does it capture and organise information from standard documents (forms, intake sheets)?", 2, False, False),
    ("d2", "Documents", "Does it generate routine documents (invoices, contracts, proposals) without copy and paste?", 2, False, False),
    ("d3", "Documents", "Does it offer templates with custom fields that update quickly per client?", 1, False, False),
    ("w1", "Workflow", "Does it trigger reminders, tasks, status updates or emails from specific events?", 2, False, False),
    ("w2", "Workflow", "Is it compatible with the tools you already use, with pre-built integrations?", 3, False, False),
    ("c1", "Communication", "Can the AI draft or answer frequent questions and standard requests?", 1, False, False),
    ("c2", "Communication", "Does it include email templates that auto-fill client details?", 1, False, False),
    ("m1", "Fit", "Did the vendor run a live demo on your real examples and documents?", 3, False, False),
    ("m2", "Fit", "Does the vendor give case studies or references from businesses like yours?", 2, False, False),
    ("m3", "Fit", "Are the AI outputs in a format your team can use right away?", 2, False, False),
    ("m4", "Fit", "Is there an admin panel to customise the automated tasks?", 1, False, False),
    ("m5", "Fit", "Can the workflows be adapted easily when your process changes?", 2, False, False),
    ("m6", "Fit", "Is it flexible enough for your industry and region-specific compliance?", 2, False, False),
    ("s1", "Security", "Is data encrypted at rest and in transit?", 3, True, False),
    ("s2", "Security", "Does it meet the regulations that apply to you (for example GDPR, HIPAA, SOC 2 report)?", 3, True, False),
    ("s3", "Security", "Is it clear whether the vendor uses your data to train its models?", 3, True, False),
    ("s4", "Security", "Can you opt in or out of that use?", 2, False, False),
    ("s5", "Security", "Does the vendor explain how it checks AI outputs for bias?", 1, False, False),
    ("i1", "Rollout", "Does it integrate with your current systems without custom development?", 2, False, False),
    ("i2", "Rollout", "Does the vendor train or onboard staff for your industry?", 1, False, False),
    ("i3", "Rollout", "Is support responsive, with a proven track record?", 2, False, False),
    ("i4", "Rollout", "Is there a clear plan to migrate your existing data with little downtime?", 2, False, False),
    ("i5", "Rollout", "Is it clear how AI features change pricing (usage fees, API calls, tiers)?", 2, False, False),
    ("x1", "Extra", "Can you export all your data in a usable format if you leave (exit and portability)?", 3, True, True),
    ("x2", "Extra", "Is there a written uptime or support commitment, and what happens if it is missed?", 2, False, True),
    ("x3", "Extra", "Can you see a log of what the AI did, and who approved it?", 2, False, True),
    ("x4", "Extra", "Can a person review or override AI output before it reaches a client?", 3, True, True),
    ("x5", "Extra", "Did you test accuracy on a sample of your own cases and count the errors?", 3, False, True),
    ("x6", "Extra", "Will the vendor tell you promptly about a breach, and does it list who else handles your data?", 2, False, True),
    ("x7", "Extra", "Do you know the total yearly cost at your expected volume, including add-ons?", 2, False, True),
]
IDS = {q[0] for q in Q}
BANDS = [(0, 6, "Missing the mark"), (7, 12, "Partial fit"), (13, 18, "Strong candidate"), (19, 25, "Ideal solution")]


def questions() -> list[dict]:
    return [{"id": i, "section": s, "question": t, "weight": w, "gate": g, "extra": x} for i, s, t, w, g, x in Q]


def _clean(answers: dict) -> dict:
    if not isinstance(answers, dict):
        raise VendorError("Send answers as an object of question id to yes, no or unknown.")
    out = {}
    for k, v in answers.items():
        if k not in IDS:
            raise VendorError(f"Unknown question '{k}'.")
        v = str(v).strip().lower()
        if v not in ("yes", "no", "unknown"):
            raise VendorError(f"Answer for {k} must be yes, no or unknown.")
        out[k] = v
    return out


def score(answers: dict, include_extra: bool = True) -> dict:
    a = _clean(answers)
    rows, yes_o, tot_w, got_w = [], 0, 0, 0
    gates, unknown, no = [], [], []
    for i, s, t, w, g, x in Q:
        if x and not include_extra:
            continue
        v = a.get(i, "unknown")
        tot_w += w
        if v == "yes":
            got_w += w
            if not x:
                yes_o += 1
        elif v == "no":
            no.append(t)
        else:
            unknown.append(t)
        if g and v != "yes":
            gates.append({"id": i, "question": t, "answer": v})
        rows.append({"id": i, "section": s, "answer": v, "weight": w, "gate": g})
    pct = round(100 * got_w / tot_w, 1) if tot_w else 0.0
    band = next(b[2] for b in BANDS if b[0] <= yes_o <= b[1])
    secs: dict[str, list] = {}
    for r in rows:
        secs.setdefault(r["section"], []).append(r)
    by = [{"section": k, "yes": sum(1 for r in v if r["answer"] == "yes"), "of": len(v)} for k, v in secs.items()]
    if gates:
        verdict = f"Do not buy yet: {len(gates)} must-pass question(s) are not a confirmed yes."
    elif unknown:
        verdict = f"No gate failed, but {len(unknown)} answer(s) are unknown. Ask the vendor in writing before deciding."
    else:
        verdict = f"Passes every gate. Weighted score {pct}%."
    return {"original_score": yes_o, "original_out_of": 25, "original_band": band, "weighted_pct": pct, "gate_failures": gates,
            "unknown_count": len(unknown), "no_count": len(no), "by_section": by, "verdict": verdict,
            "lesson": "A high total can hide a failed must-pass question. Unknown is not yes: get it in writing."}


def compare(vendors: dict, include_extra: bool = True) -> dict:
    if not isinstance(vendors, dict) or not 2 <= len(vendors) <= 5:
        raise VendorError("Compare 2 to 5 vendors.")
    res = []
    for name, ans in vendors.items():
        r = score(ans, include_extra)
        res.append({"vendor": name, "weighted_pct": r["weighted_pct"], "original_score": r["original_score"], "gate_failures": len(r["gate_failures"]),
                    "unknown": r["unknown_count"], "verdict": r["verdict"]})
    res.sort(key=lambda r: (r["gate_failures"], -r["weighted_pct"]))
    return {"ranking": res, "note": "Ranked by fewest gate failures, then weighted score. A tie on score is not a tie on risk: read the unknowns."}


def _ans(rest_yes: bool, fail: tuple = ()):
    return {i: ("no" if i in fail else "yes" if rest_yes else "unknown") for i, *_ in Q}


SAMPLE = {"vendors": {"Vendor A (full yes except training use)": _ans(True, ("s3", "x5")), "Vendor B (feature rich, security unknown)": {**_ans(True), "s1": "unknown", "s2": "unknown", "s3": "unknown", "x1": "no"}}}
SLIPS = [
    "AI software checklist: all 25 questions count the same. A 'yes' to 'email templates auto-fill' equals a 'yes' to 'data encrypted', so a product can reach the top band while failing all of security. Treat security, data use, exit and human override as must-pass gates.",
    "AI software checklist: the opening says AI needs 'minimal training required', yet a later section asks about staff training and onboarding. Both cannot be assumed; ask what the vendor expects of your staff.",
    "AI software checklist: '47% of employees believe AI will soon account for over 30% of their daily tasks' is a belief survey with no source named, and 'soon' is undefined. It shows opinion, not a rate of adoption.",
    "AI software checklist: two of the 25 questions (mapping your tasks and counting your savings) are about you, not the software, but count towards the 'Software Score'. A prepared buyer scores two points before looking at any product.",
    "AI software checklist: 'GDPR, HIPAA, SOC 2' mixes two laws with an audit report. HIPAA also needs a signed agreement (a business associate agreement) for protected health data, and SOC 2 says what was audited, not that you comply.",
    "AI software checklist: every answer comes from the vendor's say-so. A demo on your real documents and a trial on your own cases test the claim; the checklist asks about a demo but not about measuring accuracy.",
    "AI software checklist: it leaves out exit and data export, uptime commitments, activity logs, human review of AI output, breach notice and total cost. It is also published by a vendor and ends with an ad for its own product.",
]
NOT_BUILT = ["Verifying a vendor's claims (security reports, contracts, references). You enter what you learned; the scorecard cannot check it.",
             "Legal review of data terms and agreements. Have a qualified person read the contract."]


def reference() -> dict:
    return {"questions": questions(), "bands": [{"low": a, "high": b, "name": n} for a, b, n in BANDS], "slips": SLIPS, "not_built": NOT_BUILT}
