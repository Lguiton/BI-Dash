"""AI engineering workbench: check your own AI work instead of just reading about it.

Six tools. All are free and deterministic except the optional live prompt test, which asks your configured AI provider
and counts against its caps only after you confirm:
  1. context budget  - estimate tokens, see if a prompt fits a window, plan RAG chunking and its cost
  2. RAG evaluation  - score retrieval on your own question/answer pairs and compare chunk sizes
  3. tool safety     - review an agent's tool list for destructive actions and prompt-injection paths
  4. prompt versions - save prompt versions, diff them, compare test results (pasted, or run live with confirmation)
  5. cost planner    - monthly spend from volume, tokens and prices, with caching and routing savings
  6. (templates)     - model card, data card and AI incident templates live in Qual templates

Honest limits: token counts are estimates (real tokenizers differ by model and language); prices and context sizes are
always entered by you because they change; the RAG evaluation uses keyword retrieval, not embeddings; the tool review
finds design risks, it can't prove an agent is safe; pasted prompt tests don't call a model; live prompt tests do, and only on confirmation.
"""
from __future__ import annotations

import difflib
import json
import math
import re
from datetime import datetime, timezone

import numpy as np

from app.services import state, workspaces


class AieError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _n(v, name, lo=0.0, hi=1e12) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise AieError(f"{name} must be a number.") from None
    if not math.isfinite(x) or not lo <= x <= hi:
        raise AieError(f"{name} must be between {lo:g} and {hi:g}.")
    return x


# ------------------------------------------------------------------ 1. context budget
def estimate_tokens(text) -> dict:
    t = str(text or "")
    if len(t) > 2_000_000:
        raise AieError("Text is too long for the estimator (limit 2,000,000 characters).")
    chars, words = len(t), len(re.findall(r"\S+", t))
    by_chars, by_words = chars / 4, words * 1.33
    code = len(re.findall(r"[{}();=<>\[\]]", t)) / max(chars, 1) > 0.04
    est = max(by_chars, by_words) * (1.25 if code else 1.0)
    return {"characters": chars, "words": words, "estimated_tokens": int(math.ceil(est)), "range": [int(est * 0.75), int(est * 1.3)],
            "note": "English prose averages about 4 characters or 0.75 words per token. Code, numbers, and non-English text use more tokens per character." + (" This looks like code, so the estimate is raised." if code else ""),
            "caution": "An estimate, within roughly 25 to 30 percent. For billing or a hard limit use the provider's own token counter."}


def context_fit(prompt_tokens, window_tokens, output_tokens=1000, safety_pct=10) -> dict:
    p, w, o, s = _n(prompt_tokens, "Prompt tokens"), _n(window_tokens, "Context window", 100), _n(output_tokens, "Output tokens"), _n(safety_pct, "Safety margin", 0, 50)
    usable = w * (1 - s / 100)
    need = p + o
    left = usable - need
    notes = []
    if left < 0:
        notes.append(f"Over budget by about {int(-left):,} tokens. Shorten the prompt, retrieve fewer passages, summarise history, or use a larger window.")
    if p > 0.6 * w:
        notes.append("More than 60% of the window is input. Models tend to use the middle of a very long prompt less reliably than its start and end: put key instructions first and the question last, and test retrieval quality at your real length.")
    return {"fits": left >= 0, "prompt_tokens": int(p), "output_tokens": int(o), "usable_tokens": int(usable), "left": int(left), "used_pct": round(100 * need / usable, 1) if usable else None, "notes": notes,
            "lesson": "The context window holds the prompt and the answer together. A bigger window costs more per request and doesn't mean the model uses all of it equally well."}


