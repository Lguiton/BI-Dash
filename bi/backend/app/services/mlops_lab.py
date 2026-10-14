"""MLOps lab: the habits that keep a model working after you have trained it (from the Databricks "Big Book of MLOps", 2nd ed.).

It sits on top of the model registry (ML Lab -> Models) and adds what the registry did not have:
  1. promotion gate   - validation checks a new version must pass before it can challenge the live one
  2. champion / challenger - named aliases, an offline comparison, and a confirmed promotion
  3. rollout practice - shadow run (both models score the same rows, only the champion "serves"), traffic split, gradual-rollout plan
  4. serving load test - latency percentiles, throughput and errors against an SLA you set (in-process, see limits)
  5. retrain advice   - reads the drift history and says watch / investigate / retrain, and why not to automate blindly
  6. LLM approach     - prompt vs RAG vs fine-tune vs pre-train, hosted API vs self-hosted, vector library vs database
  7. feedback log     - thumbs up/down and "escalated to a human" signals, summarised per prompt version

Honest limits: comparisons use the scores stored when each version was trained, not a fresh common test set; the shadow run and load
test use made-up rows drawn from each model's training ranges, not real traffic; the load test measures one process on this machine
(no network, no autoscaling, no stress to failure); the gate catches sloppy models, not wrong ones; nothing here trains, fine-tunes or
hosts an LLM; drift advice only sees input drift. The book is a vendor guide to Databricks products, which are explained, not built.
"""
from __future__ import annotations

import hashlib
import json
import math
import time

import numpy as np

from app.services import model_registry as mr
from app.services import state, workspaces

MAX_FEEDBACK = 500
MAX_LOAD_REQUESTS = 200
LOAD_BUDGET_SECONDS = 8.0
MAX_SAMPLE_ROWS = 100
ALIASES = ("champion", "challenger")


class MlopsError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _reg(fn, *a, **k):
    try:
        return fn(*a, **k)
    except mr.ModelError as e:
        raise MlopsError(str(e), e.status) from e


def _num(v, name, lo, hi) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise MlopsError(f"{name} must be a number.") from None
    if not math.isfinite(x) or not lo <= x <= hi:
        raise MlopsError(f"{name} must be between {lo:g} and {hi:g}.")
    return x


# ------------------------------------------------------------------ aliases
def _akey() -> str:
    return f"mlops_alias:{workspaces.active()}"


def _load_aliases() -> dict:
    try:
        d = json.loads(state.kv_get(_akey(), "{}") or "{}")
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


def aliases(name: str | None = None) -> dict:
    """Alias -> version, dropping any that point at a version that was deleted."""
    have = {(m["name"], m["version"]) for m in mr.list_models()}
    data, clean = _load_aliases(), {}
    for n, al in data.items():
        keep = {a: v for a, v in al.items() if (n, v) in have}
        if keep:
            clean[n] = keep
    if name:
        return clean.get(mr.slug(name), {})
    return clean


def _set_alias(name: str, alias: str, version: int | None) -> None:
    data = aliases()
    al = data.setdefault(name, {})
    if version is None:
        al.pop(alias, None)
    else:
        al[alias] = int(version)
    if not al:
        data.pop(name, None)
    state.kv_set(_akey(), json.dumps(data))


# ------------------------------------------------------------------ made-up rows from a model's training profile
def sample_rows(name: str, version: int | None = None, n: int = 20, seed: int = 7) -> list[dict]:
    n = int(_num(n, "Rows", 1, MAX_SAMPLE_ROWS))
    c = _reg(mr.card, name, version)
    rng = np.random.RandomState(int(seed))
    rows = []
    for _ in range(n):
        row = {}
        for inp in c["inputs"]:
            if inp["kind"] == "num":
                lo, hi = inp.get("seen_range") or [None, None]
                row[inp["feature"]] = round(float(rng.uniform(lo, hi)), 2) if lo is not None and hi is not None else 0.0
            else:
                vals = inp.get("common_values") or []
                row[inp["feature"]] = str(vals[rng.randint(len(vals))]) if vals else ""
        rows.append(row)
    return rows


def _primary(c: dict) -> tuple[str, float | None, float | None]:
    p = c["primary"]
    return p["name"], p["model"], p["baseline"]


