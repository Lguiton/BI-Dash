"""Science field packs: statistics, genomic data science, science and research."""
from __future__ import annotations

import math
import random
import re

from app.services import field_howto as fh
from app.services.fieldpacks import I, PackError, md, num, numlist, pack, rows, split, tool, txt
from app.services.packs_health import wilson

STAT, GEN, SCI = "Statistics", "Genomic data science", "Science and research"
fh.AREAS.extend([STAT, GEN, SCI])
g = fh._g

pack("stat", STAT, "Science and research", "Tests, confidence intervals, sample size, multiple-testing correction and correlation, with plain-English results.", "scientist", "e.g. which test should I use, how many subjects", "statistician statistics t test chi square confidence interval power sample size p value multiple testing correlation")
pack("gen", GEN, "Science and research", "DNA sequence summaries, Hardy-Weinberg check, VCF summary and a simple association test.", "scientist", "e.g. summarize a FASTA, check a variant file", "genomic data science genomics dna sequence fasta gc content vcf variants hardy weinberg gwas allele association")
pack("sci", SCI, "Science and research", "Randomization schedule, effect size, study protocol outline, sample size and citation formatter.", "scientist", "e.g. plan a study, randomize participants", "science research study design randomization protocol pico effect size citation preregistration reproducibility")

# ------------------------------------------------------------------ guides: statistics
g("st-which", STAT, "Which statistical test should I use?", "which test choose t test chi square mann whitney anova paired compare groups categorical numeric", "The right test depends on the kind of data and the design.", ["Say what you compare: two groups, before and after, or several groups.", "Say the data type: numbers or categories.", "Two groups of numbers: t-test (or Mann-Whitney if skewed or small).", "Before and after on the same people: paired test.", "Two categories against each other: chi-square (Fisher if counts are small).", "Use the group comparison tool and read the effect size, not only p."], "You can state your question, your test and why in one sentence.", 20, "", "Compare two groups")
g("st-p", STAT, "What does a p-value actually mean?", "p value meaning significance 0.05 misinterpret probability null hypothesis effect size confidence interval", "It is how surprising the data would be if there were no effect. It is not the chance the finding is true.", ["Report the size of the effect with its confidence interval.", "Treat 0.05 as a convention, not a cliff.", "A tiny p with a tiny effect may not matter; a large effect with a wide interval may be real but uncertain.", "Never say 'proves' from a p-value."], "Your write-up gives the effect size, interval and context.", 15)
g("st-small", STAT, "Very small samples", "small sample size few observations n 5 power low unreliable exact test bootstrap", "Small studies give wide, unstable estimates.", ["Report intervals; they will be wide.", "Prefer exact or rank-based tests.", "Avoid many comparisons.", "Treat results as hints to test again, not conclusions."], "Intervals are shown and claims are modest.", 20, "", "Confidence interval")
g("st-power", STAT, "How many subjects do I need?", "sample size power calculation effect size alpha 80 percent how many participants needed study planning", "Too small and you miss real effects; too large wastes effort.", ["Decide the smallest effect that would matter.", "Estimate the spread from earlier data or a pilot.", "Choose alpha 0.05 and power 0.8 or 0.9.", "Use the sample size tool.", "Add 10 to 20 percent for dropout."], "A written sample size with the assumptions behind it.", 30, "", "Sample size")
g("st-multi", STAT, "Many tests, some will look significant by chance", "multiple comparisons testing correction bonferroni holm benjamini hochberg fdr false discovery many hypotheses", "Run 20 tests at 0.05 and about one will be 'significant' by luck.", ["List every test you ran, including ones you dropped.", "Choose a correction: Bonferroni or Holm for strict control, Benjamini-Hochberg for exploring.", "Use the multiple-testing tool.", "Report adjusted values and say how many tests were run."], "You report adjusted p-values and the number of tests.", 20, "", "Multiple testing")
g("st-outlier", STAT, "An outlier is changing my results", "outlier extreme value influence median robust remove data entry error", "One extreme value can move a mean a lot.", ["Check it is not a typing or unit error.", "If real, keep it and use robust methods (median, rank tests).", "Report results with and without it.", "Never delete a value only because it hurts your result."], "Conclusions hold with and without the value, or you explain the difference.", 20)
g("st-corr", STAT, "Two things move together: does one cause the other?", "correlation causation confounder pearson spearman scatter relationship association cause", "Correlation shows a pattern, not a reason.", ["Plot the data first.", "Use Spearman if the pattern is curved but steady or the data is skewed.", "Think of a third thing that drives both.", "Only a designed experiment or careful causal analysis can support 'causes'."], "You describe the pattern as association unless the design supports more.", 20, "", "Correlation")

