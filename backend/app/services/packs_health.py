"""Health data field packs: clinical data science, health analytics, health BI, health informatics.

Everything runs on text or numbers you paste. Do not paste real patient information: use de-identified or made-up data."""
from __future__ import annotations

import csv
import io
import json
import math
import re
from datetime import date

from app.services import field_howto as fh
from app.services.fieldpacks import I, PackError, md, num, pack, rows, split, tool, txt

CDS, HAN, HBI, HINF = "Clinical data science", "Health analytics", "Health BI", "Health informatics"
fh.AREAS.extend([CDS, HAN, HBI, HINF])
g = fh._g
PHI = "Do not paste real patient information. Use de-identified or made-up data. Not medical or legal advice."

pack("cds", CDS, "Health data", "Cohort table, diagnostic test accuracy, survival curves and a scan for identifiers in text.", "scientist", "e.g. build table 1, check data for patient identifiers", "clinical data science cohort table 1 sensitivity specificity kaplan meier survival phi identifiers trial ehr")
pack("hana", HAN, "Health data", "Rates with confidence intervals, age adjustment, observed-to-expected ratios and length-of-stay summaries.", "analyst", "e.g. is our readmission rate really higher", "health analytics rate per 1000 age adjusted smr readmission length of stay confidence interval population")
pack("hbi", HBI, "Health data", "Healthcare KPI library and calculator (readmissions, staffing hours, falls, occupancy) and a dashboard spec writer.", "analyst", "e.g. what should a nursing home dashboard show", "health bi kpi dashboard skilled nursing staffing hprd falls pressure injury occupancy denial days in ar census")
pack("hinf", HINF, "Health data", "HL7 message reader, simple FHIR check, medical code format check and interface spec writer.", "sysanalyst", "e.g. read an HL7 message, is this code valid", "health informatics hl7 fhir icd-10 npi cpt loinc interoperability interface ehr integration")

# ------------------------------------------------------------------ guides: clinical data science
g("cds-phi", CDS, "Making sure data has no patient identifiers", "phi identifiers de-identify hipaa safe harbor remove names dates ssn mrn scan deidentification", "Identifiers hide in free text, dates and codes, not only in name columns.", ["List the columns and mark which could identify a person (names, contact details, ID numbers, full dates, small geographies, free text).", "Drop or generalise them: year instead of date, 3-digit zip only where the area is large.", "Scan free-text fields with the identifier scanner.", "Have a second person review the result.", "Keep the key that links back (if any) separate and access-controlled."], "The scanner finds nothing and a reviewer agrees; rules for your setting have been checked.", 60, PHI, "Identifier scanner")
g("cds-table1", CDS, "Building a baseline characteristics table (Table 1)", "table 1 baseline characteristics cohort demographics groups p values summary study", "A good first table shows who is in each group before any outcome.", ["Choose the grouping variable (for example treated vs not).", "Pick the characteristics to show.", "Use the cohort table tool: mean and spread for numbers, counts and percentages for categories.", "Hide or merge very small cells.", "Describe differences; do not use p-values to claim groups are balanced."], "Each variable has a summary for each group, and small cells are handled.", 45, PHI, "Cohort table")
g("cds-diag", CDS, "How good is a screening or diagnostic test?", "sensitivity specificity ppv npv accuracy prevalence diagnostic test two by two confusion likelihood ratio", "Accuracy alone hides the trade-off between missed cases and false alarms.", ["Build the two-by-two table against the best available reference.", "Compute sensitivity, specificity and the predictive values.", "Check how predictive values change with how common the condition is in your setting.", "Look at the confidence intervals: small samples are wide."], "You can say how many cases the test misses and how many false alarms it gives in your setting.", 30, PHI, "Test accuracy")
g("cds-survival", CDS, "Time until an event (survival)", "survival kaplan meier time to event censoring log rank readmission mortality curve", "Some patients have not had the event yet; ignoring them biases results.", ["For each patient record the time and whether the event happened (1) or they were censored (0).", "Run the survival tool by group.", "Read the median and the number still at risk.", "Compare groups with the log-rank test, but look at the curves too.", "Do not claim a cause from an unadjusted comparison."], "Curves are drawn from times and events with censoring, and groups are compared.", 40, PHI, "Survival curves")
g("cds-leak", CDS, "A clinical model looks too good to be true", "leakage model too good future information features clinical prediction validation temporal split overfit", "Data recorded after the outcome sneaks into the inputs.", ["List each input and when it is recorded relative to the prediction time.", "Remove anything recorded after.", "Split by time or by patient, not by row.", "Check performance on a later period.", "Compare with a simple baseline."], "Inputs are all known at prediction time, and a later period holds up.", 90)
g("cds-missing", CDS, "Missing values in clinical data", "missing data imputation not recorded mar mcar lab values absent informative missingness", "A lab not ordered often means something.", ["Count missing values per column and per group.", "Ask why: not measured, not recorded, or not applicable.", "Do not fill blindly; consider an 'unknown' category or a missing flag.", "Test whether results change under different handling."], "Results are stable under reasonable handling of missing data.", 60)