# ------------------------------------------------------------------ 1. promotion gate
def gate(name: str, version: int, min_gain: float = 0.02, set_alias: bool = True) -> dict:
    """Checks a new version must pass before it may challenge the live one (the book's 'model validation' step)."""
    gain = _num(min_gain, "Minimum gain over baseline", 0, 1)
    c = _reg(mr.card, name, version)
    pm, val, base = _primary(c)
    checks = []

    def add(cid, label, ok, detail, level="fail"):
        checks.append({"id": cid, "label": label, "ok": bool(ok), "detail": detail, "level": "pass" if ok else level})

    try:
        sample = sample_rows(c["name"], c["version"], 3)
        out = _reg(mr.predict, c["name"], sample, c["version"])
        ok_pred = len(out["predictions"]) == 3 and all(math.isfinite(float(p["prediction"])) for p in out["predictions"])
        add("loads", "Loads and scores a sample", ok_pred, "The saved file loaded and returned a finite prediction for 3 made-up rows." if ok_pred else "It loaded but returned something unusable.")
    except MlopsError as e:
        add("loads", "Loads and scores a sample", False, e.message)
    add("inputs", "Inputs are documented", bool(c["inputs"]) and all("seen_range" in i or "common_values" in i for i in c["inputs"]),
        f"{len(c['inputs'])} input(s) with their training ranges or values." if c["inputs"] else "No inputs recorded.")
    have_scores = val is not None and base is not None
    add("scored", "Has a test score and a baseline", have_scores, f"{pm}: model {val}, naive baseline {base}." if have_scores else "No test score or baseline was stored.")
    if have_scores:
        add("beats", f"Beats the naive baseline by at least {gain:g}", val >= base + gain, f"{pm} {val:g} vs baseline {base:g} (needs {base + gain:g}).")
    add("note", "Has a note saying what changed", bool((c.get("note") or "").strip()), "A note is recorded." if (c.get("note") or "").strip() else "Add a note when you register: what changed and why. Six months from now it is the only memory you have.", "warn")
    add("caveats", "Reviewed the caveats", not any("barely beats" in x for x in c["caveats"]), "No caveat says the model barely beats the baseline." if not any("barely beats" in x for x in c["caveats"]) else "The card warns this model barely beats the baseline.")
    passed = all(ch["ok"] for ch in checks if ch["level"] == "fail")
    alias_set = False
    if passed and set_alias:
        _set_alias(c["name"], "challenger", c["version"])
        alias_set = True
        state.audit("mlops_gate", f"{c['name']} v{c['version']} passed; challenger alias set")
    elif not passed:
        state.audit("mlops_gate", f"{c['name']} v{c['version']} failed", ok=False)
    return {"name": c["name"], "version": c["version"], "passed": passed, "checks": checks, "challenger_alias_set": alias_set,
            "next": "Compare it with the champion, then promote with a confirmation." if passed else "Fix the failed checks (or train a better version) and run the gate again.",
            "lesson": "A gate stops sloppy models, not wrong ones. It is the cheap, automatic first filter; the comparison with the live model is the real test.",
            "limit": "Checks use the scores stored at training time. They do not test your business slices (a model can pass overall and fail for one customer group): add slice checks if that matters."}


# ------------------------------------------------------------------ 2. champion / challenger
def _live_version(name: str) -> int | None:
    al = aliases(name)
    if "champion" in al:
        return al["champion"]
    for m in mr.list_models():
        if m["name"] == mr.slug(name) and m["stage"] == "production":
            return m["version"]
    return None


def compare(name: str, min_gain: float = 0.01) -> dict:
    slug = mr.slug(name)
    gain = _num(min_gain, "Minimum gain to replace the champion", 0, 1)
    al = aliases(slug)
    if "challenger" not in al:
        raise MlopsError("There is no challenger yet. Run the gate on a version first; a version that passes becomes the challenger.", 409)
    ch = _reg(mr.card, slug, al["challenger"])
    pm, cval, cbase = _primary(ch)
    live = _live_version(slug)
    out = {"name": slug, "challenger": al["challenger"], "champion": live, "metric": pm, "challenger_score": cval, "min_gain": gain,
           "limit": "Both scores come from each version's own test period at training time, so they are only fair if the data didn't change between. For a decisive answer run the shadow comparison on the same rows."}
    if live is None or live == al["challenger"]:
        out.update(first_deployment=True, baseline_score=cbase, decision="promote" if cval is not None and cbase is not None and cval >= cbase + gain else "hold",
                   reason="There is no champion yet, so the challenger is compared with the naive baseline (the book: a business heuristic or other threshold).")
        return out
    champ = _reg(mr.card, slug, live)
    _, kval, _ = _primary(champ)
    out["champion_score"] = kval
    if cval is None or kval is None:
        out.update(decision="hold", reason="One of the versions has no stored score, so there is nothing fair to compare.")
    elif cval >= kval + gain:
        out.update(decision="promote", reason=f"{pm} {cval:g} beats the champion's {kval:g} by {cval - kval:.3g} (needs {gain:g}).")
    else:
        out.update(decision="hold", reason=f"{pm} {cval:g} does not beat the champion's {kval:g} by {gain:g}. Keep the champion.")
    return out


