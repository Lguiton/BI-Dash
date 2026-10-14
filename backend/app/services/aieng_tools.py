"""AI engineering tools: eval runner, prompt library with versions, LLM cost estimator, AI risk register, and a handoff pack.

Evals score the answers an assistant gave against rules you wrote (must say, must not say, pattern, length). Scores show the pass rate and what changed since the last run.
Prices are example numbers you edit to match your provider's current price list."""
from __future__ import annotations

import difflib
import html
import json
import re
import time
import uuid

from app.services import llm_router, state, workspaces

E = html.escape
CHECKS = ("contains", "not_contains", "regex", "max_words", "min_words", "equals")


class AiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _key(name: str) -> str:
    return f"aieng:{name}:{workspaces.active()}"


def _load(name: str, default: dict) -> dict:
    raw = state.kv_get(_key(name))
    d = json.loads(raw) if raw else {}
    for k, v in default.items():
        d.setdefault(k, v)
    return d


def _save(name: str, d: dict) -> None:
    state.kv_set(_key(name), json.dumps(d))


def _t(v, n) -> str:
    return re.sub(r"[\x00-\x08\x0b-\x1f]", " ", str(v or "")).strip()[:n]


# ------------------------------------------------------------------ eval runner
def _clean_cases(cases) -> list[dict]:
    if not isinstance(cases, list) or not cases:
        raise AiError("Add at least one test case.")
    out = []
    for i, c in enumerate(cases[:60], 1):
        prompt = _t(c.get("prompt"), 2000)
        if not prompt:
            raise AiError(f"Case {i} needs a prompt.")
        checks = []
        for k in (c.get("checks") or [])[:10]:
            t, v = k.get("type"), _t(k.get("value"), 300)
            if t not in CHECKS:
                raise AiError(f"Check type must be one of: {', '.join(CHECKS)}.")
            if t == "regex":
                if len(v) > 150 or re.search(r"\([^)]*[+*]\)[+*{]", v):
                    raise AiError("That pattern is too long or too complex. Keep it simple.")
                try:
                    re.compile(v)
                except re.error as e:
                    raise AiError(f"Bad pattern in case {i}: {e}.") from None
            if t in ("max_words", "min_words"):
                try:
                    v = str(int(float(v)))
                except ValueError:
                    raise AiError("Word limits must be numbers.") from None
            checks.append({"type": t, "value": v})
        if not checks:
            raise AiError(f"Case {i} needs at least one check, or there is nothing to score.")
        out.append({"id": c.get("id") or f"c{i}", "prompt": prompt, "checks": checks})
    return out


def eval_save(name: str, cases: list[dict], system_prompt: str = "", sid: str | None = None) -> dict:
    nm = _t(name, 80)
    if not nm:
        raise AiError("Name the test suite.")
    d = _load("evals", {"suites": {}})
    sid = sid or uuid.uuid4().hex[:8]
    old = d["suites"].get(sid, {})
    d["suites"][sid] = {"id": sid, "name": nm, "system_prompt": _t(system_prompt, 4000), "cases": _clean_cases(cases), "runs": old.get("runs", [])}
    _save("evals", d)
    return {"id": sid, "name": nm, "cases": len(d["suites"][sid]["cases"])}


def eval_list() -> list[dict]:
    return [{"id": s["id"], "name": s["name"], "cases": len(s["cases"]), "runs": len(s["runs"]), "last": s["runs"][-1]["pass_rate"] if s["runs"] else None} for s in _load("evals", {"suites": {}})["suites"].values()]


def eval_get(sid: str) -> dict:
    s = _load("evals", {"suites": {}})["suites"].get(sid)
    if not s:
        raise AiError("No test suite with that id.", 404)
    return s


def eval_delete(sid: str) -> dict:
    d = _load("evals", {"suites": {}})
    if sid not in d["suites"]:
        raise AiError("No test suite with that id.", 404)
    d["suites"].pop(sid)
    _save("evals", d)
    return {"deleted": sid}


def _check(c: dict, text: str) -> tuple[bool, str]:
    t, v = c["type"], c["value"]
    low, words = text.lower(), len(text.split())
    if t == "contains":
        return v.lower() in low, f"should contain '{v}'"
    if t == "not_contains":
        return v.lower() not in low, f"should not contain '{v}'"
    if t == "regex":
        return bool(re.search(v, text, re.I)), f"should match pattern {v}"
    if t == "max_words":
        return words <= int(v), f"should be at most {v} words (was {words})"
    if t == "min_words":
        return words >= int(v), f"should be at least {v} words (was {words})"
    return text.strip().lower() == v.lower(), f"should equal '{v}'"


