"""Decides WHICH model answers a question, and spreads usage across your three API keys.

Policy (edit ORDER and DEFAULT_LIMITS to taste):
  simple questions   Google Gemini first (free tier), then OpenAI, then Claude
  medium questions   OpenAI first (comparisons, trends, summaries, drafts), then Gemini, then Claude
  complex / code     Claude first (best at multi-step reasoning and code), then OpenAI, then Gemini
Rules that spread the load:
  * a provider is skipped when it has no key, no installed SDK, or has used up its daily cap
  * if a provider errors (rate limit, bad key, outage) the next one in the order is tried automatically
  * you can always force one provider from the UI
Daily counters live in memory: they reset when the backend restarts (fine for a learning lab; use a table for production).
"""
from __future__ import annotations

import os
import re
import threading
from datetime import datetime, timezone

from app.services import ai_agent, providers
from app.services.ai_agent import AiError, AskResult

ORDER = {"simple": ["google", "openai", "anthropic"], "medium": ["openai", "google", "anthropic"], "complex": ["anthropic", "openai", "google"]}
DEFAULT_LIMITS = {"google": 200, "openai": 100, "anthropic": 40}   # questions per UTC day, override with BI_LIMIT_<PROVIDER>

_lock = threading.Lock()
_usage: dict[str, list] = {}      # provider -> [utc_date, count]

COMPLEX_HINTS = re.compile(
    r"\b(code|script|function|python|debug|refactor|regression|correlat\w*|forecast\w*|predict\w*|statistic\w*|"
    r"significan\w*|outlier\w*|root cause|why|step[- ]by[- ]step|seasonal\w*|cohort\w*|window function|"
    r"analy[sz]e\w*|analysis|assess\w*|evaluat\w*|trade-?offs?|strateg\w*|optimi[sz]\w*|diagnos\w*|simulat\w*|scenario\w*|"
    r"architect\w*|critique|justify|prove)\b", re.I)
MEDIUM_HINTS = re.compile(
    r"\b(compar\w*|trend\w*|versus|vs|breakdown|break down|rank\w*|top \d+|summar\w*|explain|average|per|share|percent\w*|ratio|growth|change[sd]?|"
    r"draft|suggest\w*|plan|recommend\w*|list|prioriti[sz]\w*|review|improve\w*)\b", re.I)


def classify(question: str, effort: str = "auto") -> tuple[str, str]:
    """Return ("simple" | "medium" | "complex", reason)."""
    if effort in ("simple", "medium", "complex"):
        return effort, "chosen by you"
    q = question or ""
    m = COMPLEX_HINTS.search(q)
    if m:
        return "complex", f"mentions '{m.group(0).lower()}'"
    if len(q) > 240 or q.count("?") > 1 or len(re.findall(r"\b(and|then|also)\b", q, re.I)) >= 3:
        return "complex", "long or multi-part question"
    m = MEDIUM_HINTS.search(q)
    if m:
        return "medium", f"mentions '{m.group(0).lower()}'"
    if len(q) > 110 or len(re.findall(r"\b(and|then|also)\b", q, re.I)) >= 1:
        return "medium", "a bit longer than a one-liner"
    return "simple", "short, direct question"


def limit_for(provider: str) -> int:
    try:
        return int(os.environ.get(f"BI_LIMIT_{provider.upper()}", DEFAULT_LIMITS[provider]))
    except ValueError:
        return DEFAULT_LIMITS[provider]


def used_today(provider: str) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    with _lock:
        d, n = _usage.get(provider, [today, 0])
        return n if d == today else 0


def _count(provider: str) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    with _lock:
        d, n = _usage.get(provider, [today, 0])
        _usage[provider] = [today, (n if d == today else 0) + 1]


def reset_usage() -> None:
    with _lock:
        _usage.clear()


def status() -> dict:
    rows = []
    for p, info in providers.INFO.items():
        rows.append({"id": p, "label": info["label"], "configured": bool(providers.api_key(p)),
                     "sdk_installed": providers.sdk_installed(p), "model": providers.model_for(p),
                     "used_today": used_today(p), "daily_limit": limit_for(p), "pip": info["pip"],
                     "key_env": info["keys"][0],
                     "role": "default for simple questions" if p == "google" else
                             "backup" if p == "openai" else "complex questions and code"})
    return {"providers": rows, "ready": [r["id"] for r in rows if r["configured"] and r["sdk_installed"]],
            "max_steps": ai_agent.MAX_STEPS}