# ------------------------------------------------------------------ guides: genomics
g("gn-qc", GEN, "Checking sequencing data quality first", "qc quality control fastq reads fastqc trimming adapters phred contamination sequencing", "Bad reads give bad variants.", ["Run a read-quality tool (such as FastQC) on the raw files.", "Look at base quality, adapter content and duplication.", "Trim only what the report justifies.", "Re-check after trimming.", "Keep the reports with the data."], "Quality reports are clean enough for your goal and filed with the data.", 45)
g("gn-fasta", GEN, "Summarising a sequence file (FASTA)", "summarize summarise fasta sequence file gc content length composition reverse complement orf translate dna", "A quick summary shows whether a sequence looks as expected before you analyse it.", ["Open the file and check each record starts with a > header line.", "Paste the sequence into the sequence summary tool.", "Check length, base counts and GC content against what you expect for the organism or target.", "Look for runs of N (unknown bases) and unexpected letters.", "Use the reverse complement and open reading frame list to check orientation."], "Length and composition match what you expect and there are no unexplained N runs or odd letters.", 15, "", "Sequence summary")
g("gn-ref", GEN, "Reference genome versions do not match", "reference genome build grch37 grch38 hg19 hg38 coordinates liftover mismatch chromosome naming", "Positions only mean something relative to the same genome build.", ["Find the build for every file.", "Convert (liftover) to a single build or realign.", "Check chromosome names (chr1 vs 1).", "Record the build in your notes."], "All files use one build and one naming style.", 40)
g("gn-vcf", GEN, "Understanding a variant file (VCF)", "vcf variants snp indel qual depth dp filter chrom pos ref alt genotype read", "Each row is one variant with quality information.", ["Read the header lines starting with ##.", "Know the columns: chromosome, position, reference, alternate, quality, filter, info.", "Use the VCF summary to count types and check quality and depth.", "Filter by quality and depth before trusting a variant."], "You know how many variants pass your filters.", 30, "", "VCF summary")
g("gn-multi", GEN, "Thousands of tests in an association study", "gwas association multiple testing genome wide significance 5e-8 bonferroni fdr population stratification", "Testing millions of variants needs strict thresholds.", ["Use the field's conventional genome-wide threshold (5 x 10^-8 for common-variant studies).", "Check for population structure, which can create false hits.", "Replicate in another sample.", "Report effect sizes and intervals."], "Hits pass the strict threshold and replicate.", 90, "", "Association (2x2)")
g("gn-hwe", GEN, "Genotype counts look wrong (Hardy-Weinberg)", "hardy weinberg equilibrium genotype counts deviation genotyping error population structure allele frequency", "Large departures often mean genotyping error or population structure.", ["Count the three genotypes.", "Run the Hardy-Weinberg check.", "Large deviations in controls suggest quality problems.", "Check the calling for that variant."], "Variants out of equilibrium are reviewed or removed.", 25, "", "Hardy-Weinberg")
g("gn-privacy", GEN, "Handling human genomic data responsibly", "genomic data privacy consent identifiable reidentification access controlled data sharing ethics dbgap", "Genomes are identifying and shared with relatives.", ["Confirm consent covers your use.", "Store data encrypted with limited access.", "Share through controlled-access repositories.", "Never put identifiable genomes in public tools or chat."], "Consent, storage and sharing rules are documented.", 60, "General information, not legal or ethical approval.")
g("gn-repro", GEN, "Making a pipeline repeatable", "pipeline reproducibility workflow nextflow snakemake containers versions parameters bioinformatics", "Results that cannot be rerun cannot be trusted.", ["Write the steps as a workflow, not typed commands.", "Pin tool versions with containers.", "Keep parameters in a file under version control.", "Rerun from raw data on a clean machine."], "A second person can reproduce the results.", 180)

# ------------------------------------------------------------------ guides: science and research
g("sc-question", SCI, "Turning an idea into a researchable question", "research question pico hypothesis population intervention comparison outcome study design", "A sharp question decides everything else.", ["Say who (population), what you change or compare, against what, and the outcome measured.", "Use the protocol outline tool to write it as one structure.", "Write what result would change your mind.", "Check it can be answered with data you can actually get."], "One sentence says who, what, against what, and outcome.", 45, "", "Protocol outline")
g("sc-random", SCI, "Assigning participants fairly", "randomization random assignment blocks groups bias allocation concealment trial experiment", "Random assignment makes groups comparable.", ["Choose groups and block size.", "Generate the schedule with a recorded seed.", "Keep the schedule hidden from the people enrolling participants.", "Record who got which."], "Assignment follows a stored, reproducible schedule.", 20, "", "Randomization")
g("sc-prereg", SCI, "Writing the plan before you look at the data", "preregistration analysis plan hypotheses outcome primary secondary p hacking researcher degrees of freedom", "Deciding after seeing results makes false findings likely.", ["Write the primary outcome and the analysis.", "State how you handle missing data and outliers.", "Date and store the plan.", "Label any later analysis as exploratory."], "Your report separates planned from exploratory analyses.", 60, "", "Protocol outline")
g("sc-dmp", SCI, "Managing research data", "data management plan dmp storage backup metadata sharing fair retention naming versioning", "Good habits protect your results and others' ability to use them.", ["Name files consistently and keep raw data read-only.", "Back up in two places.", "Write a data dictionary.", "Decide what you will share and when.", "Remove identifiers first."], "A colleague can find and understand your data without asking you.", 60)
g("sc-reproduce", SCI, "Making analysis reproducible", "reproducible research code notebook environment versions seed raw data scripts version control", "Another person (or you in six months) should get the same numbers.", ["Script every step from raw data to figures.", "Record software versions.", "Set random seeds.", "Keep code in version control.", "Rerun from scratch before submitting."], "Rerunning the scripts reproduces every number and figure.", 90)
g("sc-ethics", SCI, "Do I need ethics approval?", "ethics irb review board human participants consent approval data protection study", "Studies with people usually need review before starting.", ["Ask your institution's review board early.", "Prepare a consent form in plain language.", "Plan data protection.", "Do not start collecting before approval."], "Written approval, or a written statement that none is needed.", 120, "Rules vary by country and institution.")
g("sc-cite", SCI, "Citing sources properly", "citation reference apa style bibliography sources plagiarism formatting zotero", "Citations let readers check your claims.", ["Pick one style and use a reference manager.", "Cite the original source when you can.", "Check each reference exists.", "Use the citation formatter for a quick APA entry."], "Every claim from another source has a checkable reference.", 20, "", "Citation formatter")