def promote(name: str, confirm: bool = False, min_gain: float = 0.01) -> dict:
    if confirm is not True:
        raise MlopsError("Promotion changes which model answers predictions. Tick the confirmation to go ahead.", 400)
    cmp_ = compare(name, min_gain)
    if cmp_["decision"] != "promote":
        raise MlopsError("The challenger did not beat the champion, so nothing changed. " + cmp_["reason"], 409)
    slug, v = cmp_["name"], cmp_["challenger"]
    old = cmp_.get("champion")
    _reg(mr.set_stage, slug, v, "production")
    _set_alias(slug, "champion", v)
    _set_alias(slug, "challenger", None)
    state.audit("mlops_promote", f"{slug} v{v} is champion" + (f" (replaced v{old})" if old else " (first deployment)"))
    return {"name": slug, "champion": v, "replaced": old, "rollback": f"To go back, put v{old} in production again from the Models list." if old else "Nothing to roll back to yet.",
            "next": "Watch the drift check and your own results for the first weeks."}


def rollback(name: str, version: int, confirm: bool = False) -> dict:
    if confirm is not True:
        raise MlopsError("Rolling back changes which model answers predictions. Tick the confirmation to go ahead.", 400)
    c = _reg(mr.card, name, version)
    _reg(mr.set_stage, c["name"], c["version"], "production")
    _set_alias(c["name"], "champion", c["version"])
    state.audit("mlops_rollback", f"{c['name']} v{c['version']} is champion again")
    return {"name": c["name"], "champion": c["version"]}


# ------------------------------------------------------------------ 3. rollout practice
def shadow(name: str, rows: int = 40, seed: int = 7) -> dict:
    """Both models score the same made-up rows. Only the champion's answers would be used; the challenger is a silent observer."""
    slug = mr.slug(name)
    al = aliases(slug)
    live = _live_version(slug)
    if "challenger" not in al or live is None or live == al["challenger"]:
        raise MlopsError("A shadow run needs a champion in production and a different challenger. Promote one version, then pass the gate with another.", 409)
    data = sample_rows(slug, live, rows, seed)
    a = _reg(mr.predict, slug, data, live)["predictions"]
    b = _reg(mr.predict, slug, data, al["challenger"])["predictions"]
    kind = _reg(mr.card, slug, live)["kind"]
    out = {"name": slug, "champion": live, "challenger": al["challenger"], "rows": len(data), "kind": kind}
    if kind == "classification":
        dis = sum(1 for x, y in zip(a, b) if x["prediction"] != y["prediction"])
        diffs = [abs(x["probability"] - y["probability"]) for x, y in zip(a, b)]
        out.update(disagree=dis, disagree_pct=round(100 * dis / len(a), 1), mean_probability_gap=round(float(np.mean(diffs)), 4))
        out["reading"] = ("They give the same answer on almost every row, so the change is small." if dis / len(a) < 0.05 else
                          "They disagree on a meaningful share of rows. Look at which kind of row, then decide with real outcomes, not this count.")
    else:
        x, y = np.array([p["prediction"] for p in a]), np.array([p["prediction"] for p in b])
        gap = float(np.mean(np.abs(x - y)))
        out.update(mean_abs_gap=round(gap, 2), mean_gap_pct=round(100 * gap / max(float(np.mean(np.abs(x))), 1e-9), 1),
                   correlation=round(float(np.corrcoef(x, y)[0, 1]), 3) if len(x) > 2 and x.std() > 0 and y.std() > 0 else None)
        out["reading"] = "Small gaps and a correlation near 1 mean the models agree about which rows are high and low." if (out["correlation"] or 0) > 0.9 else "The models order rows differently. Find out why before trusting either."
    out["limit"] = "The rows are made up from the training ranges, not real traffic, and there are no true outcomes here, so this shows how the models differ, not which is right."
    return out