def plan(question: str, provider: str = "auto", effort: str = "auto") -> dict:
    """Work out the order to try. Pure function of config + counters, so it is easy to test."""
    st = {r["id"]: r for r in status()["providers"]}
    kind, reason = classify(question, effort)
    if provider != "auto":
        if provider not in st:
            raise AiError(f"Unknown provider '{provider}'.", 400)
        return {"kind": kind, "reason": reason, "order": [provider], "skipped": [], "forced": True}
    order, skipped = [], []
    for p in ORDER[kind]:
        r = st[p]
        if not r["configured"]:
            skipped.append({"provider": p, "why": f"no {r['key_env']}"})
        elif not r["sdk_installed"]:
            skipped.append({"provider": p, "why": f"SDK missing (pip install {r['pip']})"})
        elif r["used_today"] >= r["daily_limit"]:
            skipped.append({"provider": p, "why": f"daily cap of {r['daily_limit']} reached"})
        else:
            order.append(p)
    return {"kind": kind, "reason": reason, "order": order, "skipped": skipped, "forced": False}


def ask(question: str, provider: str = "auto", effort: str = "auto", adapters: dict | None = None) -> AskResult:
    """Route, call, fall back. `adapters` lets tests supply fake adapters per provider."""
    pl = plan(question, provider, effort)
    if not pl["order"]:
        why = "; ".join(f"{s['provider']}: {s['why']}" for s in pl["skipped"])
        raise AiError(f"No AI provider is ready ({why}). Add a key to backend/.env and restart the backend.", 503)
    attempts = [{"provider": s["provider"], "ok": False, "error": s["why"], "skipped": True} for s in pl["skipped"]]
    last: AiError | None = None
    for p in pl["order"]:
        try:
            adapter = adapters[p] if adapters and p in adapters else providers.ADAPTERS[p]()
        except ImportError:
            attempts.append({"provider": p, "ok": False, "error": f"SDK missing (pip install {providers.INFO[p]['pip']})"})
            last = AiError(f"{providers.INFO[p]['label']} SDK isn't installed.", 501)
            continue
        _count(p)
        try:
            res = ai_agent.ask(question, adapter=adapter)
        except AiError as e:
            attempts.append({"provider": p, "ok": False, "error": str(e)})
            last = e
            continue
        attempts.append({"provider": p, "ok": True, "error": ""})
        res.attempts, res.provider = attempts, p
        res.route = {"kind": pl["kind"], "reason": pl["reason"], "forced": pl["forced"]}
        return res
    raise AiError("Every provider failed: " + " | ".join(f"{a['provider']}: {a['error']}" for a in attempts if not a.get("skipped")),
                  last.status if last else 502)


def complete(system: str, prompt: str, effort: str = "medium", provider: str = "auto", adapters: dict | None = None) -> dict:
    """One plain-text answer, no tools and no data access: the model only sees what is in `prompt`.
    Used for writing short briefs from numbers the app already computed. Same routing, caps and fallback as ask()."""
    pl = plan(prompt, provider, effort)
    if not pl["order"]:
        why = "; ".join(f"{s['provider']}: {s['why']}" for s in pl["skipped"])
        raise AiError(f"No AI provider is ready ({why}). Add a key to backend/.env and restart the backend.", 503)
    last: AiError | None = None
    for p in pl["order"]:
        try:
            adapter = adapters[p] if adapters and p in adapters else providers.ADAPTERS[p]()
        except ImportError:
            last = AiError(f"{providers.INFO[p]['label']} SDK isn't installed.", 501)
            continue
        _count(p)
        try:
            adapter.start(system, [], prompt)
            turn = adapter.next_turn()
        except providers.ProviderError as e:
            last = AiError(str(e), e.status)
            continue
        except AiError as e:
            last = e
            continue
        text = (turn.text or "").strip()
        if not text:
            last = AiError("The model returned no text.", 502)
            continue
        return {"text": text, "provider": p, "model": adapter.model, "kind": pl["kind"],
                "input_tokens": turn.input_tokens, "output_tokens": turn.output_tokens}
    raise last or AiError("Every provider failed.", 502)