# ------------------------------------------------------------------ tools: statistics
def _ttest_ci(a, b):
    from scipy import stats
    r = stats.ttest_ind(a, b, equal_var=False)
    na, nb = len(a), len(b)
    ma, mb = sum(a) / na, sum(b) / nb
    va, vb = sum((x - ma) ** 2 for x in a) / (na - 1), sum((x - mb) ** 2 for x in b) / (nb - 1)
    se = math.sqrt(va / na + vb / nb)
    df = (va / na + vb / nb) ** 2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1)) if se > 0 else na + nb - 2
    t = stats.t.ppf(0.975, df)
    return ma - mb, (ma - mb - t * se, ma - mb + t * se), float(r.pvalue)


def _d(a, b):
    na, nb = len(a), len(b)
    ma, mb = sum(a) / na, sum(b) / nb
    sp = math.sqrt(((na - 1) * sum((x - ma) ** 2 for x in a) / (na - 1) + (nb - 1) * sum((x - mb) ** 2 for x in b) / (nb - 1)) / (na + nb - 2))
    return (ma - mb) / sp if sp > 0 else float("nan")


@tool("stat", "compare", "Compare two groups", "Compares two lists of numbers: Welch t-test, a rank test, the effect size and an interval for the difference.", [I("a", "Group A numbers", "area", "5.1 6.2 5.8 7.0 6.4 5.5"), I("b", "Group B numbers", "area", "6.8 7.5 7.1 8.0 6.9 7.7"), I("paired", "Same people measured twice?", "select", "no", [{"id": "no", "label": "No, two separate groups"}, {"id": "yes", "label": "Yes, paired (same order)"}])])
def compare(v):
    from scipy import stats
    a, b = numlist(v, "a"), numlist(v, "b")
    paired = txt(v, "paired", 4) == "yes"
    if paired:
        if len(a) != len(b):
            raise PackError("Paired data needs the same number of values in both lists, in the same order.")
        diffs = [x - y for x, y in zip(a, b)]
        n = len(diffs)
        md_, sd = sum(diffs) / n, math.sqrt(sum((x - sum(diffs) / n) ** 2 for x in diffs) / (n - 1))
        r = stats.ttest_rel(a, b)
        t = stats.t.ppf(0.975, n - 1)
        lo, hi = md_ - t * sd / math.sqrt(n), md_ + t * sd / math.sqrt(n)
        p, d = float(r.pvalue), md_ / sd if sd > 0 else float("nan")
        w = stats.wilcoxon(diffs).pvalue if any(diffs) else None
        name = "Paired t-test"
    else:
        if len(a) < 2 or len(b) < 2:
            raise PackError("Each group needs at least two numbers.")
        md_, (lo, hi), p = _ttest_ci(a, b)
        d = _d(a, b)
        w = stats.mannwhitneyu(a, b, alternative="two-sided").pvalue
        name = "Welch t-test"
    notes = [f"{name} compares averages and assumes the numbers are roughly bell-shaped (or the groups are large). The rank test p-value is shown as a check.", "A small p-value says the difference is unlikely to be chance alone; it does not say the difference matters. Look at the effect size and the interval."]
    if min(len(a), len(b)) < 10:
        notes.append("Fewer than 10 per group: results are fragile. Treat them as a hint.")
    mag = "negligible" if abs(d) < 0.2 else "small" if abs(d) < 0.5 else "medium" if abs(d) < 0.8 else "large"
    return {"says": f"{name}: difference {md_:.3g} (95% interval {lo:.3g} to {hi:.3g}), p = {p:.3g}. Effect size {d:.2f} ({mag}).", "mean_a": round(sum(a) / len(a), 4), "mean_b": round(sum(b) / len(b), 4), "difference": round(md_, 4), "interval_low": round(lo, 4), "interval_high": round(hi, 4), "p_value": round(p, 5),
            "rank_test_p_value": round(float(w), 5) if w is not None else None, "effect_size_d": round(d, 3), "notes": notes}