def eval_score(sid: str, outputs: dict, label: str = "") -> dict:
    d = _load("evals", {"suites": {}})
    s = d["suites"].get(sid)
    if not s:
        raise AiError("No test suite with that id.", 404)
    results, passed = [], 0
    for c in s["cases"]:
        txt = str(outputs.get(c["id"], ""))[:8000]
        if not txt.strip():
            results.append({"id": c["id"], "prompt": c["prompt"][:120], "pass": False, "failed": ["no answer was given"]})
            continue
        fails = [why for ok, why in (_check(k, txt) for k in c["checks"]) if not ok]
        passed += not fails
        results.append({"id": c["id"], "prompt": c["prompt"][:120], "pass": not fails, "failed": fails, "answer": txt[:400]})
    run = {"at": time.strftime("%Y-%m-%d %H:%M"), "label": _t(label, 60) or f"Run {len(s['runs']) + 1}", "pass_rate": round(100 * passed / len(s["cases"]), 1), "passed": passed, "total": len(s["cases"]), "results": results}
    s["runs"] = (s["runs"] + [run])[-20:]
    _save("evals", d)
    return {**run, "compare": eval_compare(sid, s)}


def eval_run_live(sid: str, label: str = "", provider: str = "auto", adapters: dict | None = None) -> dict:
    s = eval_get(sid)
    if len(s["cases"]) > 30:
        raise AiError("Live runs are limited to 30 cases so one click can't use up your quota. Split the suite or paste the answers yourself.")
    outs = {}
    for c in s["cases"]:
        try:
            r = llm_router.complete(s["system_prompt"] or "You are a helpful assistant.", c["prompt"], effort="low", provider=provider, adapters=adapters)
            outs[c["id"]] = r.get("text", "") if isinstance(r, dict) else str(r)
        except Exception as e:  # noqa: BLE001 - surface the provider problem plainly
            raise AiError(f"The AI provider could not answer: {getattr(e, 'message', str(e))[:200]}. You can still paste answers and score them.", 503) from None
    return eval_score(sid, outs, label)


def eval_compare(sid: str, s: dict | None = None) -> dict | None:
    s = s or eval_get(sid)
    if len(s["runs"]) < 2:
        return None
    a, b = s["runs"][-2], s["runs"][-1]
    pa = {r["id"]: r["pass"] for r in a["results"]}
    pb = {r["id"]: r["pass"] for r in b["results"]}
    reg = [i for i in pb if pa.get(i) and not pb[i]]
    fixed = [i for i in pb if pa.get(i) is False and pb[i]]
    return {"from": a["label"], "to": b["label"], "change_points": round(b["pass_rate"] - a["pass_rate"], 1), "regressed": reg, "fixed": fixed,
            "says": f"{b['label']} passes {b['pass_rate']}% against {a['pass_rate']}% for {a['label']}. {len(reg)} case(s) got worse and {len(fixed)} got better." + (" Check the ones that got worse before you ship this change." if reg else "")}


# ------------------------------------------------------------------ prompt library
def prompt_save(name: str, text: str, note: str = "") -> dict:
    nm = re.sub(r"[^A-Za-z0-9 _.\-]", "", _t(name, 60)).strip()
    tx = _t(text, 8000)
    if not nm or not tx:
        raise AiError("Give the prompt a name and some text.")
    d = _load("prompts", {"items": {}})
    h = d["items"].setdefault(nm, [])
    if h and h[-1]["text"] == tx:
        raise AiError("That is identical to the latest version, so nothing was saved.")
    h.append({"v": len(h) + 1, "text": tx, "note": _t(note, 200), "at": time.strftime("%Y-%m-%d %H:%M")})
    _save("prompts", d)
    return {"name": nm, "version": h[-1]["v"]}


def prompt_list() -> list[dict]:
    return [{"name": n, "versions": len(h), "latest": h[-1]["at"], "note": h[-1]["note"]} for n, h in _load("prompts", {"items": {}})["items"].items()]