def chunk_plan(doc_tokens, chunk_tokens=300, overlap_tokens=40, top_k=3, queries_per_day=100, price_in_per_million=0.0, question_tokens=40, system_tokens=200) -> dict:
    d, c, ov, k = _n(doc_tokens, "Document tokens", 1), _n(chunk_tokens, "Chunk size", 20, 100000), _n(overlap_tokens, "Overlap", 0, 100000), int(_n(top_k, "Passages per question", 1, 50))
    q, price, qs, ss = _n(queries_per_day, "Questions per day", 0), _n(price_in_per_million, "Price per million input tokens", 0, 1e6), _n(question_tokens, "Question tokens", 0), _n(system_tokens, "System tokens", 0)
    if ov >= c:
        raise AieError("Overlap must be smaller than the chunk size.")
    n_chunks = max(1, math.ceil((d - ov) / (c - ov)))
    per_query = k * c + qs + ss
    daily = per_query * q
    notes = []
    if c < 100:
        notes.append("Very small chunks lose context: an answer split across two chunks may never be retrieved whole.")
    if c > 800:
        notes.append("Large chunks dilute the match and waste prompt tokens on text that isn't relevant.")
    if ov / c > 0.3:
        notes.append("Overlap above about 30% mostly duplicates text and inflates the index.")
    return {"chunks": n_chunks, "index_growth": round(c / (c - ov), 2), "tokens_per_question": int(per_query), "tokens_per_day": int(daily), "tokens_per_month": int(daily * 30),
            "input_cost_per_month": round(daily * 30 / 1e6 * price, 2), "notes": notes,
            "lesson": "Chunk size is a trade-off: small chunks match precisely but lose context, large chunks keep context but dilute the match and cost more per question. Measure it on your own questions with the RAG evaluation tab."}