def traffic_split(requests: int = 1000, challenger_pct: float = 10, seed: int = 11) -> dict:
    """How an A/B or canary split behaves: each request id is hashed to a bucket so the same id always gets the same model."""
    n = int(_num(requests, "Requests", 10, 100000))
    pct = _num(challenger_pct, "Challenger share (%)", 0, 100)
    got = 0
    for i in range(n):
        h = int(hashlib.sha256(f"{seed}:{i}".encode()).hexdigest()[:8], 16) % 10000
        got += h < pct * 100
    p = pct / 100
    se = math.sqrt(p * (1 - p) / n) if n else 0
    return {"requests": n, "target_pct": pct, "challenger_requests": got, "champion_requests": n - got, "observed_pct": round(100 * got / n, 2),
            "expected_range_pct": [round(100 * max(0, p - 1.96 * se), 2), round(100 * min(1, p + 1.96 * se), 2)],
            "lesson": "A split is never exact: with few requests the share wobbles. Hash an id (customer, session) rather than rolling dice per request, so one person doesn't flip between models."}


def rollout_plan(steps_pct: list[float] | None = None, min_requests_per_step: int = 500, max_error_pct: float = 1.0, max_metric_drop_pct: float = 3.0) -> dict:
    steps = [5, 25, 50, 100] if steps_pct is None else steps_pct
    if not isinstance(steps, list) or not 1 <= len(steps) <= 8:
        raise MlopsError("Give between 1 and 8 traffic steps.")
    clean = [_num(s, "Traffic step", 1, 100) for s in steps]
    if clean != sorted(clean) or len(set(clean)) != len(clean) or clean[-1] != 100:
        raise MlopsError("Steps must increase and end at 100.")
    mr_ = int(_num(min_requests_per_step, "Requests per step", 10, 10_000_000))
    err, drop = _num(max_error_pct, "Max error rate (%)", 0, 100), _num(max_metric_drop_pct, "Max quality drop (%)", 0, 100)
    plan = [{"step": i + 1, "challenger_pct": s, "challenger_requests_needed": int(mr_), "advance_when": f"errors <= {err:g}% and quality no more than {drop:g}% below the champion",
             "roll_back_when": f"errors > {err:g}% or quality drops more than {drop:g}%"} for i, s in enumerate(clean)]
    return {"steps": plan, "compare": [
        {"pattern": "Shadow", "serves_users": False, "use": "First, when a mistake would hurt. Costs double the predictions."},
        {"pattern": "Gradual rollout (canary)", "serves_users": True, "use": "Move traffic up in steps while watching; the safety net is going back."},
        {"pattern": "A/B test", "serves_users": True, "use": "Fixed split until you have enough results to decide; needs real outcomes."}],
        "lesson": "Decide the advance and rollback rules before the first step, in writing. Deciding while the numbers are moving is how people talk themselves into it.",
        "limit": "This is a plan and a record, not a router: the dashboard has one process and doesn't split live traffic."}


# ------------------------------------------------------------------ 4. serving load test
def load_test(name: str, version: int | None = None, requests: int = 60, rows_per_request: int = 1, p95_ms: float = 250, max_error_pct: float = 1.0) -> dict:
    n = int(_num(requests, "Requests", 5, MAX_LOAD_REQUESTS))
    rpr = int(_num(rows_per_request, "Rows per request", 1, 50))
    sla, budget = _num(p95_ms, "Latency target p95 (ms)", 0.1, 600000), _num(max_error_pct, "Allowed errors (%)", 0, 100)
    c = _reg(mr.card, name, version)
    pool = sample_rows(c["name"], c["version"], MAX_SAMPLE_ROWS, 5)
    lat, errors, started = [], 0, time.perf_counter()
    for i in range(n):
        if time.perf_counter() - started > LOAD_BUDGET_SECONDS:
            break
        batch = [pool[(i * rpr + j) % len(pool)] for j in range(rpr)]
        t0 = time.perf_counter()
        try:
            mr.predict(c["name"], batch, c["version"])
        except Exception:  # noqa: BLE001 counted as an error response
            errors += 1
        lat.append((time.perf_counter() - t0) * 1000)
    total = time.perf_counter() - started
    done = len(lat)
    arr = np.array(lat) if lat else np.array([0.0])
    p50, p95, p99 = (float(np.percentile(arr, q)) for q in (50, 95, 99))
    err_pct = 100 * errors / done if done else 0.0
    ok_lat, ok_err = p95 <= sla, err_pct <= budget
    return {"name": c["name"], "version": c["version"], "requests_done": done, "requests_asked": n, "stopped_early": done < n, "rows_per_request": rpr,
            "p50_ms": round(p50, 1), "p95_ms": round(p95, 1), "p99_ms": round(p99, 1), "max_ms": round(float(arr.max()), 1), "mean_ms": round(float(arr.mean()), 1),
            "throughput_qps": round(done / total, 1) if total > 0 else None, "error_pct": round(err_pct, 2),
            "meets_latency": ok_lat, "meets_errors": ok_err, "verdict": "meets the target" if ok_lat and ok_err else "misses the target",
            "target": {"p95_ms": sla, "max_error_pct": budget},
            "limit": "Requests run one after another inside this process and each loads the model from disk, so this measures the model plus its loading cost on this machine. There is no network, no concurrent users and no stress-to-failure test: a real load test needs a separate tool aimed at the deployed endpoint.",
            "lesson": "Look at p95 and p99, not the average: the slow tail is what users feel and what breaks an SLA. Agree the target with the business before you test, not after."}