# ------------------------------------------------------------------ guides: health analytics
g("ha-rate", HAN, "Comparing rates between facilities or years", "rate per 1000 confidence interval compare readmission falls small numbers poisson random variation", "Small counts bounce around by chance.", ["Compute the rate with a confidence interval.", "If the intervals overlap heavily, the difference may be chance.", "Use the same definition and denominator for every group.", "Look at the trend over several periods, not one."], "Each rate has a confidence interval and the same definition.", 30, "", "Rate with interval")
g("ha-age", HAN, "Populations differ in age", "age adjusted standardization direct standard population compare older younger rates confounding", "An older population has more events for reasons unrelated to quality.", ["Split counts and populations by age band.", "Pick a standard population (weights).", "Run the age adjustment tool.", "Compare the adjusted rates, not the crude ones."], "Adjusted and crude rates are both reported.", 40, "", "Age adjustment")
g("ha-smr", HAN, "Is the number of events more than expected?", "observed expected ratio smr risk adjusted benchmark mortality readmissions benchmark", "Compare actual events to what you would expect given patient mix.", ["Get the expected count from a risk-adjusted model or reference rates.", "Compute observed over expected with an interval.", "A ratio above 1 with an interval that excludes 1 deserves investigation.", "Check the data first: coding changes can create apparent shifts."], "You have O, E, the ratio and its interval.", 30, "", "Observed vs expected")
g("ha-los", HAN, "Length of stay is hard to summarise", "length of stay los skewed median percentile outliers average days long stays", "A few very long stays pull the average up.", ["Report the median and the 90th percentile, not only the mean.", "Look at the share over a threshold.", "Split by diagnosis group or unit.", "Check dates for errors (negative or huge stays)."], "Summaries include median, spread and the long-stay share.", 20, "", "Length of stay summary")
g("ha-denom", HAN, "Choosing the right denominator", "denominator patient days admissions census person time rate definition per 1000", "Per admission and per patient day tell different stories.", ["Match the denominator to exposure: patient days for falls and infections, discharges for readmissions.", "Write the definition once and reuse it.", "Never mix definitions across reports."], "Every rate lists its denominator.", 15)
g("ha-small", HAN, "Very small numbers and privacy", "small cell suppression privacy counts under 11 rare disclosure aggregate reporting", "Tiny counts can identify people.", ["Check your reporting rules for a minimum cell size.", "Merge categories or periods until cells are large enough.", "Do not give the suppressed value away by subtraction from totals."], "No published cell is below your minimum and cannot be recovered.", 30, "Rules vary by organisation and law.")

# ------------------------------------------------------------------ guides: health BI
g("hbi-start", HBI, "What should a facility dashboard show?", "healthcare dashboard kpi nursing home skilled nursing administrator director of nursing what to show start", "Each reader makes different decisions.", ["Name the reader (administrator, director of nursing, finance, quality).", "List the three decisions they make each week.", "Pick two or three KPIs for each decision.", "Use the dashboard spec writer to record definitions and sources.", "Review with the reader and remove anything unused."], "Every tile maps to a decision someone makes.", 90, "", "Dashboard spec")
g("hbi-hprd", HBI, "Staffing hours per patient day", "staffing hprd hours per patient day nursing skilled nursing staffing ratio agency overtime payroll", "A standard way to see whether staffing keeps up with census.", ["Total the nursing hours worked in the period.", "Total the resident days (census summed per day).", "Divide hours by resident days.", "Split by role and shift, and show agency share.", "Compare against your own targets and any rules that apply to you."], "The number matches payroll and census for a sample week.", 30, "Check the exact definitions your regulators use.", "Healthcare KPI calculator")
g("hbi-quality", HBI, "Falls, pressure injuries and infections per 1000 days", "falls pressure injury infection rate per 1000 resident days quality indicators incident reporting", "Rates per exposure let you compare months with different census.", ["Count incidents with a clear definition.", "Count resident days.", "Compute events per 1000 resident days.", "Look at the trend and at clusters by unit or shift."], "Rates match incident logs.", 30, "", "Healthcare KPI calculator")
g("hbi-def", HBI, "Two reports show different numbers for the same KPI", "kpi definition mismatch source of truth data dictionary reconcile numerator denominator cutoff time", "Different definitions, cut-off times or sources.", ["Write both definitions side by side.", "Check numerator, denominator and date cut-offs.", "Reconcile one day by hand.", "Choose one definition and publish it in a data dictionary."], "One written definition per KPI.", 60)
g("hbi-access", HBI, "Who may see what in healthcare reports", "access roles permissions minimum necessary hipaa dashboard row level security phi reports sharing", "Show only what each role needs.", ["Prefer aggregates over patient-level rows.", "Give patient-level views only to roles that need them.", "Log access.", "Never email patient-level extracts."], "Roles are written down and aggregates are the default.", 45, PHI)
g("hbi-ar", HBI, "Cash and claims: denials and days in accounts receivable", "denial rate days in ar claims revenue cycle billing receivable collection payer", "Slow or denied claims delay cash.", ["Track denial rate by payer and reason.", "Compute days in AR: receivables divided by average daily revenue.", "Work the largest, oldest denials first.", "Fix the top denial reason at the source."], "Denial rate and days in AR trend downward.", 45, "", "Healthcare KPI calculator")

# ------------------------------------------------------------------ guides: health informatics
g("hi-hl7", HINF, "Reading an HL7 message", "hl7 v2 message segments fields msh pid adt oru parse interface integration engine", "HL7 v2 is lines of segments with fields split by |.", ["Each line is a segment: MSH header, PID patient, PV1 visit, OBX result.", "Fields are split by | and parts by ^.", "MSH-9 tells the message type (for example ADT^A01).", "Use the HL7 reader to see the fields.", "Check the acknowledgement your system should return."], "You can say what event the message reports and which fields hold the key data.", 30, PHI, "HL7 reader")
g("hi-fhir", HINF, "Starting with FHIR", "fhir resources patient observation bundle rest api json interoperability smart standard", "FHIR sends health data as small JSON resources.", ["Learn a few resources: Patient, Encounter, Observation, Condition.", "Know the required fields of each.", "Use a public test server with made-up data.", "Check your JSON with the simple FHIR check, then with the official validator."], "Your test resources pass the official validator.", 120, PHI, "FHIR check")
g("hi-codes", HINF, "Medical codes and what they mean", "icd-10 cpt loinc snomed ndc npi codes terminology mapping format validity", "Each coding system has its own format and owner.", ["Know what each code type is for: diagnoses (ICD-10), procedures (CPT), lab tests (LOINC), clinical concepts (SNOMED), drugs (NDC), providers (NPI).", "Check formats with the code checker.", "Remember that a valid format does not mean the code exists or is current.", "Use official code sets for lookups."], "Codes pass format checks and a lookup in the official set.", 30, "", "Code format checker")
g("hi-interface", HINF, "Connecting two systems", "interface specification integration trigger events acknowledgement error handling mapping test plan ehr", "Most interface problems are unwritten assumptions.", ["Write who sends what, when and in which format.", "Map each field to the receiving system.", "Define acknowledgements and what happens on errors.", "Test with made-up data, including bad messages.", "Monitor the queue after go-live."], "A written spec and a test with bad messages passed.", 180, PHI, "Interface spec")
g("hi-privacy", HINF, "Sending health data safely", "hipaa security encryption transmission minimum necessary audit log breach secure messaging", "Protect data in transit, at rest and in access.", ["Encrypt connections.", "Send only the fields needed.", "Keep an audit trail of who accessed what.", "Have a breach response plan and know who to call."], "You can show encryption, access logs and a written plan.", 60, "General information, not legal advice.")
g("hi-dup", HINF, "Duplicate patient records", "duplicate patient master index matching mrn merge identity matching false match", "Two records for one person, or one for two, are both unsafe.", ["Decide matching rules (name, birth date, other identifiers).", "Review borderline matches by a person.", "Merge with an audit trail and an undo.", "Track the duplicate rate."], "Duplicate rate is measured and merges are reversible.", 120)