# ------------------------------------------------------------------ 2. RAG evaluation
def _chunks(docs, size_chars, overlap_ratio=0.15):
    out = []
    step = max(20, int(size_chars * (1 - overlap_ratio)))
    for di, d in enumerate(docs):
        t = re.sub(r"\s+", " ", str(d)).strip()
        if not t:
            continue
        i = 0
        while i < len(t):
            end = min(len(t), i + size_chars)
            if end < len(t):
                sp = t.rfind(" ", i + size_chars // 2, end)
                end = sp if sp > 0 else end
            out.append({"doc": di, "text": t[i:end].strip()})
            if end >= len(t):
                break
            i = max(end - int(size_chars * overlap_ratio), i + step // 2)
    return out


def rag_eval(docs, cases, chunk_sizes=(200, 400, 800), k=3, min_score=0.12) -> dict:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    if not isinstance(docs, list) or not 1 <= len(docs) <= 50 or not any(str(d).strip() for d in docs):
        raise AieError("Give 1 to 50 documents.")
    if sum(len(str(d)) for d in docs) > 1_000_000:
        raise AieError("Documents are too large for this check (limit 1,000,000 characters).")
    if not isinstance(cases, list) or not 1 <= len(cases) <= 100:
        raise AieError("Give 1 to 100 test questions.")
    sizes = sorted({int(_n(s, "Chunk size", 60, 5000)) for s in chunk_sizes})[:5]
    kk, ms = int(_n(k, "Passages", 1, 10)), _n(min_score, "Minimum score", 0, 1)
    qs = []
    for c in cases:
        if not isinstance(c, dict) or not str(c.get("question", "")).strip():
            raise AieError("Each test needs a question.")
        exp = [str(x).strip().lower() for x in (c.get("expected") or []) if str(x).strip()]
        qs.append({"question": str(c["question"]).strip()[:300], "expected": exp})
    answerable = [q for q in qs if q["expected"]]
    unanswerable = [q for q in qs if not q["expected"]]
    results = []
    for size in sizes:
        ch = _chunks(docs, size)
        if not ch:
            raise AieError("The documents are empty.")
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        try:
            M = vec.fit_transform([c["text"] for c in ch])
        except ValueError:
            raise AieError("The documents contain no usable words.") from None
        hits, rr, rows, abst_ok = 0, [], [], 0
        for q in qs:
            sims = cosine_similarity(vec.transform([q["question"]]), M)[0]
            order = [int(i) for i in np.argsort(-sims)[:kk] if sims[i] > 0]
            top = float(sims[order[0]]) if order else 0.0
            if q["expected"]:
                rank = next((r + 1 for r, i in enumerate(order) if any(p in ch[i]["text"].lower() for p in q["expected"])), None)
                hits += 1 if rank else 0
                rr.append(1 / rank if rank else 0)
                rows.append({"question": q["question"], "kind": "answerable", "found": bool(rank), "rank": rank, "top_score": round(top, 3)})
            else:
                ok = top < ms
                abst_ok += 1 if ok else 0
                rows.append({"question": q["question"], "kind": "unanswerable", "found": ok, "rank": None, "top_score": round(top, 3)})
        results.append({"chunk_chars": size, "chunks": len(ch), "hit_rate": round(hits / len(answerable), 3) if answerable else None, "mrr": round(float(np.mean(rr)), 3) if rr else None,
                        "abstain_rate": round(abst_ok / len(unanswerable), 3) if unanswerable else None, "cases": rows})
    best = max(results, key=lambda r: ((r["hit_rate"] or 0) + (r["abstain_rate"] or 0) * 0.5, -r["chunk_chars"]))
    notes = []
    if len(qs) < 10:
        notes.append("Fewer than 10 questions: the scores swing a lot on each case. Write 20 or more, including ones the documents can't answer.")
    if not unanswerable:
        notes.append("No unanswerable questions. Add some, because a RAG system that always answers will make things up when the source is silent.")
    misses = [r for r in best["cases"] if r["kind"] == "answerable" and not r["found"]]
    if misses:
        notes.append(f"{len(misses)} answerable question(s) were not retrieved at the best size. Often the question uses a different word than the document (keyword retrieval misses synonyms), so rephrase or add the document's wording.")
    return {"sizes": results, "best_chunk_chars": best["chunk_chars"], "answerable": len(answerable), "unanswerable": len(unanswerable), "k": kk, "notes": notes,
            "lesson": "Evaluate retrieval before you blame the model. Hit rate is how often the passage holding the answer was retrieved; MRR rewards ranking it first; abstain rate is how often the system correctly found nothing for a question the documents can't answer.",
            "caution": "Retrieval is keyword weighting (TF-IDF), so synonyms are missed that an embedding model would catch. A hit means the expected phrase appeared in a retrieved passage, not that a model answered correctly."}


# ------------------------------------------------------------------ 3. tool safety review
FLAGS = ("reads_private", "reads_untrusted", "writes", "destructive", "external_send", "confirm", "allowlist", "limit")


def tool_safety(tools) -> dict:
    if not isinstance(tools, list) or not 1 <= len(tools) <= 40:
        raise AieError("Give 1 to 40 tools.")
    rows, names = [], set()
    for t in tools:
        if not isinstance(t, dict) or not str(t.get("name", "")).strip():
            raise AieError("Each tool needs a name.")
        nm = str(t["name"]).strip()[:60]
        if nm in names:
            raise AieError(f"Tool '{nm}' is listed twice.")
        names.add(nm)
        rows.append({"name": nm, **{f: bool(t.get(f)) for f in FLAGS}})
    findings = []

    def add(level, tool, text, fix):
        findings.append({"level": level, "tool": tool, "problem": text, "fix": fix})
    for r in rows:
        n = r["name"]
        if r["destructive"] and not r["confirm"]:
            add("bad", n, "Deletes or overwrites without a human confirmation.", "Require explicit approval, or make it reversible (soft delete, backup first).")
        if r["writes"] and not r["destructive"] and not r["confirm"] and not r["limit"]:
            add("warn", n, "Writes with no approval and no limit on how much.", "Add a per-run cap or a confirmation step for bulk changes.")
        if r["external_send"] and not r["allowlist"]:
            add("bad" if r["reads_private"] else "warn", n, "Sends data outside with no allow-list of destinations.", "Restrict to named recipients or domains. An injected instruction could otherwise send data anywhere.")
        if r["external_send"] and not r["confirm"]:
            add("warn", n, "Sends outside without confirmation.", "Show the message and recipient and ask a person first.")
        if r["reads_untrusted"] and (r["writes"] or r["destructive"] or r["external_send"]):
            add("warn", n, "One tool both reads untrusted content and acts on the world.", "Split reading from acting, so text from a web page or email can't directly trigger an action.")
    priv = [r["name"] for r in rows if r["reads_private"]]
    untr = [r["name"] for r in rows if r["reads_untrusted"]]
    sends = [r["name"] for r in rows if r["external_send"]]
    trifecta = bool(priv and untr and sends)
    if trifecta:
        add("bad", "(whole agent)", f"Private data ({', '.join(priv)}), untrusted content ({', '.join(untr)}) and an outside channel ({', '.join(sends)}) are all available together. A hidden instruction in the untrusted text can read private data and send it out.",
            "Remove one leg: no outside channel, or no untrusted input, or no private data in the same agent. Or require a person to approve every send.")
    elif priv and sends:
        add("warn", "(whole agent)", "Private data and an outside channel are both available.", "Keep sending behind approval and an allow-list.")
    if not any(r["confirm"] for r in rows) and any(r["writes"] or r["destructive"] or r["external_send"] for r in rows):
        add("warn", "(whole agent)", "No tool asks for confirmation.", "Put a human in the loop for anything irreversible or external.")
    score = max(0, 100 - 25 * sum(f["level"] == "bad" for f in findings) - 8 * sum(f["level"] == "warn" for f in findings))
    order = {"bad": 0, "warn": 1}
    return {"tools": len(rows), "findings": sorted(findings, key=lambda f: order[f["level"]]), "score": score, "verdict": "high risk" if score < 50 else "needs work" if score < 85 else "reasonable", "private_untrusted_external_all_present": trifecta,
            "lesson": "Prompt injection works because a model can't reliably tell instructions from data. So design the tools, not just the prompt: limit what each tool can do, keep reading and acting apart, ask a person before anything irreversible or external, and never let private data, untrusted text and an outside channel meet.",
            "caution": "This reviews the design you describe. It can't prove an agent is safe, and a clean result is not permission to skip testing with hostile inputs."}


# ------------------------------------------------------------------ 4. prompt versions
MAX_PROMPTS, MAX_VERSIONS, MAX_LEN = 20, 30, 8000


def _key() -> str:
    return f"aieng_prompts:{workspaces.active()}"


def _load() -> dict:
    raw = state.kv_get(_key())
    return json.loads(raw) if raw else {}


def _name(v) -> str:
    n = str(v or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,49}", n):
        raise AieError("Name the prompt with letters, numbers, spaces, - _ . (up to 50 characters).")
    return n


def prompts() -> dict:
    d = _load()
    return {"prompts": [{"name": k, "versions": [{"v": x["v"], "at": x["at"], "note": x["note"], "chars": len(x["text"]), "tokens": estimate_tokens(x["text"])["estimated_tokens"]} for x in v]} for k, v in sorted(d.items())]}


def prompt_get(name, v) -> dict:
    d = _load()
    nm = _name(name)
    if nm not in d:
        raise AieError("No prompt with that name.")
    hit = next((x for x in d[nm] if x["v"] == int(v)), None)
    if not hit:
        raise AieError("No such version.")
    return hit


def prompt_save(name, text, note="") -> dict:
    nm = _name(name)
    t = str(text or "")
    if not t.strip():
        raise AieError("The prompt is empty.")
    if len(t) > MAX_LEN:
        raise AieError(f"The prompt is too long (limit {MAX_LEN} characters).")
    d = _load()
    if nm not in d and len(d) >= MAX_PROMPTS:
        raise AieError(f"You already have {MAX_PROMPTS} prompts. Delete one first.")
    versions = d.setdefault(nm, [])
    if versions and versions[-1]["text"] == t:
        raise AieError("That is identical to the latest version, so nothing was saved.")
    v = (versions[-1]["v"] + 1) if versions else 1
    versions.append({"v": v, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "note": str(note or "")[:200], "text": t})
    d[nm] = versions[-MAX_VERSIONS:]
    state.kv_set(_key(), json.dumps(d))
    return {"name": nm, "version": v}


def prompt_delete(name) -> dict:
    d = _load()
    nm = _name(name)
    if nm not in d:
        raise AieError("No prompt with that name.")
    del d[nm]
    state.kv_set(_key(), json.dumps(d))
    return {"deleted": nm}


def prompt_diff(name, a, b) -> dict:
    x, y = prompt_get(name, a), prompt_get(name, b)
    diff = list(difflib.unified_diff(x["text"].splitlines(), y["text"].splitlines(), f"v{x['v']}", f"v{y['v']}", lineterm="", n=1))
    added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
    return {"from": x["v"], "to": y["v"], "diff": "\n".join(diff) or "(identical)", "lines_added": added, "lines_removed": removed,
            "token_change": estimate_tokens(y["text"])["estimated_tokens"] - estimate_tokens(x["text"])["estimated_tokens"]}


def _passes(case, out) -> list[str]:
    t = str(out or "")
    low = t.lower()
    fails = []
    for s in case.get("must_include") or []:
        if str(s).lower() not in low:
            fails.append(f"missing '{s}'")
    for s in case.get("must_not_include") or []:
        if str(s).lower() in low:
            fails.append(f"contains '{s}'")
    mc = case.get("max_chars")
    if mc and len(t) > int(mc):
        fails.append(f"longer than {int(mc)} characters")
    if not t.strip():
        fails.append("empty output")
    return fails


def compare_versions(cases, outputs_a, outputs_b) -> dict:
    if not isinstance(cases, list) or not 1 <= len(cases) <= 100:
        raise AieError("Give 1 to 100 test cases.")
    if not isinstance(outputs_a, dict) or not isinstance(outputs_b, dict):
        raise AieError("Give an output for each test id, for each version.")
    rows, reg, fixed = [], [], []
    for c in cases:
        if not isinstance(c, dict) or not str(c.get("id", "")).strip():
            raise AieError("Each test case needs an id.")
        cid = str(c["id"]).strip()
        fa, fb = _passes(c, outputs_a.get(cid)), _passes(c, outputs_b.get(cid))
        rows.append({"id": cid, "a_pass": not fa, "b_pass": not fb, "a_problems": fa, "b_problems": fb})
        if not fa and fb:
            reg.append(cid)
        if fa and not fb:
            fixed.append(cid)
    pa, pb = sum(r["a_pass"] for r in rows), sum(r["b_pass"] for r in rows)
    return {"rows": rows, "a_passed": pa, "b_passed": pb, "total": len(rows), "regressions": reg, "fixed": fixed,
            "verdict": "B is worse: it broke cases that A passed" if reg and len(reg) >= len(fixed) else "B is better" if pb > pa else "no difference" if pb == pa and not reg else "mixed: review the regressions",
            "lesson": "Treat a prompt like code. Keep versions, run the same fixed test cases against each, and look at regressions (cases that passed before and fail now), not just the total.",
            "caution": "These checks look for required and forbidden text in outputs you paste. They can't judge quality, tone or correctness, so read samples of the outputs as well."}


# ---- live prompt tests (calls the real model; asks first)
LIVE_MAX_CASES = 20
LIVE_KEEP = 5
ASSUMED_OUTPUT_TOKENS = 300


def _live_key() -> str:
    return f"aieng_live:{workspaces.active()}"


def _live_inputs(name, a, b, cases):
    ta = prompt_get(name, a)
    tb = prompt_get(name, b) if b not in (None, "", 0) else None
    if not isinstance(cases, list) or not 1 <= len(cases) <= LIVE_MAX_CASES:
        raise AieError(f"Give 1 to {LIVE_MAX_CASES} test cases for a live run.")
    seen, out = set(), []
    for c in cases:
        if not isinstance(c, dict) or not str(c.get("id", "")).strip() or not str(c.get("input", "")).strip():
            raise AieError("Each live test case needs an id and an input to send.")
        cid = str(c["id"]).strip()
        if cid in seen:
            raise AieError(f"Test case '{cid}' is listed twice.")
        seen.add(cid)
        if len(str(c["input"])) > 1500:
            raise AieError(f"The input for '{cid}' is too long (limit 1,500 characters).")
        out.append(c)
    return ta, tb, out


def live_plan(name, a, b, cases) -> dict:
    """What a live run would do and roughly what it would use. Calls nothing."""
    ta, tb, cs = _live_inputs(name, a, b, cases)
    versions = [ta] + ([tb] if tb else [])
    calls = len(cs) * len(versions)
    tin = sum(estimate_tokens(v["text"] + str(c["input"]))["estimated_tokens"] for v in versions for c in cs)
    from app.services import ai_policy, llm_router
    pl = llm_router.plan("test prompt", "auto", "medium")
    return {"calls": calls, "versions": [v["v"] for v in versions], "cases": len(cs), "estimated_input_tokens": tin, "assumed_output_tokens_per_call": ASSUMED_OUTPUT_TOKENS,
            "estimated_output_tokens": calls * ASSUMED_OUTPUT_TOKENS, "ai_allowed": ai_policy.describe()["allowed"],
            "providers_ready": [p for p in pl["order"]], "providers_skipped": [f"{x['provider']}: {x['why']}" for x in pl["skipped"]],
            "warnings": ["A live run sends the prompt text and each test input to your AI provider and counts against your daily caps. Do not put personal or confidential data in test inputs.",
                         "Model output varies from run to run. With few cases, a difference between two versions can be chance: run the same cases more than once before you trust a small gap."]}


def live_run(name, a, b, cases, provider="auto", confirm=False, adapters=None) -> dict:
    from app.services import ai_agent, ai_policy, llm_router
    ta, tb, cs = _live_inputs(name, a, b, cases)
    calls = len(cs) * (2 if tb else 1)
    if not confirm:
        raise AieError(f"A live run makes {calls} real model call(s) and counts against your daily caps. Preview it, then confirm to go ahead.")
    if not ai_policy.describe()["allowed"]:
        raise AieError("AI is switched off for this workspace. Turn it on in Settings, or paste outputs instead.", 403)
    outs: dict[str, dict] = {"a": {}, "b": {}}
    errors, models, aborted = [], set(), None
    for label, ver in (("a", ta), ("b", tb)):
        if ver is None or aborted:
            continue
        for c in cs:
            cid = str(c["id"]).strip()
            try:
                r = llm_router.complete(ver["text"], str(c["input"]), "medium", provider, adapters)
                outs[label][cid] = r["text"]
                models.add(f"{r['provider']}:{r['model']}")
            except ai_agent.AiError as e:
                errors.append({"version": ver["v"], "case": cid, "error": str(e)})
                if getattr(e, "status", 0) in (403, 501, 503):
                    aborted = str(e)
                    break
    cmp = compare_versions(cs, outs["a"], outs["b"] if tb else outs["a"])
    entry = {"at": state.now(), "name": ta and name, "a": ta["v"], "b": tb["v"] if tb else None, "calls": sum(len(v) for v in outs.values()), "models": sorted(models),
             "a_passed": cmp["a_passed"], "b_passed": cmp["b_passed"] if tb else None, "total": cmp["total"], "regressions": cmp["regressions"] if tb else [], "fixed": cmp["fixed"] if tb else [], "errors": errors, "aborted": aborted,
             "outputs_a": {k: v[:600] for k, v in outs["a"].items()}, "outputs_b": {k: v[:600] for k, v in outs["b"].items()}}
    hist = [entry] + live_history()
    state.kv_set(_live_key(), json.dumps(hist[:LIVE_KEEP]))
    state.audit("prompt_live_test", f"{name} v{ta['v']}" + (f" vs v{tb['v']}" if tb else "") + f": {entry['calls']} calls")
    return {**entry, "comparison": cmp if tb else None, "single": None if tb else {"rows": cmp["rows"]},
            "note": "Replies come from a live model and vary between runs. These checks test required and forbidden text and length only; read the replies as well."}


def live_history() -> list:
    raw = state.kv_get(_live_key())
    return json.loads(raw) if raw else []


# ------------------------------------------------------------------ 5. cost planner
def cost_plan(requests_per_day, input_tokens, output_tokens, price_in_per_million, price_out_per_million, cache_hit_pct=0, cache_discount_pct=90, cheap_share_pct=0, cheap_price_in=0, cheap_price_out=0, days=30) -> dict:
    r, i, o = _n(requests_per_day, "Requests per day"), _n(input_tokens, "Input tokens"), _n(output_tokens, "Output tokens")
    pi, po = _n(price_in_per_million, "Input price", 0, 1e6), _n(price_out_per_million, "Output price", 0, 1e6)
    ch, cd, cs = _n(cache_hit_pct, "Cache hit %", 0, 100), _n(cache_discount_pct, "Cache discount %", 0, 100), _n(cheap_share_pct, "Cheap-model share %", 0, 100)
    cpi, cpo, dd = _n(cheap_price_in, "Cheap input price", 0, 1e6), _n(cheap_price_out, "Cheap output price", 0, 1e6), int(_n(days, "Days", 1, 366))
    if cs > 0 and cpi == 0 and cpo == 0:
        raise AieError("Enter the cheaper model's prices to use routing.")
    n = r * dd

    def cost(share_cheap, cache_pct):
        big, small = n * (1 - share_cheap / 100), n * share_cheap / 100
        eff_in = 1 - (cache_pct / 100) * (cd / 100)
        c_big = big * (i / 1e6 * pi * eff_in + o / 1e6 * po)
        c_small = small * (i / 1e6 * cpi * eff_in + o / 1e6 * cpo)
        return c_big + c_small
    base, cached, routed, both = cost(0, 0), cost(0, ch), cost(cs, 0), cost(cs, ch)
    per_req = both / n if n else 0
    return {"requests": int(n), "base": round(base, 2), "with_cache": round(cached, 2), "with_routing": round(routed, 2), "with_both": round(both, 2), "saving": round(base - both, 2),
            "saving_pct": round(100 * (base - both) / base, 1) if base else 0, "per_request": round(per_req, 5), "at_double_volume": round(both * 2, 2),
            "output_share_of_base": round(100 * (n * o / 1e6 * po) / base, 1) if base else 0,
            "notes": ["Output tokens usually cost several times more than input tokens, so shortening answers often saves more than shortening prompts." if po > pi else "Check which side dominates your bill before optimising.",
                      "Caching only helps when the same long prefix repeats (a fixed system prompt or document). Discount and eligibility vary by provider.",
                      "Routing needs a way to decide which requests are easy. Measure quality on the cheap model first, with the prompt tests."],
            "lesson": "Cost = requests × (input tokens × input price + output tokens × output price). The levers are fewer tokens, caching a repeated prefix, and sending easy requests to a cheaper model.",
            "caution": "Prices are what you type in; they change often, so copy current ones from the provider. Excludes retries, tool calls, embeddings, storage and engineering time."}


def reference() -> dict:
    return {"window_examples": [8_000, 32_000, 128_000, 200_000, 1_000_000],
            "window_note": "Example sizes only. Check your model's current limit in the provider's documentation.",
            "tool_flags": [{"id": "reads_private", "label": "Reads private data"}, {"id": "reads_untrusted", "label": "Reads untrusted content (web, email, uploads)"}, {"id": "writes", "label": "Writes or changes data"},
                           {"id": "destructive", "label": "Deletes or overwrites"}, {"id": "external_send", "label": "Sends data outside"}, {"id": "confirm", "label": "Asks a person first"},
                           {"id": "allowlist", "label": "Limited to an allow-list"}, {"id": "limit", "label": "Has a cap or rate limit"}],
            "example_tools": [{"name": "read_inbox", "reads_private": True, "reads_untrusted": True}, {"name": "search_web", "reads_untrusted": True}, {"name": "send_email", "external_send": True}, {"name": "delete_file", "destructive": True}],
            "example_docs": ["Refunds are issued to the original payment method within 5 business days of approval.\n\nShipping is free on orders over $50. Standard delivery takes 3 to 7 business days.", "Support is open Monday to Friday, 9 AM to 6 PM Pacific. Weekend requests are answered the next business day.\n\nTo reset a password, use the Forgot password link on the sign-in page."],
            "example_cases": [{"question": "how long do refunds take", "expected": ["5 business days"]}, {"question": "when is free shipping available", "expected": ["over $50"]}, {"question": "what are the support hours", "expected": ["9 am to 6 pm"]},
                              {"question": "how do I reset my password", "expected": ["forgot password"]}, {"question": "do you ship to the moon", "expected": []}],
            "example_prompt_cases": [{"id": "refund", "input": "How long do refunds take? Policy: refunds are issued within 5 business days.", "must_include": ["5 business days"], "must_not_include": ["guarantee"]}, {"id": "unknown", "input": "Do you ship to the moon? Policy: we ship within the United States.", "must_include": ["don't know"], "max_chars": 300}],
            "checklist": ["Write the success metric and a baseline before you build.", "Keep 20+ test questions including ones the system must refuse or not know.", "Version every prompt and rerun the same tests on each change.", "Log inputs and outputs (minus personal data) so failures can be studied.",
                          "Put a person in the loop for irreversible or external actions.", "Track cost and latency per request, not just per month.", "Plan for the provider changing or retiring a model."],
            "not_built": ["Judging answer quality: live tests check required text, forbidden text and length only. Model output also varies between runs.",
                          "Semantic (embedding) retrieval, vector databases, fine-tuning and quantizing models: these need an embedding model or GPUs.",
                          "Proving an agent safe: the tool review finds design risks only."]}