# ------------------------------------------------------------------ 5. retrain advice
def retrain_advice(name: str, limit: int = 12) -> dict:
    slug = mr.slug(name)
    live = _live_version(slug)
    hist = _reg(mr.drift_history, slug, live, int(_num(limit, "Readings", 1, 100))) if live is not None else []
    levels = [h["overall"] for h in hist]
    sig = sum(1 for x in levels if x == "significant drift")
    some = sum(1 for x in levels if x == "some drift")
    streak = 0
    for x in reversed(levels):
        if x == "significant drift":
            streak += 1
        else:
            break
    if live is None:
        status, why = "no model", "No version is in production, so there is nothing to retrain yet."
    elif not hist:
        status, why = "no data", "No drift readings are saved yet. Run the drift check (ML Lab -> Models) on a schedule you will actually keep, then come back."
    elif streak >= 2:
        status, why = "investigate", f"The last {streak} readings show significant drift in the inputs."
    elif sig or some >= 3:
        status, why = "watch", f"{sig} significant and {some} moderate readings in the last {len(hist)}."
    else:
        status, why = "stable", f"{len(hist)} reading(s) and no significant drift."
    return {"name": slug, "live_version": live, "status": status, "why": why, "readings": len(hist), "recent": [{"at": h["at"], "overall": h["overall"], "worst": h["worst_feature"], "psi": h["worst_psi"]} for h in hist[-6:]],
            "steps": {
                "investigate": ["Find which input moved (the worst feature) and why: a real change in the business, a new category, or a broken data feed?",
                                "If the world changed, retrain on recent data and run the gate and comparison before promoting.",
                                "If the data broke, fix the feed. Retraining on broken data bakes the break in."],
                "watch": ["Keep the schedule; look again after the next readings."],
                "stable": ["Nothing to do. Retrain on a calendar if the business changes with the seasons."],
                "no data": ["Run the drift check and save readings."], "no model": ["Promote a version first."]}[status],
            "policy": [{"option": "Scheduled", "when": "Fresh data arrives regularly", "note": "The book's advice: start here. Simple and predictable."},
                       {"option": "Triggered by an alert", "when": "You have a monitor you trust", "note": "Add later. Drift tells you the inputs moved, not what to do: retrain, add a feature, or fix a feed?"}],
            "limit": "Only input drift is measured. Drift in the answers, or a drop in real-world accuracy, needs your own outcomes. Don't automate retraining until a person has handled a few alerts by hand."}