@tool("stat", "chisq", "Table of counts (chi-square)", "Tests whether two categories are related, from a table of counts.", [I("table", "Rows of counts, separated by commas or spaces (one row per line)", "area", "30, 20\n15, 35")])
def chisq(v):
    from scipy import stats
    tab = []
    for ln in rows(v, "table", 12):
        try:
            tab.append([float(x) for x in re.split(r"[\s,;]+", ln) if x])
        except ValueError:
            raise PackError("The table may only contain numbers.") from None
    if len(tab) < 2 or any(len(r) != len(tab[0]) for r in tab) or len(tab[0]) < 2:
        raise PackError("Give at least a 2 by 2 table with the same number of columns in every row.")
    if any(x < 0 for r in tab for x in r) or any(x != int(x) for r in tab for x in r):
        raise PackError("Counts must be whole numbers, 0 or more.")
    if any(sum(r) == 0 for r in tab) or any(sum(c) == 0 for c in zip(*tab)):
        raise PackError("A row or column of zeros cannot be tested. Remove it.")
    chi, p, dof, exp = stats.chi2_contingency(tab, correction=False)
    n = sum(map(sum, tab))
    k = min(len(tab), len(tab[0])) - 1
    cv = math.sqrt(chi / (n * k)) if k > 0 else 0
    out = {"chi_square": round(float(chi), 3), "degrees_of_freedom": int(dof), "p_value": round(float(p), 5), "cramers_v": round(cv, 3)}
    notes = ["Cramer's V is an effect size from 0 (no link) to 1 (complete link)."]
    small = sum(1 for r in exp for x in r if x < 5)
    if len(tab) == 2 and len(tab[0]) == 2:
        fe = stats.fisher_exact(tab)
        out["fisher_exact_p"] = round(float(fe.pvalue), 5)
        out["odds_ratio"] = round(float(fe.statistic), 3)
        if small:
            notes.append("Some expected counts are under 5, so use the Fisher exact p-value.")
    elif small:
        notes.append(f"{small} cell(s) have expected counts under 5: the chi-square result is unreliable. Combine categories if sensible.")
    out["says"] = f"Chi-square {chi:.2f}, {int(dof)} degrees of freedom, p = {p:.3g}; strength of link (Cramer's V) {cv:.2f}."
    out["notes"] = notes
    return out


@tool("stat", "ci", "Confidence interval", "An interval for a mean (from numbers) or a proportion (from counts).", [I("kind", "What for", "select", "mean", [{"id": "mean", "label": "Average of some numbers"}, {"id": "prop", "label": "A proportion (count out of total)"}]), I("data", "Numbers (for an average)", "area"), I("x", "Count with outcome (for a proportion)", "number", ""), I("n", "Total (for a proportion)", "number", ""), I("conf", "Confidence level (%)", "number", "95")])
def ci(v):
    from scipy import stats
    conf = num(v, "conf", 50, 99.9) / 100
    if txt(v, "kind", 6) == "prop":
        x, n = num(v, "x", 0), num(v, "n", 1)
        if x > n:
            raise PackError("The count cannot be more than the total.")
        lo, hi = wilson(x, n, float(stats.norm.ppf(1 - (1 - conf) / 2)))
        return {"says": f"{100 * x / n:.1f}% ({conf:.0%} interval {100 * lo:.1f}% to {100 * hi:.1f}%).", "estimate_pct": round(100 * x / n, 2), "lower_pct": round(100 * lo, 2), "upper_pct": round(100 * hi, 2), "notes": ["Wilson interval, which behaves well for small counts."]}
    xs = numlist(v, "data")
    n = len(xs)
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    h = float(stats.t.ppf(1 - (1 - conf) / 2, n - 1)) * sd / math.sqrt(n)
    return {"says": f"Mean {m:.4g} ({conf:.0%} interval {m - h:.4g} to {m + h:.4g}) from {n} values.", "mean": round(m, 5), "sd": round(sd, 5), "lower": round(m - h, 5), "upper": round(m + h, 5), "n": n, "notes": ["Assumes the values are roughly bell-shaped, or the sample is fairly large. A 95% interval is a method that captures the true mean 95% of the time, not a 95% chance for this one interval."]}


@tool("stat", "power", "Sample size", "How many people per group for two means or two proportions.", [I("kind", "Comparing", "select", "means", [{"id": "means", "label": "Two averages"}, {"id": "props", "label": "Two proportions"}]), I("a", "Averages: smallest difference that matters. Proportions: group 1 rate (%)", "number"), I("b", "Averages: standard deviation. Proportions: group 2 rate (%)", "number"), I("alpha", "Significance level", "number", "0.05"), I("power", "Power", "number", "0.8")])
def power(v):
    from scipy import stats
    alpha, pw = num(v, "alpha", 0.001, 0.2), num(v, "power", 0.5, 0.99)
    a, b = num(v, "a", 0.0000001), num(v, "b", 0.0000001)
    za, zb = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(pw)
    if txt(v, "kind", 6) == "props":
        if not (0 < a < 100 and 0 < b < 100) or a == b:
            raise PackError("Give two different rates between 0 and 100.")
        p1, p2 = a / 100, b / 100
        pbar = (p1 + p2) / 2
        n = ((za * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2) / (p1 - p2) ** 2
    else:
        d = a / b
        n = 2 * ((za + zb) / d) ** 2
        for _ in range(30):
            df = 2 * max(n, 2) - 2
            nc = d * math.sqrt(max(n, 2) / 2)
            tc = stats.t.ppf(1 - alpha / 2, df)
            cur = 1 - stats.nct.cdf(tc, df, nc) + stats.nct.cdf(-tc, df, nc)
            if abs(cur - pw) < 0.002:
                break
            n *= 1 + (pw - cur) * 0.6
    n = math.ceil(n)
    return {"says": f"About {n} per group ({2 * n} in total); allow for dropout: {math.ceil(n * 1.15)} per group at 15% loss.", "per_group": n, "total": 2 * n, "with_15pct_dropout_per_group": math.ceil(n * 1.15),
            "notes": ["Assumes equal group sizes, a two-sided test and that your standard deviation or rates are right. If those inputs are guesses, so is the answer: try a few values.", "Use the smallest effect that would matter, not the effect you hope to find."]}


@tool("stat", "multi", "Multiple testing", "Adjusts a list of p-values for the number of tests (Bonferroni, Holm, Benjamini-Hochberg).", [I("p", "P-values (separated by spaces, commas or new lines)", "area", "0.001 0.012 0.03 0.04 0.2"), I("alpha", "Level", "number", "0.05")])
def multi(v):
    ps = numlist(v, "p", 1, 10000)
    if any(not 0 <= p <= 1 for p in ps):
        raise PackError("P-values must be between 0 and 1.")
    alpha = num(v, "alpha", 0.001, 0.5)
    m = len(ps)
    order = sorted(range(m), key=lambda i: ps[i])
    holm, bh = [0.0] * m, [0.0] * m
    run = 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (m - r) * ps[i]))
        holm[i] = run
    run = 1.0
    for r in range(m - 1, -1, -1):
        i = order[r]
        run = min(run, ps[i] * m / (r + 1))
        bh[i] = run
    out = [{"p": ps[i], "bonferroni": round(min(1.0, ps[i] * m), 5), "holm": round(holm[i], 5), "benjamini_hochberg": round(bh[i], 5), "significant_after_bh": bh[i] <= alpha} for i in order]
    return {"says": f"{sum(r['significant_after_bh'] for r in out)} of {m} remain significant at {alpha:g} using Benjamini-Hochberg; {sum(r['bonferroni'] <= alpha for r in out)} with Bonferroni.", "results": out, "notes": ["Bonferroni and Holm control the chance of any false positive; Benjamini-Hochberg controls the share of false discoveries and suits exploration.", "Include every test you ran, not only the ones that worked."]}