def prompt_get(name: str) -> list[dict]:
    h = _load("prompts", {"items": {}})["items"].get(name)
    if not h:
        raise AiError("No prompt with that name.", 404)
    return h


def prompt_diff(name: str, v1: int, v2: int) -> dict:
    h = prompt_get(name)
    try:
        a, b = h[int(v1) - 1], h[int(v2) - 1]
    except (IndexError, ValueError):
        raise AiError("Pick two versions that exist.") from None
    diff = list(difflib.unified_diff(a["text"].splitlines(), b["text"].splitlines(), f"v{v1}", f"v{v2}", lineterm="", n=1))
    return {"from": v1, "to": v2, "diff": diff, "changed": bool(diff)}


def prompt_delete(name: str) -> dict:
    d = _load("prompts", {"items": {}})
    if name not in d["items"]:
        raise AiError("No prompt with that name.", 404)
    d["items"].pop(name)
    _save("prompts", d)
    return {"deleted": name}


# ------------------------------------------------------------------ cost estimator
TIERS = {"small": (0.25, 1.25), "medium": (3.0, 15.0), "large": (15.0, 75.0)}


def cost(requests_per_day: float, in_tokens: float, out_tokens: float, tier: str = "medium", price_in: float | None = None, price_out: float | None = None, retry_pct: float = 5, days: int = 30, extra_context_tokens: float = 0) -> dict:
    try:
        rpd, ti, to, rp, dd, ex = float(requests_per_day), float(in_tokens), float(out_tokens), float(retry_pct), int(days), float(extra_context_tokens)
    except (TypeError, ValueError):
        raise AiError("All inputs must be numbers.") from None
    if rpd <= 0 or ti < 0 or to < 0 or not 0 <= rp <= 100 or not 1 <= dd <= 31 or ex < 0:
        raise AiError("Check the inputs: requests above 0, tokens not negative, retries 0-100%, days 1-31.")
    if tier not in TIERS and (price_in is None or price_out is None):
        raise AiError("tier must be small, medium or large, or give both prices.")
    pi, po = (float(price_in), float(price_out)) if price_in is not None and price_out is not None else TIERS[tier]
    per = ((ti + ex) * pi + to * po) / 1e6
    mult = 1 + rp / 100
    daily = per * rpd * mult
    return {"per_request": round(per, 5), "per_day": round(daily, 2), "per_month": round(daily * dd, 2), "per_month_at_3x": round(daily * dd * 3, 2), "per_1000_requests": round(per * 1000 * mult, 2),
            "prices_used": {"input_per_million": pi, "output_per_million": po, "label": "example prices" if price_in is None else "your prices"},
            "arithmetic": [f"Per request = ({ti + ex:g} input tokens x ${pi:g} + {to:g} output tokens x ${po:g}) / 1,000,000 = ${per:.5f}", f"Per day = ${per:.5f} x {rpd:g} requests x {mult:.2f} (retries) = ${daily:.2f}"],
            "tips": ["Shorter prompts and answers cost less: every token is billed.", "Use a smaller model for easy steps and the larger one only when needed.", "Cache or reuse answers to questions that repeat."],
            "caution": "The prices here are examples. Enter your provider's current prices for a real quote. Tokens are about 4 characters or 0.75 words each, and chat history is re-sent on every request."}


def tokens_from_words(words: float) -> int:
    return int(round(float(words) / 0.75))


# ------------------------------------------------------------------ risk register
DEFAULT_RISKS = [
    ("Wrong answers stated confidently (hallucination)", 4, 4, "Show sources, add evals, and keep a person in the loop for decisions."),
    ("Private data sent to a vendor", 3, 5, "Strip personal data first; check the vendor's data-use terms; use a local model for sensitive text."),
    ("Prompt injection (text in a document or web page tells the assistant what to do)", 3, 4, "Treat outside text as data, limit what tools it can use, confirm before any action."),
    ("Biased or unfair results for some groups", 2, 4, "Test on varied examples; review decisions that affect people."),
    ("Costs grow faster than expected", 3, 3, "Set a monthly cap, log usage, alert at 80%."),
    ("Vendor change or outage breaks the product", 3, 3, "Keep prompts portable, add a fallback provider, test after each model update."),
    ("Staff trust it too much", 3, 3, "Label AI output, train staff on limits, require review for high-impact steps."),
]