# ------------------------------------------------------------------ 6. LLM approach chooser
def llm_plan(a: dict) -> dict:
    if not isinstance(a, dict):
        raise MlopsError("Send your answers as an object.")

    def b(k):
        return bool(a.get(k))
    examples = int(_num(a.get("labeled_examples", 0), "Labeled examples", 0, 1e9))
    volume = _num(a.get("requests_per_day", 100), "Requests per day", 0, 1e9)
    tokens = _num(a.get("corpus_tokens", 0), "Your text corpus (tokens)", 0, 1e15)
    stack = [{"step": "Prompt engineering with a hosted model", "why": "Always the baseline. No training, fast to try, and it tells you what better would have to beat.", "builds_here": "Prompt versions and live tests (AI workbench)."}]
    if b("private_knowledge") or b("knowledge_changes"):
        stack.append({"step": "Retrieval (RAG)", "why": "The model needs facts it was never trained on" + (", and they change, which retraining can't keep up with" if b("knowledge_changes") else "") + ". It also grounds answers and cuts invented ones.",
                      "builds_here": "RAG evaluation with your own questions (AI workbench)."})
    if examples >= 1000 and (b("needs_style") or b("high_volume_cost") or volume >= 50000):
        stack.append({"step": "Fine-tune a smaller model", "why": f"You have about {examples:,} labelled examples and need a consistent behaviour or cheaper calls at {volume:,.0f} requests a day. A small tuned model can match a big general one on one narrow task.",
                      "builds_here": "Nothing: fine-tuning needs GPUs. The workbench can estimate cost and test the result's prompts."})
    elif b("needs_style"):
        stack.append({"step": "Better prompts and examples first", "why": f"Fine-tuning generally needs thousands of examples; you have {examples:,}. Put your best examples in the prompt (few-shot) and revisit when you have more.", "builds_here": "Prompt versions."})
    if tokens >= 1e10 and b("unique_domain"):
        stack.append({"step": "Pre-train (almost never)", "why": "Only for a large, unique corpus (billions of tokens) with a domain or control need nothing else meets. Weeks of GPU time and a team.", "builds_here": "Nothing."})
    hosting, reasons = "Hosted API", ["Fastest start, no GPUs to run, and you pay per use."]
    if b("data_cannot_leave") or b("regulation_blocks_third_party"):
        hosting, reasons = "Self-hosted open model", ["Your rules say the data can't be sent to a third party. That outweighs the convenience of an API."]
    elif b("needs_version_stability"):
        hosting, reasons = "Hosted API with pinned model versions, or self-hosted", ["Hosted models are updated by the vendor and behaviour can shift. Pin a dated version and re-run your tests on each change, or host it yourself."]
    if hosting == "Self-hosted open model" and not b("can_run_gpu"):
        reasons.append("Self-hosting a large model needs GPUs (or heavy quantization with some quality loss). Without them, consider a smaller open model or a vendor offering a private deployment.")
    vec = {"choice": "Keyword search is enough to start", "why": "Under a few thousand short passages, keyword or hybrid search plus good chunking is often adequate and has nothing to run."}
    if b("private_knowledge") and (b("knowledge_changes") or b("needs_filtering")):
        vec = {"choice": "Vector database", "why": "You need to add, update and delete passages and filter by metadata without rebuilding the index."}
    elif b("private_knowledge") and tokens > 5e6:
        vec = {"choice": "Vector library (FAISS-style) or a vector database", "why": "A fixed, large collection can sit in an in-memory index; if it will change, choose a database."}
    return {"stack": stack, "hosting": {"choice": hosting, "reasons": reasons}, "retrieval_store": vec,
            "cost_levers": ["Shorter prompts and answers", "A smaller model for easy requests, a bigger one for hard ones", "Caching repeated questions", "Fine-tune a small model once volume justifies it", "Quantization (lower precision) if you self-host, with a quality check"],
            "evaluation": ["Build 20 to 50 real questions with a 'must include' fact each and re-run them on every change (AI workbench).", "Expect no single right answer for open text: check facts and format, not wording.",
                           "Use a stronger model as a judge only as a screen, and check its verdicts against a human on a sample.", "Collect user feedback from day one (the Feedback tab)."],
            "rule": "Start with the simplest approach that could work, measure it, and add the next layer only when the numbers say so. The techniques combine: a tuned model can still use RAG and a good prompt.",
            "limit": "Rules of thumb from one vendor guide, not a verdict. The thresholds (about a thousand examples to fine-tune, billions of tokens to pre-train) are rough, and models change fast."}


# ------------------------------------------------------------------ 7. feedback log
FEEDBACK_KINDS = {"thumbs_up": ("explicit", 1), "thumbs_down": ("explicit", -1), "accepted": ("implicit", 1), "escalated": ("implicit", -1), "edited": ("implicit", -1)}


def _fkey() -> str:
    return f"mlops_feedback:{workspaces.active()}"


def _fload() -> list[dict]:
    try:
        d = json.loads(state.kv_get(_fkey(), "[]") or "[]")
        return d if isinstance(d, list) else []
    except ValueError:
        return []


def feedback_add(kind: str, prompt: str = "", version: int | None = None, note: str = "") -> dict:
    if kind not in FEEDBACK_KINDS:
        raise MlopsError(f"Kind must be one of: {', '.join(FEEDBACK_KINDS)}.")
    p = str(prompt or "").strip()[:50]
    if version is not None:
        version = int(_num(version, "Version", 1, 1000))
    rows = _fload()
    rows.append({"at": state.now(), "kind": kind, "prompt": p, "version": version, "note": str(note or "").strip()[:200]})
    rows = rows[-MAX_FEEDBACK:]
    state.kv_set(_fkey(), json.dumps(rows))
    return {"saved": True, "total": len(rows)}