@tool("stat", "corr", "Correlation", "How strongly two lists of numbers move together (Pearson and Spearman), with an interval.", [I("x", "X values", "area", "1 2 3 4 5 6 7 8"), I("y", "Y values (same order)", "area", "2.1 2.9 3.8 5.2 5.1 6.9 7.2 8.8")])
def corr(v):
    from scipy import stats
    x, y = numlist(v, "x", 3), numlist(v, "y", 3)
    if len(x) != len(y):
        raise PackError("X and Y need the same number of values.")
    if len(set(x)) < 2 or len(set(y)) < 2:
        raise PackError("Each list needs at least two different values.")
    r, p = stats.pearsonr(x, y)
    rs, ps = stats.spearmanr(x, y)
    n = len(x)
    lo = hi = None
    if n > 3 and abs(r) < 1:
        z, se = math.atanh(r), 1 / math.sqrt(n - 3)
        lo, hi = math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se)
    strength = "very weak" if abs(r) < 0.2 else "weak" if abs(r) < 0.4 else "moderate" if abs(r) < 0.6 else "strong" if abs(r) < 0.8 else "very strong"
    return {"says": f"Pearson r = {r:.2f} ({strength} {'positive' if r > 0 else 'negative'}), p = {p:.3g}; Spearman = {rs:.2f}.", "pearson_r": round(float(r), 4), "pearson_p": round(float(p), 5), "interval_low": round(lo, 3) if lo is not None else None, "interval_high": round(hi, 3) if hi is not None else None, "spearman_rho": round(float(rs), 4), "n": n,
            "notes": ["Correlation is not cause: a third thing may drive both.", "Pearson measures straight-line links and is thrown by outliers; Spearman measures steady rises and falls. Plot the data."]}


# ------------------------------------------------------------------ tools: genomics
COMP = str.maketrans("ACGTacgtNn", "TGCAtgcaNn")
CODON = {}
_b = "TCAG"
_aa = "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"
for _i, _c in enumerate(f"{x}{y}{z}" for x in _b for y in _b for z in _b):
    CODON[_c] = _aa[_i]


def _parse_seq(text: str) -> list[tuple[str, str]]:
    recs, name, buf = [], "sequence", []
    for ln in text.splitlines():
        ln = ln.strip()
        if ln.startswith(">"):
            if buf:
                recs.append((name, "".join(buf)))
            name, buf = ln[1:].strip()[:60] or "sequence", []
        elif ln:
            buf.append(re.sub(r"\s+", "", ln).upper())
    if buf:
        recs.append((name, "".join(buf)))
    return recs[:50]