def risk_register(system: str, risks: list[dict] | None = None, owner: str = "") -> str:
    rs = risks or [{"risk": r, "likelihood": l, "impact": i, "mitigation": m, "owner": owner} for r, l, i, m in DEFAULT_RISKS]
    rows = []
    for r in rs[:60]:
        try:
            l, i = int(r["likelihood"]), int(r["impact"])
        except (KeyError, TypeError, ValueError):
            raise AiError("Likelihood and impact must be whole numbers from 1 to 5.") from None
        if not (1 <= l <= 5 and 1 <= i <= 5):
            raise AiError("Likelihood and impact must be from 1 to 5.")
        rows.append((l * i, l, i, _t(r.get("risk"), 200), _t(r.get("mitigation"), 300), _t(r.get("owner"), 60)))
    rows.sort(key=lambda x: -x[0])
    band = lambda s: ("High", "#fee2e2") if s >= 15 else ("Medium", "#fef3c7") if s >= 8 else ("Low", "#dcfce7")  # noqa: E731
    body = "".join(f"<tr style='background:{band(s)[1]}'><td>{E(r)}</td><td>{l}</td><td>{i}</td><td>{s} ({band(s)[0]})</td><td>{E(m)}</td><td>{E(o)}</td></tr>" for s, l, i, r, m, o in rows)
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>AI risk register</title><style>body{{font-family:system-ui,sans-serif;max-width:980px;margin:24px auto;padding:0 16px}}table{{border-collapse:collapse;width:100%;font-size:13px}}"
            f"td,th{{border:1px solid #ccc;padding:6px;text-align:left;vertical-align:top}}th{{background:#f3f4f6}}</style></head><body><h1>AI risk register: {E(_t(system, 100) or 'AI system')}</h1>"
            f"<p>Score = likelihood x impact (each 1 to 5). Review every quarter or after any change to the system.</p><table><tr><th>Risk</th><th>Likelihood</th><th>Impact</th><th>Score</th><th>What reduces it</th><th>Owner</th></tr>{body}</table>"
            "<p style='font-size:12px;color:#555'>A starting list, not a complete assessment. Add risks specific to the client's data and users.</p></body></html>")


# ------------------------------------------------------------------ handoff pack
def handoff(f: dict) -> str:
    g = lambda k, n=600: E(_t(f.get(k), n)) or "<i>not filled in</i>"  # noqa: E731
    runs = ""
    if f.get("suite_id"):
        try:
            s = eval_get(f["suite_id"])
            if s["runs"]:
                r = s["runs"][-1]
                runs = f"<p>Last evaluation: <b>{r['pass_rate']}%</b> of {r['total']} test cases passed on {E(r['at'])}.</p>"
        except AiError:
            pass
    tools = "".join(f"<li>{E(_t(t, 120))}</li>" for t in (f.get("tools") or [])[:20]) or "<li><i>none</i></li>"
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Handoff: {g('name', 80)}</title><style>body{{font-family:system-ui,sans-serif;max-width:760px;margin:24px auto;padding:0 16px}}h2{{font-size:15px;border-bottom:1px solid #ccc;margin-top:20px}}pre{{background:#f3f4f6;padding:8px;white-space:pre-wrap}}</style></head><body>"
            f"<h1>{g('name', 80)}: handoff pack</h1><p>Owner: {g('owner', 80)} &middot; Built {time.strftime('%Y-%m-%d')}</p>"
            f"<h2>What it is for</h2><p>{g('purpose')}</p><h2>Who uses it</h2><p>{g('users')}</p><h2>Model and provider</h2><p>{g('model', 120)}</p>"
            f"<h2>Instructions it follows (system prompt)</h2><pre>{g('system_prompt', 4000)}</pre><h2>Tools and data it can reach</h2><ul>{tools}</ul>"
            f"<h2>What it must not do</h2><p>{g('limits')}</p><h2>How it is tested</h2><p>{g('testing')}</p>{runs}<h2>Cost</h2><p>{g('cost', 300)}</p>"
            f"<h2>Monitoring and care</h2><p>{g('monitoring')}</p><ul><li>Re-run the tests after any change to the prompt or model.</li><li>Check cost and errors weekly for the first month, then monthly.</li><li>Review the risk register each quarter.</li></ul>"
            "<h2>If it goes wrong</h2><p>Switch the assistant off, tell the owner, keep the conversation logs, and fix the cause before turning it back on.</p></body></html>")