def feedback_summary() -> dict:
    rows = _fload()
    groups: dict[str, dict] = {}
    for r in rows:
        key = f"{r['prompt'] or '(no prompt named)'} v{r['version']}" if r.get("version") else (r["prompt"] or "(no prompt named)")
        g = groups.setdefault(key, {"prompt": key, "good": 0, "bad": 0})
        if FEEDBACK_KINDS[r["kind"]][1] > 0:
            g["good"] += 1
        else:
            g["bad"] += 1
    out = []
    for g in groups.values():
        n = g["good"] + g["bad"]
        out.append({**g, "n": n, "helpful_pct": round(100 * g["good"] / n, 1), "enough": n >= 20,
                    "note": "" if n >= 20 else "Fewer than 20 signals: the rate is a hint, not a result."})
    out.sort(key=lambda x: -x["n"])
    return {"total": len(rows), "groups": out, "recent": rows[-8:][::-1],
            "kinds": {k: {"type": v[0], "signal": "good" if v[1] > 0 else "bad"} for k, v in FEEDBACK_KINDS.items()},
            "lesson": "Explicit feedback (thumbs) is clear but rare; implicit feedback (asked for a human, edited the answer) is common but ambiguous. Use both and read them together.",
            "limit": "A hand-kept log capped at 500 entries. Don't put personal details in the note; it is stored as written."}


def feedback_clear() -> dict:
    state.kv_set(_fkey(), "[]")
    state.audit("mlops_feedback_clear", "")
    return {"cleared": True}


# ------------------------------------------------------------------ reference
HIERARCHY = [
    {"term": "MLOps", "meaning": "DataOps + DevOps + ModelOps: the processes and automation for managing data, code and models so ML keeps performing."},
    {"term": "Deploy code", "meaning": "Training code moves dev -> staging -> prod and the model is trained in prod on production data. The book's default for most cases."},
    {"term": "Deploy models", "meaning": "The model is trained in dev and the artifact is promoted. Fits one-off or very expensive training, but the inference and monitoring code needs its own path."},
    {"term": "Champion / challenger", "meaning": "Named aliases for the version serving traffic and the candidate that must beat it. An alias moves; a version number never does."},
    {"term": "Inference table", "meaning": "A log of every request and response from a served model, joined later to real outcomes so you can measure quality."},
    {"term": "Online vs offline evaluation", "meaning": "Offline = score on held-out data. Online = watch live behaviour (A/B, canary, shadow)."},
]

ENVIRONMENTS = [
    {"env": "Development", "data": "Read-write on dev, ideally read-only on prod", "code": "Branches; notebooks for exploring, a repo for everything else", "goal": "Explore, train, tune, write the pipelines and tests"},
    {"env": "Staging", "data": "Temporary, cleaned up", "code": "Pull request triggers unit tests, then integration tests that run every pipeline small", "goal": "Prove the code works together before it touches production"},
    {"env": "Production", "data": "Written only by deployed, tested code", "code": "Release branch; few people can change it", "goal": "Train, validate, deploy, serve, monitor, retrain"},
]

PIPELINE = [
    "Develop on a branch", "Pull request: unit tests on the CI runner", "Integration tests in staging (pipelines at small scale)", "Merge", "Cut a release; pipelines deploy to production",
    "Train on production data; log the run", "Validate (format, metadata, thresholds, slices, compliance); attach 'challenger' if it passes",
    "Compare challenger with champion (offline, or online for real-time); promote the winner", "Serve (batch, streaming or real time) from the champion alias",
    "Monitor inputs, outputs and performance; alert", "Retrain on a schedule or when monitoring says so"]

TESTING = [
    {"test": "Unit tests", "checks": "A function does what it says", "when": "Every pull request"},
    {"test": "Integration tests", "checks": "Pipelines work together, at small scale", "when": "Before merge, in staging"},
    {"test": "Deployment readiness", "checks": "Config, dependencies and input shape are right before an endpoint is created", "when": "Before a real-time deploy"},
    {"test": "Load test", "checks": "Latency percentiles, throughput, errors against the agreed SLA", "when": "Before a real-time deploy"},
    {"test": "Stress test", "checks": "What happens when demand is far above normal; does it fail gracefully and recover?", "when": "Before launch, for high-stakes endpoints"}]

