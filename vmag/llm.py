"""The `complete()` seam: one text-in/text-out call, many backends.

This is the boundary the rest of VMAG talks to. Nothing above it knows whether a
response came from a frontier model, a local 7B, or a hard-coded string, which is
the point -- the guard's behavior must not depend on which agent it is wrapping,
and the same must be true of the harness that measures it.

Design constraints, in order of how much they matter here:

1. **Standard library only.** No `openai`, no `anthropic`, no `requests`. A
   benchmark that stops reproducing because a vendor SDK changed its interface is
   not a benchmark. Every provider below is reachable over plain HTTP.
2. **Deterministic by default.** `temperature=0`, and every response is cached on
   disk keyed by the exact request. Re-running an evaluation costs nothing and
   returns the same numbers.
3. **Offline reproduction.** `VMAG_LLM_OFFLINE=1` refuses to make a network call
   and serves only from cache, so a published result can be recomputed with no
   credentials and no spend. A cache miss is an error, not a silent live call.
4. **No silent coercion.** A refusal, a truncation, or unparseable output is
   returned as-is and recorded. What a model actually emitted is data.

Backend selection is a single env var:

    VMAG_MODEL=mock                                  offline, deterministic
    VMAG_MODEL=ollama:qwen2.5:7b                     local, free, no key
    VMAG_MODEL=cli:sonnet                            local `claude` CLI, no API key
    VMAG_MODEL=groq:llama-3.3-70b-versatile          free tier, no card
    VMAG_MODEL=gemini:gemini-2.0-flash               free tier, no card
    VMAG_MODEL=anthropic:claude-sonnet-4-5           paid
    VMAG_MODEL=stanford:gpt-4o                       Stanford AI API Gateway (needs a PTA)

Every provider except `anthropic` and `cli` speaks the OpenAI chat-completions
wire format, so they share one adapter and differ only in base URL and key.

**Data provenance is enforced here, not left to discipline.** Controlled-access
records (MIMIC and anything else under a PhysioNet-style DUA) may not be sent to
a third-party endpoint; PhysioNet names Claude and OpenAI explicitly. Passing
`provenance="controlled-access"` to `complete()` therefore refuses every remote
backend, including `cli`, and permits only backends that run on hardware you
control. This project's whole argument is that safety should not depend on someone
choosing to comply, so applying that to its own compliance posture is the
consistent thing to do. See `docs/MODEL_ACCESS.md`.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

DEFAULT_CACHE = os.path.join("outputs", "llm_cache")
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TIMEOUT = 120
RETRIES = 3


@dataclass(frozen=True)
class Provider:
    base_url: str
    key_env: str | None
    wire: str = "openai"          # "openai" | "anthropic"
    base_url_env: str | None = None
    notes: str = ""


# Free tiers below were checked 2026-08-07; rate limits move, so treat the
# comments as orientation rather than a contract.
PROVIDERS: dict[str, Provider] = {
    "ollama": Provider(
        # 127.0.0.1, not localhost: on Windows `localhost` resolves to ::1 and
        # 127.0.0.1, so a refused connection pays two timeouts instead of one
        # (measured 4.13s vs 2.04s). Nothing here needs name resolution.
        "http://127.0.0.1:11434/v1", None,
        base_url_env="OLLAMA_BASE_URL",
        notes="local; no key, no quota, no data leaves the machine",
    ),
    "groq": Provider(
        "https://api.groq.com/openai/v1", "GROQ_API_KEY",
        notes="free tier, no credit card",
    ),
    "gemini": Provider(
        "https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY",
        notes="free tier via the OpenAI-compatible endpoint, no credit card",
    ),
    "nvidia": Provider(
        "https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY",
        notes="free tier, many open-weight models",
    ),
    "openrouter": Provider(
        "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY",
        notes="free-tier models exist; daily cap is low until credits are bought",
    ),
    "cerebras": Provider(
        "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY",
        notes="free tier, generous daily token budget",
    ),
    "stanford": Provider(
        "", "STANFORD_AI_API_KEY",
        base_url_env="STANFORD_AI_BASE_URL",
        notes="Stanford AI API Gateway; OpenAI-compatible, requires a PTA to bill",
    ),
    "anthropic": Provider(
        "https://api.anthropic.com/v1", "ANTHROPIC_API_KEY", wire="anthropic",
        notes="paid",
    ),
    "cli": Provider(
        "", None, wire="cli",
        notes="local `claude` CLI on a subscription; no API key, no temperature control",
    ),
}

# Backends that run on hardware you control. Everything else sends the prompt to
# a third party, which is what a PhysioNet-style DUA forbids for its data.
# `cli` is REMOTE: the binary is local, the inference is not.
LOCAL_BACKENDS = frozenset({"mock", "ollama"})

PROVENANCE = ("synthetic-public", "controlled-access")

# --- claude CLI -------------------------------------------------------------
# Tools are denied so the call is a text completion rather than an agent turn.
CLI_DENIED_TOOLS = (
    "Bash Edit Write Read Glob Grep WebFetch WebSearch Task TodoWrite "
    "NotebookEdit MultiEdit"
)
CLI_TIMEOUT_PAD = 60


class ProvenanceViolation(RuntimeError):
    """Raised when controlled-access content would leave hardware you control."""


@dataclass
class Completion:
    text: str
    backend: str                  # "mock" or "<provider>:<model>"
    cached: bool = False
    error: str | None = None      # transport/HTTP failure, after retries
    raw: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None


class OfflineCacheMiss(RuntimeError):
    """Raised when VMAG_LLM_OFFLINE=1 and the request is not cached."""


# ---------------------------------------------------------------- cache -----
def _cache_key(backend: str, system: str | None, prompt: str,
               temperature: float, max_tokens: int) -> str:
    payload = json.dumps(
        {"backend": backend, "system": system, "prompt": prompt,
         "temperature": temperature, "max_tokens": max_tokens},
        sort_keys=True, ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


class Cache:
    """One JSON file per entry. Plain files so a cache is reviewable in a diff
    and can be committed alongside results -- everything here is synthetic."""

    def __init__(self, root: str = DEFAULT_CACHE):
        self.root = root

    def path(self, key: str) -> str:
        return os.path.join(self.root, f"{key}.json")

    def get(self, key: str) -> dict | None:
        path = self.path(key)
        if not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return None

    def put(self, key: str, record: dict) -> None:
        os.makedirs(self.root, exist_ok=True)
        with open(self.path(key), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(record, fh, indent=1, ensure_ascii=True, sort_keys=True)


# ------------------------------------------------------------- transport ----
def _post_json(url: str, headers: dict, body: dict, timeout: int) -> dict:
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    for name, value in headers.items():
        request.add_header(name, value)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _call_openai(provider: Provider, model: str, system: str | None, prompt: str,
                 temperature: float, max_tokens: int, timeout: int) -> tuple[str, dict]:
    base = os.environ.get(provider.base_url_env or "", "") or provider.base_url
    if not base:
        raise RuntimeError(
            f"no base URL for this provider; set {provider.base_url_env}"
        )
    headers = {}
    if provider.key_env:
        key = os.environ.get(provider.key_env)
        if not key:
            raise RuntimeError(f"{provider.key_env} is not set")
        headers["Authorization"] = f"Bearer {key}"

    messages = ([{"role": "system", "content": system}] if system else [])
    messages.append({"role": "user", "content": prompt})
    payload = _post_json(
        f"{base.rstrip('/')}/chat/completions", headers,
        {"model": model, "messages": messages,
         "temperature": temperature, "max_tokens": max_tokens},
        timeout,
    )
    text = (payload.get("choices") or [{}])[0].get("message", {}).get("content", "")
    return text or "", payload


def _call_anthropic(provider: Provider, model: str, system: str | None, prompt: str,
                    temperature: float, max_tokens: int, timeout: int) -> tuple[str, dict]:
    key = os.environ.get(provider.key_env or "")
    if not key:
        raise RuntimeError(f"{provider.key_env} is not set")
    body = {"model": model, "max_tokens": max_tokens, "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}]}
    if system:
        body["system"] = system
    payload = _post_json(
        f"{provider.base_url.rstrip('/')}/messages",
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
        body, timeout,
    )
    blocks = payload.get("content") or []
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    return text, payload


def _neutral_cwd() -> str:
    """An empty directory outside any repo, for the CLI to run in.

    This is load-bearing, not tidiness. `claude` auto-discovers CLAUDE.md up the
    directory tree, and this repo's CLAUDE.md states the action space
    ("act | gather-missing-info | abstain | escalate-to-clinician") and the thesis
    ("safety enforcement lives outside the model"). Running the benchmark from the
    repo would hand the model the answer key and the result would be worthless.

    `--bare` would also suppress discovery, but it forces ANTHROPIC_API_KEY and so
    defeats the point of using a subscription.
    """
    path = os.path.join(tempfile.gettempdir(), "vmag_cli_neutral")
    os.makedirs(path, exist_ok=True)
    return path


def _call_cli(model: str, system: str | None, prompt: str,
              max_tokens: int, timeout: int) -> tuple[str, dict]:
    """Run one completion through the local `claude` CLI.

    Note what this does and does not measure: the reply comes from Claude as
    exposed by the Claude Code CLI, with its system prompt replaced and its tools
    denied. That is close to a raw model call but not identical, and the CLI
    exposes no temperature setting -- so results must be labelled as coming from
    the CLI harness rather than from the API. `max_tokens` is accepted for
    interface parity and has no CLI equivalent.
    """
    binary = shutil.which("claude")
    if not binary:
        raise RuntimeError("`claude` is not on PATH")

    argv = [binary, "-p", prompt,
            "--model", model,
            "--output-format", "json",
            "--strict-mcp-config",
            "--disallowed-tools", CLI_DENIED_TOOLS]
    if system:
        argv += ["--system-prompt", system]

    proc = subprocess.run(
        argv, cwd=_neutral_cwd(), capture_output=True,
        # Pin UTF-8. `text=True` alone decodes with the locale codec, which on a
        # zh-CN Windows box is GBK -- and a model reply containing a curly quote or
        # an em dash then raises UnicodeDecodeError inside subprocess's reader
        # thread. The call returns exit 0 with empty stdout, so it looks like the
        # CLI produced nothing rather than like an encoding bug.
        encoding="utf-8", errors="replace",
        timeout=timeout + CLI_TIMEOUT_PAD,
    )
    raw = (proc.stdout or "").strip()
    if not raw:
        raise RuntimeError(
            f"claude CLI produced no output (exit {proc.returncode}): "
            f"{(proc.stderr or '').strip()[:300]}"
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # Not JSON: treat the whole of stdout as the reply rather than losing it.
        return raw, {"raw_stdout": raw[:2000]}

    if payload.get("is_error"):
        raise RuntimeError(
            f"claude CLI error ({payload.get('terminal_reason')}): "
            f"{str(payload.get('result'))[:300]}"
        )
    return str(payload.get("result") or ""), payload


# ------------------------------------------------------------------ mock ----
class MockBackend:
    """Deterministic stand-in, so every code path above the seam is testable
    with no key and no network.

    `responses` maps a substring of the prompt to the reply to return. The first
    match in insertion order wins; `default` covers the rest. Keep the mapping in
    the test that needs it, not here -- a mock that grows domain knowledge starts
    quietly encoding the answers.
    """

    def __init__(self, responses: dict[str, str] | None = None, default: str = ""):
        self.responses = responses or {}
        self.default = default
        self.calls: list[str] = []

    def __call__(self, system: str | None, prompt: str) -> str:
        self.calls.append(prompt)
        for needle, reply in self.responses.items():
            if needle in prompt:
                return reply
        return self.default


_MOCK = MockBackend()


def set_mock(backend: MockBackend) -> None:
    """Install the mock used when VMAG_MODEL=mock."""
    global _MOCK
    _MOCK = backend


def get_mock() -> MockBackend:
    return _MOCK


# -------------------------------------------------------------- complete ----
def resolve_backend(spec: str | None = None) -> str:
    return (spec or os.environ.get("VMAG_MODEL") or "mock").strip()


def is_local(spec: str) -> bool:
    return spec.split(":", 1)[0] in LOCAL_BACKENDS


def enforce_provenance(spec: str, provenance: str) -> None:
    """Refuse to send controlled-access content off your own hardware.

    Raises rather than warning. A warning would make compliance depend on someone
    reading the log, which is exactly the failure mode this project exists to
    argue against.
    """
    if provenance not in PROVENANCE:
        raise ValueError(f"provenance must be one of {PROVENANCE}, got {provenance!r}")
    if provenance == "controlled-access" and not is_local(spec):
        raise ProvenanceViolation(
            f"backend '{spec}' sends the prompt to a third party, and this content is "
            "marked controlled-access. PhysioNet's DUA forbids sending its data to an "
            "external API endpoint (Claude and OpenAI are named explicitly), and the "
            "local `claude` CLI is no exception -- the binary is local, the inference is "
            f"not. Use a local backend ({', '.join(sorted(LOCAL_BACKENDS))}) or a "
            "controlled deployment you administer. See docs/MODEL_ACCESS.md."
        )


def complete(prompt: str, *, system: str | None = None, backend: str | None = None,
             temperature: float = 0.0, max_tokens: int = DEFAULT_MAX_TOKENS,
             cache: Cache | None = None, timeout: int = DEFAULT_TIMEOUT,
             provenance: str = "synthetic-public") -> Completion:
    """Return a completion for `prompt`. Never raises on a model-side failure.

    Transport failures are returned in `Completion.error` rather than raised, so
    one flaky call cannot abort a 100-case evaluation and, more importantly, so
    the failure is recorded next to the cases it affected.

    A provenance violation DOES raise. That one is not a measurement problem to be
    recorded and moved past; it is a thing that must not happen.
    """
    spec = resolve_backend(backend)
    enforce_provenance(spec, provenance)
    cache = cache if cache is not None else Cache()
    offline = os.environ.get("VMAG_LLM_OFFLINE") == "1"

    if spec == "mock":
        return Completion(_MOCK(system, prompt), backend="mock")

    if ":" not in spec:
        return Completion("", backend=spec,
                          error=f"VMAG_MODEL='{spec}' must be 'mock' or '<provider>:<model>'")
    name, model = spec.split(":", 1)
    provider = PROVIDERS.get(name)
    if provider is None:
        return Completion("", backend=spec,
                          error=f"unknown provider '{name}'; known: {', '.join(sorted(PROVIDERS))}")

    key = _cache_key(spec, system, prompt, temperature, max_tokens)
    hit = cache.get(key)
    if hit is not None:
        return Completion(hit.get("text", ""), backend=spec, cached=True, raw=hit)

    if offline:
        raise OfflineCacheMiss(
            f"VMAG_LLM_OFFLINE=1 and no cached response for {spec} (key {key}). "
            "Run once online to populate the cache, or commit the cache alongside "
            "the results you are reproducing."
        )

    if provider.wire == "cli":
        def caller(_provider, mdl, sys_prompt, usr_prompt, _temp, max_tok, tmo):
            return _call_cli(mdl, sys_prompt, usr_prompt, max_tok, tmo)
    elif provider.wire == "anthropic":
        caller = _call_anthropic
    else:
        caller = _call_openai

    last_error = ""
    for attempt in range(RETRIES):
        try:
            text, payload = caller(provider, model, system, prompt,
                                   temperature, max_tokens, timeout)
            cache.put(key, {"backend": spec, "system": system, "prompt": prompt,
                            "temperature": temperature, "max_tokens": max_tokens,
                            "text": text})
            return Completion(text, backend=spec, raw=payload)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:400]
            last_error = f"HTTP {exc.code}: {body}"
            # 4xx other than rate limiting will not fix themselves.
            if exc.code != 429 and 400 <= exc.code < 500:
                break
        except subprocess.TimeoutExpired:
            last_error = f"claude CLI timed out after {timeout + CLI_TIMEOUT_PAD}s"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            # A refused connection means nothing is listening. Retrying with
            # backoff turns "ollama is not running" into minutes of waiting per
            # evaluation, so fail fast and say so -- the fix is to start the
            # server, not to wait.
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, ConnectionRefusedError) or "10061" in str(reason):
                last_error = (f"{last_error}  (nothing is listening -- is the server "
                              f"running? for ollama: `ollama serve`)")
                break
        except RuntimeError as exc:            # missing key / base URL / CLI failure
            last_error = str(exc)
            break
        if attempt < RETRIES - 1:
            time.sleep(2 ** attempt)

    return Completion("", backend=spec, error=last_error or "unknown failure")


def describe_backends() -> str:
    lines = [f"{'mock':11} {'no key needed':24} [ok ]  LOCAL   offline, deterministic"]
    for name, provider in sorted(PROVIDERS.items()):
        key = provider.key_env or "no key needed"
        if name == "cli":
            status = "ok " if shutil.which("claude") else "-  "
        elif provider.key_env:
            status = "set" if os.environ.get(provider.key_env) else "-  "
        else:
            status = "ok "
        scope = "LOCAL " if name in LOCAL_BACKENDS else "REMOTE"
        lines.append(f"{name:11} {key:24} [{status}]  {scope}  {provider.notes}")
    lines.append("")
    lines.append("LOCAL backends may be used with controlled-access data; REMOTE ones may not.")
    return "\n".join(lines)


if __name__ == "__main__":
    print(f"VMAG_MODEL = {resolve_backend()}\n")
    print(describe_backends())