# ------------------------------------------------------------------ shared maths
def wilson(x: float, n: float, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p = x / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def poisson_ci(k: float, conf: float = 0.95) -> tuple[float, float]:
    from scipy.stats import chi2
    a = 1 - conf
    lo = 0.0 if k == 0 else chi2.ppf(a / 2, 2 * k) / 2
    return lo, chi2.ppf(1 - a / 2, 2 * (k + 1)) / 2


def pct(x: float | None, d: int = 1) -> str:
    return "n/a" if x is None else f"{100 * x:.{d}f}%"


# ------------------------------------------------------------------ tools: clinical data science
PHI_PATTERNS = [("Social security number", r"\b\d{3}-\d{2}-\d{4}\b"), ("Phone number", r"(?<!\d)(?:\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}(?!\d)"), ("Email address", r"\b[\w.+\-]+@[\w\-]+\.[\w.\-]+\b"),
                ("Full date (could be a birth or visit date)", r"\b(?:\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})\b"), ("Medical record number", r"(?i)\b(?:mrn|medical record(?: number)?|chart)\s*(?:#|no\.?|number)?\s*[:#]?\s*\d{4,}\b"),
                ("Street address", r"\b\d{1,5}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Dr|Drive|Ln|Lane|Ct|Court)\b"), ("ZIP code", r"(?<!\d)\d{5}(?:-\d{4})?(?!\d)"), ("IP address", r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
                ("Name after a label", r"(?i)\b(?:patient|name|resident|pt)\s*[:\-]\s*[A-Z][a-z]+(?:,?\s+[A-Z][a-z]+)+")]


@tool("cds", "phi", "Identifier scanner", "Looks for text that may identify a person: IDs, contact details, dates, addresses, names after labels. Shows only counts and line numbers.", [I("text", "Paste de-identification candidates (free text, notes, a column of values)", "area")])
def phi(v):
    t = txt(v, "text", 300000, True)
    hits: dict[str, list[int]] = {}
    for i, ln in enumerate(t.splitlines(), 1):
        for name, pat in PHI_PATTERNS:
            if re.search(pat, ln):
                hits.setdefault(name, []).append(i)
    res = [{"kind": k, "matches": len(x), "first_lines": ", ".join(map(str, x[:8]))} for k, x in hits.items()]
    return {"says": f"{len(res)} kind(s) of possible identifier found." if res else "No known identifier patterns found.", "results": res,
            "notes": ["Names are the hardest to find by pattern. Have a person read a sample of free text.", "The values themselves are not shown here, to avoid copying them around."], "caution": "Not a guarantee of de-identification, which also depends on rare combinations of fields. A clean result does not mean the data is safe to share. " + PHI}


def _num_or_none(x: str):
    try:
        return float(x)
    except ValueError:
        return None


@tool("cds", "table1", "Cohort table", "Summarises each column overall and by group, with a simple test for two groups.", [I("csv", "Paste de-identified CSV with a header row", "area"), I("group", "Group column (optional)", "text", "")])
def table1(v):
    from scipy import stats
    text = txt(v, "csv", 400000, True)
    rd = list(csv.reader(io.StringIO(text)))
    if len(rd) < 3:
        raise PackError("Paste a header row and at least two data rows.")
    head, data = [h.strip() for h in rd[0]][:30], [r for r in rd[1:5001] if any(c.strip() for c in r)]
    gcol = txt(v, "group", 60)
    if gcol and gcol not in head:
        raise PackError(f"Group column '{gcol}' is not in the header: {', '.join(head)}.")
    gi = head.index(gcol) if gcol else None
    groups = sorted({r[gi].strip() for r in data if gi is not None and len(r) > gi and r[gi].strip()}) if gi is not None else []
    if gi is not None and not 2 <= len(groups) <= 6:
        raise PackError("The group column needs between 2 and 6 different values.")
    out = []
    for ci, name in enumerate(head):
        if ci == gi:
            continue
        col = [(r[ci].strip() if len(r) > ci else "", (r[gi].strip() if gi is not None and len(r) > gi else "")) for r in data]
        vals = [c for c, _ in col if c != ""]
        nums = [_num_or_none(c) for c in vals]
        numeric = len(vals) >= 3 and sum(x is not None for x in nums) / len(vals) > 0.9
        row = {"variable": name, "missing": len(col) - len(vals)}
        parts = [("All", [c for c, _ in col])] + ([(gname, [c for c, gg in col if gg == gname]) for gname in groups] if gi is not None else [])
        pval = None
        if numeric:
            for label, cs in parts:
                xs = [x for x in (_num_or_none(c) for c in cs if c != "") if x is not None]
                if xs:
                    q = sorted(xs)
                    m = sum(xs) / len(xs)
                    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) if len(xs) > 1 else 0.0
                    row[label] = f"{m:.1f} ({sd:.1f}); median {q[len(q) // 2]:.1f}; n={len(xs)}"
                else:
                    row[label] = "n=0"
            if len(groups) == 2:
                a, b = ([x for x in (_num_or_none(c) for c, gg in col if gg == gn and c != "") if x is not None] for gn in groups)
                if len(a) > 1 and len(b) > 1:
                    pval = stats.ttest_ind(a, b, equal_var=False).pvalue
            row["type"] = "number: mean (SD)"
        else:
            levels = sorted(set(vals))[:8]
            for label, cs in parts:
                cc = [c for c in cs if c != ""]
                row[label] = "; ".join(f"{lv} {cc.count(lv)} ({100 * cc.count(lv) / len(cc):.0f}%)" for lv in levels) if cc else "n=0"
            if len(groups) == 2 and 2 <= len(levels) <= 8:
                tab = [[sum(1 for c, gg in col if gg == gn and c == lv) for gn in groups] for lv in levels]
                try:
                    pval = stats.fisher_exact(tab).pvalue if len(levels) == 2 and min(map(min, tab)) < 5 else stats.chi2_contingency(tab)[1]
                except ValueError:
                    pval = None
            row["type"] = "category: n (%)"
        row["p_value"] = f"{pval:.3f}" if pval is not None else ""
        out.append(row)
    small = sum(1 for r in out for k, x in r.items() if k not in ("variable", "missing", "type", "p_value") and re.search(r"\b(?:n=|\s)([1-9]|10)\b[ )]", str(x) + " "))
    return {"says": f"{len(out)} variables summarised across {len(data)} rows" + (f" and {len(groups)} groups." if groups else "."), "table": out, "notes": ["P-values for two groups: Welch t-test for numbers, chi-square or Fisher exact for categories. They test difference, not balance, and many columns means some will look 'significant' by chance.", "Small cells (often under 11) usually must be hidden before sharing outside your team." + (" Some cells here look small." if small else "")], "caution": PHI}


@tool("cds", "diag", "Test accuracy", "Sensitivity, specificity, predictive values and likelihood ratios from a two-by-two table, with intervals.", [I("tp", "Test positive, condition present", "number"), I("fp", "Test positive, condition absent", "number"), I("fn", "Test negative, condition present", "number"), I("tn", "Test negative, condition absent", "number"), I("prev", "Prevalence in your setting (%) (optional)", "number", "")])
def diag(v):
    tp, fp, fn, tn = (num(v, k, 0) for k in ("tp", "fp", "fn", "tn"))
    if min(tp + fn, fp + tn, tp + fp, fn + tn) <= 0:
        raise PackError("Each row and column of the table needs at least one case.")
    se, sp = tp / (tp + fn), tn / (tn + fp)
    ppv, npv = tp / (tp + fp), tn / (tn + fn)
    ci = lambda x, n: tuple(round(100 * c, 1) for c in wilson(x, n))  # noqa: E731
    out = {"sensitivity_pct": round(100 * se, 1), "sensitivity_ci": ci(tp, tp + fn), "specificity_pct": round(100 * sp, 1), "specificity_ci": ci(tn, tn + fp), "ppv_pct_in_this_sample": round(100 * ppv, 1), "npv_pct_in_this_sample": round(100 * npv, 1),
           "accuracy_pct": round(100 * (tp + tn) / (tp + fp + fn + tn), 1), "positive_likelihood_ratio": round(se / (1 - sp), 2) if sp < 1 else None, "negative_likelihood_ratio": round((1 - se) / sp, 2) if sp > 0 else None}
    notes = [f"In this sample, the test misses {100 * (1 - se):.0f}% of people with the condition and wrongly flags {100 * (1 - sp):.0f}% of people without it."]
    if v.get("prev") not in (None, ""):
        pr = num(v, "prev", 0.001, 99.999) / 100
        p2 = se * pr / (se * pr + (1 - sp) * (1 - pr))
        n2 = sp * (1 - pr) / (sp * (1 - pr) + (1 - se) * pr)
        out["ppv_pct_at_your_prevalence"], out["npv_pct_at_your_prevalence"] = round(100 * p2, 1), round(100 * n2, 1)
        notes.append(f"At {100 * pr:g}% prevalence, a positive result is right about {100 * p2:.0f}% of the time.")
    notes.append("Predictive values change with how common the condition is; sensitivity and specificity do not (in theory).")
    out["says"] = f"Sensitivity {100 * se:.0f}%, specificity {100 * sp:.0f}%."
    out["notes"] = notes
    out["caution"] = "Only as good as the reference standard used to decide who truly has the condition. " + PHI
    return out


@tool("cds", "km", "Survival curves", "Kaplan-Meier survival by group, with a log-rank test for two groups. Time and whether the event happened (1) or the person was censored (0).", [I("data", "Lines: time, event (1 or 0), group (optional)", "area", "5, 1, A\n8, 0, A\n12, 1, A\n3, 1, B\n6, 1, B\n9, 0, B\n14, 1, B")])
def km(v):
    recs = []
    for i, ln in enumerate(rows(v, "data", 20000), 1):
        c = split(ln)
        if len(c) < 2:
            raise PackError(f"Line {i} needs a time and an event (1 or 0).")
        try:
            t, e = float(c[0]), int(float(c[1]))
        except ValueError:
            raise PackError(f"Line {i}: time and event must be numbers.") from None
        if t < 0 or e not in (0, 1):
            raise PackError(f"Line {i}: time cannot be negative and event must be 0 or 1.")
        recs.append((t, e, c[2] if len(c) > 2 and c[2] else "all"))
    if len(recs) < 4:
        raise PackError("Give at least four people.")
    groups = sorted({r[2] for r in recs})
    if len(groups) > 6:
        raise PackError("At most 6 groups.")
    res, curves = [], {}
    for gname in groups:
        d = sorted(r for r in recs if r[2] == gname)
        times = sorted({t for t, e, _ in d if e == 1})
        s, rows_out, med = 1.0, [], None
        for t in times:
            n_risk = sum(1 for x, _, _ in d if x >= t)
            ev = sum(1 for x, e, _ in d if x == t and e == 1)
            s *= 1 - ev / n_risk
            rows_out.append({"group": gname, "time": t, "at_risk": n_risk, "events": ev, "survival_pct": round(100 * s, 1)})
            if med is None and s <= 0.5:
                med = t
        curves[gname] = rows_out
        res.append({"group": gname, "people": len(d), "events": sum(e for _, e, _ in d), "censored": sum(1 - e for _, e, _ in d), "median_survival": med if med is not None else "not reached"})
    out = {"groups": res, "curve": [r for g_ in groups for r in curves[g_]]}
    notes = ["Censored people count until they leave the study, then stop counting. This assumes censoring is unrelated to risk."]
    if len(groups) == 2:
        from scipy.stats import chi2
        times = sorted({t for t, e, _ in recs if e == 1})
        oa = ea = va = 0.0
        for t in times:
            n = sum(1 for x, _, _ in recs if x >= t)
            n1 = sum(1 for x, _, gg in recs if x >= t and gg == groups[0])
            d = sum(1 for x, e, _ in recs if x == t and e == 1)
            d1 = sum(1 for x, e, gg in recs if x == t and e == 1 and gg == groups[0])
            oa += d1
            ea += d * n1 / n
            if n > 1:
                va += d * (n1 / n) * (1 - n1 / n) * (n - d) / (n - 1)
        if va > 0:
            stat = (oa - ea) ** 2 / va
            out["log_rank_p"] = round(float(chi2.sf(stat, 1)), 4)
            notes.append(f"Log-rank p = {out['log_rank_p']}. Small samples give weak tests; look at the curves and the number at risk.")
    out["says"] = "; ".join(f"{r['group']}: {r['events']} events in {r['people']} people, median {r['median_survival']}" for r in res)
    out["notes"] = notes
    out["caution"] = "Unadjusted comparison: it does not account for differences between groups. " + PHI
    return out


# ------------------------------------------------------------------ tools: health analytics
@tool("hana", "rate", "Rate with interval", "A rate per population with an exact confidence interval, and optional comparison with a reference rate.", [I("events", "Events (count)", "number"), I("pop", "Denominator (people, admissions or patient days)", "number"), I("per", "Per how many", "number", "1000"), I("ref", "Reference rate per same unit (optional)", "number", "")])
def rate(v):
    k, n, per = num(v, "events", 0), num(v, "pop", 0.0001), num(v, "per", 1)
    if k != int(k):
        raise PackError("Events must be a whole number.")
    lo, hi = poisson_ci(int(k))
    r = per * k / n
    out = {"rate": round(r, 3), "lower": round(per * lo / n, 3), "upper": round(per * hi / n, 3), "per": per}
    out["says"] = f"{r:.2f} per {per:g} (95% interval {per * lo / n:.2f} to {per * hi / n:.2f}) from {int(k)} events."
    notes = ["Exact (Poisson) interval. It assumes events are independent and the rate is steady."]
    if v.get("ref") not in (None, ""):
        ref = num(v, "ref", 0)
        inside = per * lo / n <= ref <= per * hi / n
        notes.append(f"The reference rate {ref:g} is {'inside' if inside else 'outside'} the interval, so the difference {'could be chance' if inside else 'is unlikely to be chance alone'}. Check for case-mix differences before drawing conclusions.")
    if k < 10:
        notes.append("Fewer than 10 events: the interval is wide. Combine periods if you can.")
    out["notes"] = notes
    return out


@tool("hana", "age", "Age adjustment", "Directly standardises a rate to a standard population so groups with different ages can be compared.", [I("strata", "Lines: age group, events, population, standard population weight", "area", "0-44, 5, 3000, 50000\n45-64, 20, 2500, 30000\n65+, 90, 1500, 20000"), I("per", "Per how many", "number", "1000")])
def age(v):
    per, d, p, w = num(v, "per", 1), [], [], []
    names = []
    for i, ln in enumerate(rows(v, "strata", 30), 1):
        c = split(ln)
        if len(c) < 4:
            raise PackError(f"Line {i} needs age group, events, population and weight.")
        try:
            e, pp, ww = float(c[1]), float(c[2]), float(c[3])
        except ValueError:
            raise PackError(f"Line {i}: events, population and weight must be numbers.") from None
        if e < 0 or pp <= 0 or ww < 0:
            raise PackError(f"Line {i}: population must be above 0 and the others at least 0.")
        names.append(c[0]), d.append(e), p.append(pp), w.append(ww)
    if len(d) < 2 or sum(w) <= 0:
        raise PackError("Give at least two age groups and positive weights.")
    tw = sum(w)
    crude = per * sum(d) / sum(p)
    adj = per * sum(wi * di / pi for wi, di, pi in zip(w, d, p)) / tw
    var = sum((wi / tw) ** 2 * di / pi ** 2 for wi, di, pi in zip(w, d, p))
    se = per * math.sqrt(var)
    return {"says": f"Crude rate {crude:.2f}; age-adjusted rate {adj:.2f} per {per:g} (approx. 95% interval {max(adj - 1.96 * se, 0):.2f} to {adj + 1.96 * se:.2f}).", "crude_rate": round(crude, 3), "adjusted_rate": round(adj, 3), "adjusted_lower": round(max(adj - 1.96 * se, 0), 3), "adjusted_upper": round(adj + 1.96 * se, 3),
            "strata": [{"age_group": n, "rate": round(per * di / pi, 3), "weight_pct": round(100 * wi / tw, 1)} for n, di, pi, wi in zip(names, d, p, w)],
            "notes": ["Compare adjusted rates only between groups standardised to the same standard population.", "The interval is a normal approximation and is rough when counts per age group are small."]}


@tool("hana", "smr", "Observed vs expected", "Observed to expected ratio with an exact interval.", [I("obs", "Observed events", "number"), I("exp", "Expected events", "number")])
def smr(v):
    from scipy.stats import poisson
    o, e = num(v, "obs", 0), num(v, "exp", 0.0001)
    if o != int(o):
        raise PackError("Observed events must be a whole number.")
    lo, hi = poisson_ci(int(o))
    r = o / e
    p = float(min(1.0, 2 * min(poisson.cdf(o, e), poisson.sf(o - 1, e))))
    sig = lo / e > 1 or hi / e < 1
    return {"says": f"Ratio {r:.2f} (95% interval {lo / e:.2f} to {hi / e:.2f}): {'higher' if lo / e > 1 else 'lower' if hi / e < 1 else 'not clearly different from expected'}.", "ratio": round(r, 3), "lower": round(lo / e, 3), "upper": round(hi / e, 3), "p_value_two_sided": round(p, 4), "interval_excludes_1": sig,
            "notes": ["The result is only as good as the expected number: a poor risk model gives a misleading ratio.", "Check data and coding changes before concluding care changed."]}


@tool("hana", "los", "Length of stay summary", "Median, spread and long-stay share for a list of stays.", [I("days", "Lengths of stay in days (separated by commas, spaces or new lines)", "area"), I("threshold", "Long-stay threshold (days, optional)", "number", "")])
def los(v):
    xs = sorted(float(x) for x in re.split(r"[\s,;]+", txt(v, "days", 200000, True)) if x)
    if len(xs) < 3:
        raise PackError("Give at least three stays.")
    if xs[0] < 0:
        raise PackError("A stay cannot be negative: check for date errors.")
    q = lambda f: xs[min(len(xs) - 1, int(f * len(xs)))]  # noqa: E731
    mean = sum(xs) / len(xs)
    out = {"stays": len(xs), "mean": round(mean, 2), "median": q(0.5), "p25": q(0.25), "p75": q(0.75), "p90": q(0.9), "max": xs[-1]}
    notes = []
    if mean > 1.3 * q(0.5):
        notes.append("The mean is well above the median: a few long stays pull it up. Report the median and the 90th percentile too.")
    if v.get("threshold") not in (None, ""):
        th = num(v, "threshold", 0)
        k = sum(x > th for x in xs)
        out["share_over_threshold_pct"] = round(100 * k / len(xs), 1)
        notes.append(f"{k} of {len(xs)} stays ({100 * k / len(xs):.1f}%) are over {th:g} days.")
    out["says"] = f"Median {out['median']:g} days, average {mean:.1f}, 90th percentile {out['p90']:g}."
    out["notes"] = notes
    return out


@tool("hana", "prop", "Proportion with interval", "A percentage with a confidence interval (for example a readmission rate).", [I("x", "Number with the outcome", "number"), I("n", "Total", "number")])
def prop(v):
    x, n = num(v, "x", 0), num(v, "n", 1)
    if x > n:
        raise PackError("The count cannot be more than the total.")
    lo, hi = wilson(x, n)
    return {"says": f"{100 * x / n:.1f}% ({int(x)} of {int(n)}); 95% interval {100 * lo:.1f}% to {100 * hi:.1f}%.", "percent": round(100 * x / n, 2), "lower": round(100 * lo, 2), "upper": round(100 * hi, 2), "notes": ["Wilson interval. With few cases the interval is wide: do not over-read a single month."]}


# ------------------------------------------------------------------ tools: health BI
KPIS = {
    "readmit": ("30-day readmission rate", "Readmissions", "Discharges", 100, "%", False, "Readmissions within 30 days of discharge divided by discharges in the period."),
    "alos": ("Average length of stay", "Total resident or patient days", "Discharges", 1, "days", None, "Days of stay divided by discharges. Check whether you count the discharge day."),
    "occupancy": ("Occupancy", "Resident days", "Available bed days", 100, "%", None, "Resident days divided by beds times days in the period."),
    "hprd": ("Nursing hours per resident day (HPRD)", "Nursing hours worked", "Resident days", 1, "hours", True, "Hours worked by nursing staff divided by resident days. Check which roles your regulator counts."),
    "falls": ("Falls per 1,000 resident days", "Falls", "Resident days", 1000, "per 1,000 days", False, "Falls divided by resident days times 1,000."),
    "pressure": ("New pressure injuries per 1,000 resident days", "New pressure injuries", "Resident days", 1000, "per 1,000 days", False, "New (facility-acquired) injuries divided by resident days times 1,000."),
    "infection": ("Infections per 1,000 resident days", "Infections", "Resident days", 1000, "per 1,000 days", False, "Infections meeting your surveillance definition divided by resident days times 1,000."),
    "turnover": ("Staff turnover", "Separations in the period", "Average headcount", 100, "%", False, "Separations divided by average headcount. Annualise if the period is shorter than a year."),
    "agency": ("Agency share of hours", "Agency hours", "Total hours", 100, "%", False, "Agency hours divided by all nursing hours."),
    "noshow": ("No-show rate", "No-shows", "Scheduled appointments", 100, "%", False, "Missed appointments divided by scheduled appointments."),
    "denial": ("Claim denial rate", "Denied claims", "Submitted claims", 100, "%", False, "Denied claims divided by claims submitted."),
    "dar": ("Days in accounts receivable", "Accounts receivable balance", "Average daily revenue", 1, "days", False, "Receivable balance divided by average daily revenue."),
    "vacancy": ("Vacancy rate", "Open positions", "Total budgeted positions", 100, "%", False, "Open positions divided by budgeted positions."),
}


@tool("hbi", "kpi", "Healthcare KPI calculator", "Calculates a healthcare KPI from two numbers and shows its definition.", [I("kpi", "KPI", "select", "hprd", [{"id": k, "label": x[0]} for k, x in KPIS.items()]), I("a", "Top number (see definition)", "number"), I("b", "Bottom number", "number")])
def kpi(v):
    k = txt(v, "kpi", 20)
    d = KPIS.get(k)
    if not d:
        raise PackError("Choose a KPI.")
    a, b = num(v, "a", 0), num(v, "b", 0.0000001, label="The bottom number")
    val = d[3] * a / b
    return {"says": f"{d[0]}: {val:.2f} {d[4]}.", "value": round(val, 3), "unit": d[4], "top_is": d[1], "bottom_is": d[2], "definition": d[6], "direction": {True: "higher is usually better", False: "lower is usually better", None: "depends on your situation"}[d[5]],
            "notes": ["Use the same definition and period every time so trends are comparable.", "Targets and regulatory definitions differ: check the ones that apply to you."]}


@tool("hbi", "library", "KPI library", "All KPIs in the calculator, with definitions.", [])
def library(v):
    return {"says": f"{len(KPIS)} KPIs.", "kpis": [{"kpi": x[0], "top": x[1], "bottom": x[2], "unit": x[4], "definition": x[6]} for x in KPIS.values()]}


@tool("hbi", "spec", "Dashboard spec", "Writes a one-page dashboard specification for a healthcare reader.", [I("reader", "Who reads it", "select", "don", [{"id": "admin", "label": "Administrator"}, {"id": "don", "label": "Director of nursing"}, {"id": "finance", "label": "Finance or business office"}, {"id": "quality", "label": "Quality or infection control"}]), I("facility", "Facility or unit name", "text", "")])
def spec(v):
    r = txt(v, "reader", 10)
    sets = {"admin": ["occupancy", "hprd", "turnover", "agency", "denial", "readmit"], "don": ["hprd", "agency", "falls", "pressure", "infection", "turnover"], "finance": ["dar", "denial", "occupancy", "agency", "vacancy"], "quality": ["falls", "pressure", "infection", "readmit"]}.get(r)
    if not sets:
        raise PackError("Choose who reads it.")
    sec = [("Purpose", f"Help the {r} make weekly decisions about staffing, quality and cash for {txt(v, 'facility', 80) or 'the facility'}."), ("Tiles", [f"{KPIS[k][0]} ({KPIS[k][1]} / {KPIS[k][2]}, shown as {KPIS[k][4]})" for k in sets]),
           ("Layout", ["Top row: the numbers, each with the change from last period and a color only if a target exists", "Middle: one trend line per KPI over 12 periods", "Bottom: breakdown by unit and shift"]), ("Data sources", ["(Write the system each number comes from and who owns it)"]),
           ("Refresh", ["Weekly, same weekday", "Show the date of the data on the page"]), ("Privacy", ["Aggregates only; hide counts under your minimum cell size", "No patient names or identifiers on the dashboard", "Log who opens it"]), ("Definitions", [f"{KPIS[k][0]}: {KPIS[k][6]}" for k in sets])]
    return {"says": f"Spec for the {r}: {len(sets)} tiles.", "markdown": md("Dashboard specification", sec), "caution": "A starting draft. Confirm the definitions with your regulator, payers and clinical leaders. " + PHI}


# ------------------------------------------------------------------ tools: health informatics
HL7_NAMES = {"MSH": "Message header", "PID": "Patient identification", "PV1": "Patient visit", "OBR": "Observation request", "OBX": "Observation result", "EVN": "Event type", "NK1": "Next of kin", "DG1": "Diagnosis", "AL1": "Allergy", "IN1": "Insurance", "ORC": "Common order", "MSA": "Acknowledgement"}
PID_MASK = {3, 5, 6, 7, 11, 13, 14, 19}


@tool("hinf", "hl7", "HL7 reader", "Splits an HL7 v2 message into segments and fields. Patient identifier fields are hidden by default.", [I("msg", "Paste an HL7 v2 message (made-up data only)", "area"), I("mask", "Hide patient identifier fields", "select", "yes", [{"id": "yes", "label": "Yes (recommended)"}, {"id": "no", "label": "No"}])])
def hl7(v):
    raw = txt(v, "msg", 100000, True)
    segs = [s for s in re.split(r"[\r\n]+", raw) if s.strip()]
    if not segs or not segs[0].startswith("MSH"):
        raise PackError("An HL7 message starts with an MSH line. Check the first line.")
    if len(segs[0]) < 8:
        raise PackError("The MSH line is too short.")
    sep = segs[0][3]
    if sep != "|":
        raise PackError(f"The field separator is '{sep}', but HL7 v2 normally uses |.")
    mask = txt(v, "mask", 5) != "no"
    out, find = [], []
    for s in segs[:300]:
        f = s.split("|")
        name = f[0]
        for i, val in enumerate(f[1:], 1):
            idx = i + 1 if name == "MSH" else i
            if name == "MSH" and i == 1:
                val = "|"
                idx = 1
            if not val:
                continue
            shown = "[hidden]" if mask and name == "PID" and idx in PID_MASK else val[:120]
            out.append({"segment": name, "meaning": HL7_NAMES.get(name, ""), "field": f"{name}-{idx}", "value": shown})
    h = segs[0].split("|")
    mtype = h[8] if len(h) > 8 else ""
    ver = h[11] if len(h) > 11 else ""
    if not mtype:
        find.append({"severity": "high", "says": "MSH-9 (message type) is empty."})
    if len(h) <= 9 or not h[9]:
        find.append({"severity": "medium", "says": "MSH-10 (message control id) is empty: acknowledgements cannot refer to it."})
    if not ver:
        find.append({"severity": "low", "says": "MSH-12 (version) is empty."})
    if mtype.startswith("ADT") and not any(s.startswith("PID") for s in segs):
        find.append({"severity": "high", "says": "An ADT message should include a PID segment."})
    return {"says": f"Message type {mtype or 'unknown'}, version {ver or 'unknown'}, {len(segs)} segments.", "findings": find, "fields": out[:400], "caution": "A simple reader: it does not check your interface's own profile. " + PHI}


FHIR_REQ = {"Patient": [], "Observation": ["status", "code"], "Condition": ["subject"], "Encounter": ["status", "class"], "MedicationRequest": ["status", "intent", "subject"], "Bundle": ["type"], "Procedure": ["status", "subject", "code"], "AllergyIntolerance": ["patient"]}


@tool("hinf", "fhir", "FHIR check", "A basic check of a FHIR JSON resource. Not a full validator.", [I("json", "Paste a FHIR resource as JSON (made-up data only)", "area")])
def fhir(v):
    t = txt(v, "json", 200000, True)
    try:
        d = json.loads(t)
    except json.JSONDecodeError as e:
        raise PackError(f"That is not valid JSON ({e.msg} at line {e.lineno}).") from None
    if not isinstance(d, dict) or "resourceType" not in d:
        raise PackError("A FHIR resource has a resourceType field at the top.")
    rt = d["resourceType"]
    f = []
    if rt not in FHIR_REQ:
        f.append({"severity": "low", "says": f"{rt} is not in this simple check's list. Use the official validator."})
    for k in FHIR_REQ.get(rt, []):
        if k not in d and not any(x.startswith(k) for x in d):
            f.append({"severity": "high", "says": f"{rt} needs '{k}'."})
    if rt != "Bundle" and "id" not in d:
        f.append({"severity": "low", "says": "No id: fine for a new resource to be created, but needed for updates."})

    def walk(o, path=""):
        if isinstance(o, dict):
            for k, x in o.items():
                p = f"{path}.{k}" if path else k
                if k == "reference" and isinstance(x, str) and not re.fullmatch(r"(?:[A-Za-z]+/[A-Za-z0-9\-.]{1,64}|#[\w\-]+|urn:uuid:[0-9a-fA-F\-]{36}|https?://\S+)", x):
                    f.append({"severity": "medium", "says": f"{p}: '{x[:40]}' is not a valid reference (use Type/id)."})
                if isinstance(x, str) and re.search(r"date|period|time|issued|effective|authored|recorded", k, re.I) and re.match(r"\d", x) and not re.fullmatch(r"\d{4}(-\d{2}(-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2}))?)?)?", x):
                    f.append({"severity": "medium", "says": f"{p}: '{x}' is not a valid FHIR date or dateTime (use 2026-03-01 or 2026-03-01T10:00:00Z)."})
                if k == "coding" and isinstance(x, list):
                    for j, cd in enumerate(x):
                        if isinstance(cd, dict) and cd.get("code") and not cd.get("system"):
                            f.append({"severity": "medium", "says": f"{p}[{j}]: a code without a system is ambiguous."})
                walk(x, p)
        elif isinstance(o, list):
            for j, x in enumerate(o):
                walk(x, f"{path}[{j}]")
    walk(d)
    f.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["severity"]])
    return {"says": f"{rt}: {sum(x['severity'] == 'high' for x in f)} high and {len(f)} total finding(s)." if f else f"{rt}: no problems found by this basic check.", "findings": f, "caution": "Checks a few common rules only. Use the official FHIR validator before exchanging data. " + PHI}