LLM_CHANGES = [
    {"change": "Many forms: hosted API, open model, custom fine-tune", "means": "Projects start with a hosted model and may end with a tuned one."},
    {"change": "Prompts are the program", "means": "Version prompts like code. Prompts are model-specific: a new model means re-testing."},
    {"change": "Context from your own data", "means": "A retrieval store enters the stack. Treat the index as an asset with owners and refresh rules."},
    {"change": "Huge models", "means": "GPUs and a cost/quality trade-off become an operations topic."},
    {"change": "No single right answer", "means": "Evaluation needs rubrics, judges and, above all, human feedback built into the product."},
    {"change": "What is promoted", "means": "Often a pipeline (prompt + retrieval + model), not a model file."}]

SLIPS = [
    "Vendor guide. It describes Databricks products (Unity Catalog, Model Serving, Lakehouse Monitoring, MLflow AI Gateway, MosaicML). The principles carry over; the product names and the performance figures (for example p50 overhead under 10 ms and over 25,000 queries a second, and 'the only tool' for monitoring models and data) are the vendor's own claims, not independent measurements.",
    "Dated. It is from late 2023: Llama 2 and 'MLflow AI Gateway' are the examples, and several named tools have since been renamed or replaced. Treat tool names as examples of a role, and check what exists today.",
    "A paragraph is repeated by mistake: the 'Merge code' section under Staging opens with the text from 'Model training development' (data scientists developing the training pipeline), which doesn't belong there.",
    "Fine-tuning is described as updating 'only a small number of weights'. That is true of parameter-efficient methods (LoRA and similar), not of full fine-tuning, which updates all of them.",
    "'Fully automated' promotion is shown as the default flow, but the book itself notes human approval is needed in regulated settings and that automated retraining is hard to do safely. Treat the automation as something you earn, not the starting point.",
    "Embedding-based retrieval is presented as the RAG default. For a small, stable document set, keyword search with good chunking can score as well and is far simpler to run; measure before adding a vector store."]

NOT_BUILT = [
    {"item": "Unity Catalog, Model Serving, Lakehouse Monitoring, Workflows, MLflow, MosaicML", "why": "Closed or cloud products. This app has its own small registry, drift check and load test; the ideas map across."},
    {"item": "Autoscaling, serverless endpoints, GPU serving", "why": "Needs infrastructure this single-process app doesn't have."},
    {"item": "Fine-tuning, LoRA, RLHF, pre-training, quantization", "why": "Need GPUs and training frameworks."},
    {"item": "Vector database or embedding search", "why": "Not embedded. The RAG evaluation uses keyword matching so you can measure before you commit."},
    {"item": "CI/CD pipelines, dev/staging/prod workspaces, asset bundles", "why": "Taught in the Software engineering tab. The Practice and Real workspaces are the nearest thing here, and they are a safety rail, not a deployment pipeline."},
    {"item": "Proving a model is safe, fair or correct", "why": "The gate and comparison catch common mistakes; they are not an audit."}]

NAMING = {
    "book": "<catalog>.<schema>.<model>, for example prod.fraud_detection.fraud_clf, with one catalog per environment.",
    "here": "Workspace (Practice or Real) / model name / version number, with the 'champion' and 'challenger' aliases on top.",
    "tip": "Name models for the job (late_delivery_risk), not the algorithm (random_forest_2), so a better algorithm later keeps the same name and gains a version."}


def reference() -> dict:
    return {"hierarchy": HIERARCHY, "environments": ENVIRONMENTS, "pipeline": PIPELINE, "testing": TESTING, "llm_changes": LLM_CHANGES, "naming": NAMING,
            "slips": SLIPS, "not_built": NOT_BUILT, "feedback_kinds": list(FEEDBACK_KINDS),
            "approach_questions": [{"id": "private_knowledge", "label": "The model must use facts that aren't public (your documents)"},
                                   {"id": "knowledge_changes", "label": "Those facts change often"},
                                   {"id": "needs_style", "label": "I need a very consistent format, tone or behaviour"},
                                   {"id": "high_volume_cost", "label": "Cost per request is a problem at my volume"},
                                   {"id": "data_cannot_leave", "label": "My data may not be sent to a third party"},
                                   {"id": "needs_version_stability", "label": "I need behaviour that doesn't change under me"},
                                   {"id": "can_run_gpu", "label": "I can run GPUs"},
                                   {"id": "needs_filtering", "label": "I need to filter retrieved passages by metadata"},
                                   {"id": "unique_domain", "label": "My domain/text is unlike what public models saw"}]}