@tool("gen", "seq", "Sequence summary", "Length, base composition, GC content, reverse complement, translation and open reading frames for DNA text.", [I("fasta", "Paste DNA (FASTA or plain letters A C G T N)", "area", ">example\nATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG"), I("min_orf", "Smallest open reading frame to list (codons)", "number", "10")])
def seq(v):
    recs = _parse_seq(txt(v, "fasta", 500000, True))
    mo = int(num(v, "min_orf", 3, 1000))
    out, notes = [], []
    for name, s in recs:
        bad = set(s) - set("ACGTN")
        if bad:
            raise PackError(f"{name}: unexpected letters {''.join(sorted(bad))[:10]}. Only A, C, G, T and N are accepted here.")
        n = len(s)
        c = {b: s.count(b) for b in "ACGTN"}
        acgt = n - c["N"]
        gc = 100 * (c["G"] + c["C"]) / acgt if acgt else 0
        rc = s.translate(COMP)[::-1]
        orfs = []
        for strand, sq in (("+", s), ("-", rc)):
            for f in range(3):
                i = f
                while i + 3 <= len(sq):
                    if sq[i:i + 3] == "ATG":
                        j = i
                        while j + 3 <= len(sq) and CODON.get(sq[j:j + 3], "X") != "*":
                            j += 3
                        if j + 3 <= len(sq) and (j - i) // 3 >= mo:
                            orfs.append({"strand": strand, "frame": f + 1, "start": i + 1, "codons": (j - i) // 3, "protein": "".join(CODON.get(sq[k:k + 3], "X") for k in range(i, j, 3))[:60]})
                            i = j
                    i += 3
        tm = None
        if 8 <= n <= 30 and c["N"] == 0:
            tm = 2 * (c["A"] + c["T"]) + 4 * (c["G"] + c["C"]) if n < 14 else 64.9 + 41 * (c["G"] + c["C"] - 16.4) / n
        out.append({"name": name, "length": n, "A": c["A"], "C": c["C"], "G": c["G"], "T": c["T"], "N": c["N"], "gc_pct": round(gc, 1), "reverse_complement": rc[:80] + ("…" if n > 80 else ""), "orfs_found": len(orfs), "tm_estimate_c": round(tm, 1) if tm is not None else ""})
        if orfs:
            notes.append(f"{name}: longest ORF {max(orfs, key=lambda o: o['codons'])['codons']} codons ({max(orfs, key=lambda o: o['codons'])['protein'][:30]}…).")
    return {"says": f"{len(out)} sequence(s) summarised.", "sequences": out, "notes": notes + ["ORFs are ATG to stop codon in all three frames of both strands; a long ORF is a hint of a gene, not proof.", "Melting temperature is only a rough estimate for short primers."]}


@tool("gen", "hwe", "Hardy-Weinberg check", "Tests whether genotype counts match the proportions expected for the allele frequencies.", [I("aa", "Count of AA", "number"), I("ab", "Count of Aa", "number"), I("bb", "Count of aa", "number")])
def hwe(v):
    from scipy.stats import chi2
    aa, ab, bb = num(v, "aa", 0), num(v, "ab", 0), num(v, "bb", 0)
    n = aa + ab + bb
    if n < 1 or any(x != int(x) for x in (aa, ab, bb)):
        raise PackError("Give whole-number genotype counts.")
    p = (2 * aa + ab) / (2 * n)
    q = 1 - p
    exp = [p * p * n, 2 * p * q * n, q * q * n]
    if min(exp) == 0:
        raise PackError("One allele is absent, so the test does not apply.")
    chi = sum((o - e) ** 2 / e for o, e in zip((aa, ab, bb), exp))
    pv = float(chi2.sf(chi, 1))
    notes = ["Departures in healthy controls often point to genotyping errors or mixed populations.", "Selection, non-random mating and related people also break the assumption."]
    if min(exp) < 5:
        notes.insert(0, "An expected count is under 5: use an exact test instead.")
    return {"says": f"Allele A {p:.3f}, a {q:.3f}. Chi-square {chi:.2f}, p = {pv:.3g}: {'departs from' if pv < 0.05 else 'consistent with'} Hardy-Weinberg proportions.", "allele_freq_A": round(p, 4), "allele_freq_a": round(q, 4), "expected": {"AA": round(exp[0], 2), "Aa": round(exp[1], 2), "aa": round(exp[2], 2)}, "chi_square": round(chi, 3), "p_value": round(pv, 5), "notes": notes}


@tool("gen", "vcf", "VCF summary", "Counts variants by type, transitions vs transversions, and filters by quality and depth. Paste data lines of a VCF.", [I("vcf", "Paste VCF lines (header lines starting with # are ignored)", "area", "chr1\t100\t.\tA\tG\t50\tPASS\tDP=30\nchr1\t200\t.\tC\tT\t12\tPASS\tDP=8\nchr2\t300\t.\tAT\tA\t80\tPASS\tDP=40\nchr2\t400\t.\tG\tT\t60\tPASS\tDP=25"), I("min_qual", "Minimum quality", "number", "30"), I("min_dp", "Minimum depth", "number", "10")])
def vcf(v):
    mq, md_ = num(v, "min_qual", 0), num(v, "min_dp", 0)
    n = kept = snv = ind = ts = tv = 0
    chrom: dict[str, int] = {}
    TS = {("A", "G"), ("G", "A"), ("C", "T"), ("T", "C")}
    for ln in txt(v, "vcf", 3000000, True).splitlines():
        if not ln.strip() or ln.startswith("#"):
            continue
        c = re.split(r"\t|\s{2,}", ln.strip())
        if len(c) < 8:
            c = ln.split()
        if len(c) < 8:
            raise PackError(f"A VCF data line needs at least 8 columns: '{ln[:40]}'.")
        n += 1
        try:
            q = float(c[5]) if c[5] != "." else 0.0
        except ValueError:
            raise PackError(f"Quality '{c[5]}' on line {n} is not a number.") from None
        m = re.search(r"(?:^|;)DP=(\d+)", c[7])
        dp = int(m.group(1)) if m else None
        if q >= mq and (dp is None or dp >= md_):
            kept += 1
            chrom[c[0]] = chrom.get(c[0], 0) + 1
            for alt in c[4].split(","):
                if len(c[3]) == 1 and len(alt) == 1:
                    snv += 1
                    if (c[3].upper(), alt.upper()) in TS:
                        ts += 1
                    else:
                        tv += 1
                else:
                    ind += 1
    if n == 0:
        raise PackError("No variant lines found.")
    ratio = round(ts / tv, 2) if tv else None
    return {"says": f"{kept} of {n} variants pass (quality ≥ {mq:g}, depth ≥ {md_:g}): {snv} single-base changes and {ind} insertions or deletions.", "total": n, "passing": kept, "snvs": snv, "indels": ind, "transitions": ts, "transversions": tv, "ts_tv_ratio": ratio, "by_chromosome": [{"chromosome": k, "passing": x} for k, x in sorted(chrom.items())],
            "notes": ["For whole-genome human data a transition/transversion ratio near 2 is typical; exomes run higher. A ratio far from expected can signal problems, but small samples vary widely.", "Variants with no depth value are kept: check your file records DP."]}


@tool("gen", "assoc", "Association (2x2)", "Tests whether a variant is more common in cases than controls, from allele or carrier counts.", [I("ca", "Cases with the variant", "number"), I("cn", "Cases without", "number"), I("ka", "Controls with the variant", "number"), I("kn", "Controls without", "number")])
def assoc(v):
    from scipy import stats
    ca, cn, ka, kn = (num(v, k, 0) for k in ("ca", "cn", "ka", "kn"))
    if min(ca + cn, ka + kn, ca + ka, cn + kn) <= 0:
        raise PackError("Each row and column needs at least one count.")
    fe = stats.fisher_exact([[ca, cn], [ka, kn]])
    a, b, c, d = (x + 0.5 for x in (ca, cn, ka, kn)) if 0 in (ca, cn, ka, kn) else (ca, cn, ka, kn)
    orr = (a * d) / (b * c)
    se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    lo, hi = math.exp(math.log(orr) - 1.96 * se), math.exp(math.log(orr) + 1.96 * se)
    return {"says": f"Odds ratio {orr:.2f} (95% interval {lo:.2f} to {hi:.2f}), Fisher exact p = {fe.pvalue:.3g}.", "odds_ratio": round(orr, 3), "interval_low": round(lo, 3), "interval_high": round(hi, 3), "fisher_p": round(float(fe.pvalue), 6),
            "notes": ["One variant tested alone. If you tested many, adjust: genome-wide studies of common variants use about 5 x 10^-8.", "Ancestry differences between cases and controls can create false associations. Check population structure.", "Zero cells are given a 0.5 correction for the interval only."]}


# ------------------------------------------------------------------ tools: science and research
@tool("sci", "random", "Randomization", "A reproducible blocked random assignment of participants to groups.", [I("n", "Number of participants", "number", "20"), I("groups", "Group names (comma separated)", "text", "Treatment, Control"), I("block", "Block size (multiple of groups)", "number", "4"), I("seed", "Seed (write it down)", "number", "2026")])
def randomize(v):
    n, blk, seed = int(num(v, "n", 2, 2000)), int(num(v, "block", 2, 100)), int(num(v, "seed", 0, 10**9))
    gs = [x.strip() for x in str(v.get("groups") or "").split(",") if x.strip()]
    if not 2 <= len(gs) <= 6:
        raise PackError("Give between 2 and 6 group names.")
    if len(set(gs)) != len(gs):
        raise PackError("Group names must be different.")
    if blk % len(gs):
        raise PackError(f"Block size must be a multiple of the number of groups ({len(gs)}).")
    rng = random.Random(seed)
    sched = []
    while len(sched) < n:
        b = gs * (blk // len(gs))
        rng.shuffle(b)
        sched += b
    sched = sched[:n]
    return {"says": f"Schedule for {n} participants across {len(gs)} groups (seed {seed}).", "counts": [{"group": x, "participants": sched.count(x)} for x in gs], "schedule": [{"participant": i + 1, "group": s} for i, s in enumerate(sched)],
            "notes": ["Same seed and settings give the same schedule, so you can show how it was made.", "Keep the schedule hidden from people who enrol participants, and store it with the study records.", "Blocks keep group sizes balanced as recruitment proceeds; very small blocks can make the next assignment guessable."]}


@tool("sci", "effect", "Effect size", "Cohen's d, Hedges' g and an interval from two groups' summary numbers.", [I("m1", "Group 1 mean", "number"), I("s1", "Group 1 standard deviation", "number"), I("n1", "Group 1 size", "number"), I("m2", "Group 2 mean", "number"), I("s2", "Group 2 standard deviation", "number"), I("n2", "Group 2 size", "number")])
def effect(v):
    m1, s1, n1, m2, s2, n2 = (num(v, k) for k in ("m1", "s1", "n1", "m2", "s2", "n2"))
    if min(s1, s2) < 0 or min(n1, n2) < 2:
        raise PackError("Standard deviations cannot be negative and each group needs at least 2 people.")
    sp = math.sqrt(((n1 - 1) * s1 ** 2 + (n2 - 1) * s2 ** 2) / (n1 + n2 - 2))
    if sp == 0:
        raise PackError("Both standard deviations are zero, so d is undefined.")
    d = (m1 - m2) / sp
    j = 1 - 3 / (4 * (n1 + n2) - 9)
    se = math.sqrt((n1 + n2) / (n1 * n2) + d * d / (2 * (n1 + n2)))
    mag = "negligible" if abs(d) < 0.2 else "small" if abs(d) < 0.5 else "medium" if abs(d) < 0.8 else "large"
    return {"says": f"Cohen's d = {d:.2f} ({mag}); Hedges' g = {d * j:.2f}; 95% interval for d {d - 1.96 * se:.2f} to {d + 1.96 * se:.2f}.", "cohens_d": round(d, 3), "hedges_g": round(d * j, 3), "interval_low": round(d - 1.96 * se, 3), "interval_high": round(d + 1.96 * se, 3),
            "notes": ["The labels (0.2 small, 0.5 medium, 0.8 large) are rough conventions. Judge importance in your own field's terms."]}


@tool("sci", "protocol", "Protocol outline", "A one-page study protocol skeleton from your question (PICO).", [I("title", "Study title"), I("population", "Who or what is studied (P)"), I("intervention", "What is changed or exposed (I)"), I("comparison", "Compared with (C)"), I("outcome", "Main outcome measured (O)"), I("design", "Design", "select", "rct", [{"id": "rct", "label": "Randomised trial"}, {"id": "cohort", "label": "Cohort (follow a group)"}, {"id": "cross", "label": "Cross-sectional survey"}, {"id": "case", "label": "Case-control"}, {"id": "lab", "label": "Laboratory experiment"}])])
def protocol(v):
    t = txt(v, "title", 150, True)
    d = {"rct": "Randomised controlled trial", "cohort": "Cohort study", "cross": "Cross-sectional study", "case": "Case-control study", "lab": "Laboratory experiment"}.get(txt(v, "design", 6))
    if not d:
        raise PackError("Choose a design.")
    f = lambda k: txt(v, k, 300) or "(fill in)"  # noqa: E731
    sec = [("Question (PICO)", [f"Population: {f('population')}", f"Intervention or exposure: {f('intervention')}", f"Comparison: {f('comparison')}", f"Outcome: {f('outcome')}"]), ("Design", [d, "Setting and recruitment: (fill in)", "Inclusion and exclusion criteria: (fill in)"]),
           ("Hypothesis", ["Primary hypothesis (one sentence): (fill in)", "What result would change your mind: (fill in)"]), ("Outcomes", [f"Primary outcome and how measured: {f('outcome')}", "Secondary outcomes: (fill in)"]),
           ("Sample size", ["Smallest effect that matters: (fill in)", "Spread estimate and source: (fill in)", "Calculation (use the Sample size tool in Statistics): (fill in)"]), ("Analysis plan", ["Primary analysis: (fill in)", "Handling of missing data and outliers: (fill in)", "Multiple comparisons: (fill in)", "Planned versus exploratory analyses will be labelled."]),
           ("Ethics and data", ["Approval and consent: (fill in)", "Data management and privacy: (fill in)", "Data and code sharing: (fill in)"]), ("Timeline", ["(fill in)"])]
    return {"says": f"Protocol outline for {t}.", "markdown": md(f"Protocol: {t}", sec), "caution": "A skeleton to organise your thinking, not an approved protocol. Your institution's review board and a statistician should check the real one."}


@tool("sci", "cite", "Citation formatter", "Formats a journal article in APA 7 style from its parts.", [I("authors", "Authors (one per line: Last, First)", "area"), I("year", "Year"), I("title", "Article title"), I("journal", "Journal"), I("volume", "Volume"), I("issue", "Issue (optional)"), I("pages", "Pages (optional)"), I("doi", "DOI (optional)")])
def cite(v):
    au = rows(v, "authors", 20, 80)
    if not au:
        raise PackError("Add at least one author as Last, First.")
    names = []
    for a in au:
        p = [x.strip() for x in a.split(",", 1)]
        init = " ".join(w[0].upper() + "." for w in re.split(r"[\s\-]+", p[1]) if w) if len(p) > 1 else ""
        names.append(f"{p[0]}, {init}".strip(", "))
    ys, ti, jo, vol = txt(v, "year", 4, True), txt(v, "title", 250, True), txt(v, "journal", 150, True), txt(v, "volume", 10, True)
    if not re.fullmatch(r"\d{4}", ys):
        raise PackError("Year must be four digits.")
    auth = names[0] if len(names) == 1 else ", ".join(names[:-1]) + ", & " + names[-1] if len(names) <= 20 else ", ".join(names[:19]) + ", ... " + names[-1]
    iss = txt(v, "issue", 10)
    pg = txt(v, "pages", 20).replace("-", "–")
    doi = txt(v, "doi", 100)
    if doi and not re.fullmatch(r"(?:https?://doi\.org/)?10\.\d{4,9}/\S+", doi):
        raise PackError("The DOI should look like 10.1000/xyz123.")
    doi = (doi if doi.startswith("http") else "https://doi.org/" + doi) if doi else ""
    ref = f"{auth} ({ys}). {ti.rstrip('.')}. {jo}, {vol}" + (f"({iss})" if iss else "") + (f", {pg}" if pg else "") + "." + (f" {doi}" if doi else "")
    return {"says": "APA 7 reference ready.", "reference": ref, "notes": ["In your document, italicise the journal name and volume number.", "Check against the style manual or your reference manager: rules have exceptions."]}


# the same sample-size tool is useful in research planning
from app.services.fieldpacks import PACKS  # noqa: E402

PACKS["sci"]["tools"]["power"] = PACKS["stat"]["tools"]["power"]