def _luhn_npi(s: str) -> bool:
    digits = [int(c) for c in "80840" + s]
    tot = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            d = d - 9 if d > 9 else d
        tot += d
    return tot % 10 == 0


@tool("hinf", "codes", "Code format checker", "Checks whether codes are shaped correctly. It cannot tell whether a code exists or is current.", [I("kind", "Code type", "select", "icd10", [{"id": "icd10", "label": "ICD-10-CM diagnosis"}, {"id": "cpt", "label": "CPT procedure"}, {"id": "npi", "label": "NPI provider number"}, {"id": "ndc", "label": "NDC drug code"}, {"id": "loinc", "label": "LOINC lab code"}, {"id": "snomed", "label": "SNOMED CT concept id"}]), I("codes", "Codes (one per line)", "area")])
def codes(v):
    kind = txt(v, "kind", 10)
    chk = {"icd10": lambda c: bool(re.fullmatch(r"[A-TV-Z][0-9][0-9AB](?:\.[0-9A-TV-Z]{1,4})?", c.upper())), "cpt": lambda c: bool(re.fullmatch(r"\d{5}|\d{4}[A-Z]", c.upper())),
           "npi": lambda c: bool(re.fullmatch(r"[12]\d{9}", c)) and _luhn_npi(c), "ndc": lambda c: bool(re.fullmatch(r"\d{4}-\d{4}-\d{2}|\d{5}-\d{3}-\d{2}|\d{5}-\d{4}-\d|\d{11}", c)),
           "loinc": lambda c: bool(re.fullmatch(r"\d{1,5}-\d", c)), "snomed": lambda c: bool(re.fullmatch(r"[1-9]\d{5,17}", c))}.get(kind)
    if not chk:
        raise PackError("Choose a code type.")
    cs = rows(v, "codes", 500, 40)
    if not cs:
        raise PackError("Add at least one code.")
    res = [{"code": c, "format_ok": chk(c)} for c in cs]
    bad = [r for r in res if not r["format_ok"]]
    return {"says": f"{len(res) - len(bad)} of {len(res)} codes have a valid format.", "results": res, "notes": ["NPI numbers are also checked with the standard check digit. Other types are format-only.", "A well-formed code can still be retired or not exist. Look codes up in the official set (the current ICD-10-CM and CPT editions change yearly)."]}


