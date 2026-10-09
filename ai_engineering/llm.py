"""One tiny seam between your code and language models (Gemini, OpenAI, Claude, or an offline stub).

    from llm import complete
    text = complete(system="...", prompt="...")                 # simple task: Gemini -> OpenAI -> Claude
    text = complete(system="...", prompt="...", kind="complex") # hard task / code: Claude -> OpenAI -> Gemini

Keys are read from environment variables or ../backend/.env (the same file the dashboard uses):
GOOGLE_API_KEY (or GEMINI_API_KEY), OPENAI_API_KEY, ANTHROPIC_API_KEY. Models can be changed with
BI_GOOGLE_MODEL, BI_OPENAI_MODEL, BI_AI_MODEL.

With no keys at all (or BI_OFFLINE=1) it uses `offline_model`, a deterministic rule-based stand-in, so every exercise still runs and every
test is repeatable. It is NOT intelligent: it lets you practise the plumbing (parsing, validation, retries, evals) for free.
Keeping the model behind one function is itself a lesson: it makes your code testable and the model replaceable.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Callable

try:  # share the dashboard's keys file if python-dotenv is installed
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")
except ImportError:
    pass

ORDER = {"simple": ["google", "openai", "anthropic"], "complex": ["anthropic", "openai", "google"]}
KEYS = {"google": ("GOOGLE_API_KEY", "GEMINI_API_KEY"), "openai": ("OPENAI_API_KEY",), "anthropic": ("ANTHROPIC_API_KEY",)}
MODELS = {"google": ("BI_GOOGLE_MODEL", "gemini-2.5-flash"), "openai": ("BI_OPENAI_MODEL", "gpt-4o-mini"),
          "anthropic": ("BI_AI_MODEL", "claude-sonnet-5-5")}
MODEL = MODELS["anthropic"][1]            # kept for older scripts
OFFLINE_HANDLERS: list[tuple[re.Pattern, Callable[[re.Match, str], str]]] = []
last_provider = "offline"                 # which backend answered the most recent call


def _key(p: str) -> str | None:
    if os.environ.get("BI_OFFLINE"):          # force the stub (the tests set this so they never spend money)
        return None
    return next((os.environ[k] for k in KEYS[p] if os.environ.get(k)), None)


def model_for(p: str) -> str:
    env, default = MODELS[p]
    return os.environ.get(env, default)


def available() -> list[str]:
    """Providers that have a key set (the SDK is imported lazily when used)."""
    return [p for p in KEYS if _key(p)]


def live() -> bool:
    return bool(available())


def offline(pattern: str):
    """Register a stub answer for prompts matching `pattern` (each exercise teaches the stub its own task)."""
    def deco(fn):
        OFFLINE_HANDLERS.append((re.compile(pattern, re.S | re.I), fn))
        return fn
    return deco


def offline_model(system: str, prompt: str) -> str:
    for pat, fn in OFFLINE_HANDLERS:
        m = pat.search(prompt)
        if m:
            return fn(m, system)
    return "I can't answer that offline."


def call(provider: str, system: str, prompt: str, max_tokens: int = 800) -> str:
    """Call ONE provider. Raises on any failure (complete() decides whether to fall back)."""
    model = model_for(provider)
    if provider == "google":
        from google import genai
        from google.genai import types
        r = genai.Client(api_key=_key("google")).models.generate_content(
            model=model, contents=prompt, config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens))
        return (r.text or "").strip()
    if provider == "openai":
        import openai
        r = openai.OpenAI(api_key=_key("openai")).chat.completions.create(
            model=model, max_completion_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}])
        return (r.choices[0].message.content or "").strip()
    if provider == "anthropic":
        import anthropic
        m = anthropic.Anthropic(api_key=_key("anthropic")).messages.create(
            model=model, max_tokens=max_tokens, system=system, messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in m.content if getattr(b, "type", "") == "text").strip()
    raise ValueError(f"unknown provider {provider}")


def complete(system: str, prompt: str, max_tokens: int = 800, kind: str = "simple", provider: str | None = None) -> str:
    global last_provider
    order = [provider] if provider else [p for p in ORDER[kind] if _key(p)]
    if not order:
        last_provider = "offline"
        return offline_model(system, prompt)
    errors = []
    for p in order:
        try:
            out = call(p, system, prompt, max_tokens)
            last_provider = p
            return out
        except Exception as e:           # rate limit, bad key, missing SDK, outage: try the next provider
            errors.append(f"{p}: {type(e).__name__}")
    raise RuntimeError("every provider failed: " + "; ".join(errors))
