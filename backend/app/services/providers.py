"""Provider adapters: one agent loop, three model vendors.

Each adapter hides one vendor's message format behind the same three calls:
    start(system, tools, question)      begin a conversation
    next_turn() -> Turn                 call the model once
    add_results(turn, results)          send tool results back

`Turn` is the vendor-neutral shape the agent loop understands, so ai_agent.py never needs to know whether it is talking
to Claude, GPT or Gemini. Study this file to see how the three tool-calling formats differ.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from importlib.util import find_spec


@dataclass
class Call:
    id: str
    name: str
    args: dict


@dataclass
class Turn:
    text: str = ""
    calls: list[Call] = field(default_factory=list)
    cut_off: bool = False          # the model hit its output-token limit
    input_tokens: int = 0
    output_tokens: int = 0


# ---------- registry ----------
INFO = {
    "google": {"label": "Google Gemini", "keys": ("GOOGLE_API_KEY", "GEMINI_API_KEY"), "module": "google.genai",
               "model_env": "BI_GOOGLE_MODEL", "default_model": "gemini-3.5-flash-lite", "pip": "google-genai"},
    "openai": {"label": "OpenAI", "keys": ("OPENAI_API_KEY",), "module": "openai",
               "model_env": "BI_OPENAI_MODEL", "default_model": "gpt-4o-mini", "pip": "openai"},
    "anthropic": {"label": "Anthropic Claude", "keys": ("ANTHROPIC_API_KEY",), "module": "anthropic",
                  "model_env": "BI_AI_MODEL", "default_model": "claude-sonnet-5-5", "pip": "anthropic"},
    # Local model through Ollama: free, private, works offline. "Configured" means BI_OLLAMA_MODEL is set (there is no key).
    "ollama": {"label": "Ollama (local)", "keys": ("BI_OLLAMA_MODEL",), "module": "urllib.request",
               "model_env": "BI_OLLAMA_MODEL", "default_model": "llama3.1", "pip": "(none: install Ollama from ollama.com)"},
}


def api_key(provider: str) -> str | None:
    for k in INFO[provider]["keys"]:
        if os.environ.get(k):
            return os.environ[k]
    return None


def model_for(provider: str) -> str:
    i = INFO[provider]
    return os.environ.get(i["model_env"], i["default_model"])


def sdk_installed(provider: str) -> bool:
    try:
        return find_spec(INFO[provider]["module"].split(".")[0]) is not None and (
            provider != "google" or find_spec("google.genai") is not None)
    except (ImportError, ValueError):
        return False


class ProviderError(Exception):
    """Raised by adapters with a learner-friendly message and an HTTP-ish status."""
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def translate(provider: str, e: Exception) -> ProviderError:
    name, code = type(e).__name__, getattr(e, "status_code", None) or getattr(e, "code", None)
    label, env = INFO[provider]["label"], INFO[provider]["keys"][0]
    if name in ("AuthenticationError", "PermissionDeniedError") or code in (401, 403):
        return ProviderError(f"{label} rejected the API key. Check {env}.", 401)
    if name == "RateLimitError" or code == 429:
        return ProviderError(f"{label} is rate limiting requests (free tiers have tight limits).", 429)
    if name in ("APIConnectionError", "APITimeoutError", "ConnectError", "ReadTimeout"):
        return ProviderError(f"Couldn't reach {label} from the backend. Check the network.", 502)
    if name == "NotFoundError" or code == 404:
        return ProviderError(f"{label} doesn't know the model '{model_for(provider)}'. Set {INFO[provider]['model_env']} to one your account can use.", 400)
    return ProviderError(f"{label} request failed ({name}{f' {code}' if code else ''}).", 502)


# ---------- Anthropic ----------
class AnthropicAdapter:
    provider = "anthropic"

    def __init__(self, client=None, model: str | None = None, max_tokens: int = 1024):
        if client is None:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key("anthropic"), timeout=60.0, max_retries=2)
        self.client, self.model, self.max_tokens = client, model or model_for("anthropic"), max_tokens

    def start(self, system, tools, question):
        self.system, self.tools = system, tools
        self.messages = [{"role": "user", "content": question}]

    def next_turn(self) -> Turn:
        try:
            extra = {"tools": self.tools} if self.tools else {}      # a plain-text call (no tools) must omit the field
            resp = self.client.messages.create(model=self.model, max_tokens=self.max_tokens, system=self.system,
                                               messages=self.messages, **extra)
        except Exception as e:
            raise translate("anthropic", e)
        u = getattr(resp, "usage", None)
        calls = [Call(b.id, b.name, b.input if isinstance(b.input, dict) else {})
                 for b in resp.content if getattr(b, "type", None) == "tool_use"]
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text").strip()
        self._last_content = resp.content
        return Turn(text, calls if resp.stop_reason == "tool_use" else [], resp.stop_reason == "max_tokens",
                    getattr(u, "input_tokens", 0) or 0, getattr(u, "output_tokens", 0) or 0)

    def add_results(self, turn, results):
        self.messages.append({"role": "assistant", "content": self._last_content})
        self.messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": c.id, "content": out, "is_error": err} for c, out, err in results]})


# ---------- OpenAI ----------
class OpenAIAdapter:
    provider = "openai"

    def __init__(self, client=None, model: str | None = None, max_tokens: int = 1024):
        if client is None:
            import openai
            client = openai.OpenAI(api_key=api_key("openai"), timeout=60.0, max_retries=2)
        self.client, self.model, self.max_tokens = client, model or model_for("openai"), max_tokens

    def start(self, system, tools, question):
        self.tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                          "parameters": t["input_schema"]}} for t in tools]
        self.messages = [{"role": "system", "content": system}, {"role": "user", "content": question}]

    def next_turn(self) -> Turn:
        try:
            extra = {"tools": self.tools} if self.tools else {}
            resp = self.client.chat.completions.create(model=self.model, messages=self.messages,
                                                       max_completion_tokens=self.max_tokens, **extra)
        except Exception as e:
            raise translate("openai", e)
        ch = resp.choices[0]
        msg = ch.message
        calls = []
        for tc in (getattr(msg, "tool_calls", None) or []):
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append(Call(tc.id, tc.function.name, args if isinstance(args, dict) else {}))
        self._assistant = {"role": "assistant", "content": msg.content or None, "tool_calls": [
            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"}}
            for tc in (getattr(msg, "tool_calls", None) or [])]}
        u = getattr(resp, "usage", None)
        return Turn((msg.content or "").strip(), calls, ch.finish_reason == "length",
                    getattr(u, "prompt_tokens", 0) or 0, getattr(u, "completion_tokens", 0) or 0)

    def add_results(self, turn, results):
        self.messages.append(self._assistant)
        for c, out, err in results:
            self.messages.append({"role": "tool", "tool_call_id": c.id, "content": ("ERROR: " + out) if err else out})


# ---------- Google Gemini ----------
class GeminiAdapter:
    provider = "google"

    def __init__(self, client=None, model: str | None = None, max_tokens: int = 1024):
        from google import genai
        if client is None:
            client = genai.Client(api_key=api_key("google"))
        self.client, self.model, self.max_tokens = client, model or model_for("google"), max_tokens

    def start(self, system, tools, question):
        from google.genai import types
        decls = []
        for t in tools:
            props = t["input_schema"].get("properties") or {}
            # Gemini rejects empty object schemas and 'additionalProperties', so build the minimal form.
            params = {"type": "object", "properties": props, "required": t["input_schema"].get("required", [])} if props else None
            decls.append(types.FunctionDeclaration(name=t["name"], description=t["description"], parameters=params))
        self.config = types.GenerateContentConfig(
            system_instruction=system, tools=[types.Tool(function_declarations=decls)] if decls else None, max_output_tokens=self.max_tokens,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        self.contents = [types.Content(role="user", parts=[types.Part.from_text(text=question)])]

    def next_turn(self) -> Turn:
        try:
            resp = self.client.models.generate_content(model=self.model, contents=self.contents, config=self.config)
        except Exception as e:
            raise translate("google", e)
        fcs = list(getattr(resp, "function_calls", None) or [])
        cand = resp.candidates[0] if getattr(resp, "candidates", None) else None
        self._model_content = getattr(cand, "content", None)   # keep whole content: it carries thought signatures
        text = "".join(p.text for p in (getattr(self._model_content, "parts", None) or []) if getattr(p, "text", None)
                       and not getattr(p, "thought", False)).strip()
        u = getattr(resp, "usage_metadata", None)
        reason = str(getattr(cand, "finish_reason", "") or "")
        return Turn(text, [Call(f"g{i}", f.name, dict(f.args or {})) for i, f in enumerate(fcs)],
                    "MAX_TOKENS" in reason.upper(),
                    getattr(u, "prompt_token_count", 0) or 0, getattr(u, "candidates_token_count", 0) or 0)

    def add_results(self, turn, results):
        from google.genai import types
        if self._model_content is not None:
            self.contents.append(self._model_content)
        self.contents.append(types.Content(role="user", parts=[
            types.Part.from_function_response(name=c.name, response={"error": out} if err else {"result": out})
            for c, out, err in results]))


# ---------- Ollama (local) ----------
class OllamaAdapter:
    """Talks to a local Ollama server over its plain HTTP API (no SDK, no key). Tool calling needs a model that supports it
    (for example llama3.1, qwen2.5 or mistral-nemo). Set BI_OLLAMA_MODEL to turn it on and BI_OLLAMA_URL if it isn't on this machine."""
    provider = "ollama"

    def __init__(self, client=None, model: str | None = None, max_tokens: int = 1024):
        self.base = os.environ.get("BI_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
        self.model, self.max_tokens, self._post = model or model_for("ollama"), max_tokens, client or self._http

    def _http(self, path: str, body: dict) -> dict:
        import urllib.error
        import urllib.request
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read(8_000_000))
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = json.loads(e.read(2000)).get("error", "")
            except Exception:  # noqa: BLE001
                pass
            if e.code == 404:
                raise ProviderError(f"Ollama doesn't have the model '{self.model}'. Run: ollama pull {self.model}", 400) from e
            raise ProviderError(f"Ollama answered {e.code}. {detail}"[:200], 502) from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ProviderError(f"Couldn't reach Ollama at {self.base}. Is it running? (start the Ollama app, or run: ollama serve)", 502) from e

    def start(self, system, tools, question):
        self.tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}} for t in tools]
        self.messages = [{"role": "system", "content": system}, {"role": "user", "content": question}]

    def next_turn(self) -> Turn:
        body = {"model": self.model, "messages": self.messages, "stream": False, "options": {"num_predict": self.max_tokens}}
        if self.tools:
            body["tools"] = self.tools
        resp = self._post("/api/chat", body)
        msg = resp.get("message") or {}
        calls = []
        for i, tc in enumerate(msg.get("tool_calls") or []):
            fn = tc.get("function") or {}
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            calls.append(Call(f"ollama-{len(self.messages)}-{i}", str(fn.get("name", "")), args if isinstance(args, dict) else {}))
        self._assistant = {"role": "assistant", "content": msg.get("content") or "", **({"tool_calls": msg["tool_calls"]} if msg.get("tool_calls") else {})}
        return Turn((msg.get("content") or "").strip(), calls, resp.get("done_reason") == "length",
                    int(resp.get("prompt_eval_count") or 0), int(resp.get("eval_count") or 0))

    def add_results(self, turn, results):
        self.messages.append(self._assistant)
        for c, out, err in results:
            self.messages.append({"role": "tool", "tool_name": c.name, "content": ("ERROR: " + out) if err else out})


ADAPTERS = {"google": GeminiAdapter, "openai": OpenAIAdapter, "anthropic": AnthropicAdapter, "ollama": OllamaAdapter}