@tool("hinf", "spec", "Interface spec", "Writes a one-page interface specification template for connecting two systems.", [I("sender", "Sending system"), I("receiver", "Receiving system"), I("events", "What triggers a message (one per line)", "area"), I("format", "Format", "select", "hl7", [{"id": "hl7", "label": "HL7 v2"}, {"id": "fhir", "label": "FHIR (JSON over HTTPS)"}, {"id": "csv", "label": "File (CSV)"}])])
def ispec(v):
    s, r = txt(v, "sender", 80, True), txt(v, "receiver", 80, True)
    ev = rows(v, "events", 20) or ["(list the events)"]
    fm = {"hl7": "HL7 v2 over a secure connection", "fhir": "FHIR JSON over HTTPS", "csv": "CSV file over a secure transfer"}.get(txt(v, "format", 5))
    if not fm:
        raise PackError("Choose a format.")
    sec = [("Parties", [f"Sender: {s}", f"Receiver: {r}", "Technical contacts: (names, phone, hours)"]), ("Format and transport", [fm, "Encryption in transit: yes", "Authentication: (describe)"]), ("Triggers", ev),
           ("Field mapping", ["(table: source field, receiving field, format, required?, example made-up value)"]), ("Acknowledgement and errors", ["Receiver confirms each message", "Rejected messages go to a queue someone checks daily", "Retry rules: (how many times, how far apart)"]),
           ("Testing", ["Test with made-up data only", "Include missing fields, bad dates and duplicate messages", "Sign-off by both sides before go-live"]), ("Go-live", ["Cutover date and rollback plan", "Monitoring after go-live: message counts and queue length"])]
    return {"says": f"Interface spec from {s} to {r}.", "markdown": md(f"Interface specification: {s} to {r}", sec), "caution": PHI}
