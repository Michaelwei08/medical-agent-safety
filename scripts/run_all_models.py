"""Run the evaluation once per available real model, and say why each was skipped.

WHY THIS EXISTS
    D022 forbids a real model sharing a table with the deterministic stand-ins,
    so every real backend needs its own run. Doing that by hand invites two
    errors: silently omitting a backend whose key is absent (which reads as "we
    tested everything") and forgetting which cohort/store a given output used.

    So this enumerates every backend `vmag/llm.py` wires, decides availability
    mechanically, runs the ones that are available, and prints the skipped ones
    WITH THE REASON. A skip is data: "no key" and "the model refused" are
    different facts and must not collapse into a blank cell.

AVAILABILITY IS CHECKED, NOT ASSUMED
    A hosted backend needs its env var set. `ollama` needs the daemon answering
    on 11434 AND the specific tag present locally -- a key-less backend can still
    be unavailable, and pulling a 4.7 GB model is not something to do implicitly.
    `cli` needs a live `claude` login, which expired here (D0xx), so it is listed
    and skipped rather than dropped from the menu.

COST NOTE
    Every call goes through `outputs/llm_cache/`, so a re-run of an already-run
    backend costs nothing and returns the same numbers. That is what makes it
    safe to invoke this repeatedly while adding keys one at a time.

Usage:
    python scripts/run_all_models.py                 # everything available
    python scripts/run_all_models.py --dry-run       # just the availability table
    python scripts/run_all_models.py --only gemini groq
    python scripts/run_all_models.py --store http    # against the live FHIR server
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.getcwd())
from vmag.llm import PROVIDERS                                    # noqa: E402


def load_env_local(path=".env.local"):
    """Read KEY=value lines into os.environ without overwriting a real env var.

    An already-exported variable wins, so a shell that has a key set stays
    authoritative and this file cannot silently shadow it. Values are not
    logged anywhere - only the NAME is ever printed, never the secret.
    """
    if not os.path.exists(path):
        return 0
    n = 0
    for raw in open(path, encoding="utf-8"):
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if v and not os.environ.get(k):
            os.environ[k] = v
            n += 1
    return n

# One representative model per provider. Chosen for the comparison, not for
# leaderboard scores: a different model FAMILY per provider is worth more than
# three variants of the same base weights.
CANDIDATES = [
    ("ollama:qwen2.5:7b",              "local 7B, no key, no egress"),
    # NOT listing ollama:qwen2.5:7b-instruct. Measured: identical digest
    # (845dbda0ea48...) to qwen2.5:7b, because the bare tag already resolves to
    # the instruct build. Running both spends hours to produce a second column
    # that looks like independent evidence and is the same weights twice.
    ("gemini:gemini-3.6-flash",        "frontier-class, free tier"),
    # llama-3.3-70b-versatile was RETIRED (checked live 2026-08-25, 13 models
    # visible and it is not among them). gpt-oss-120b is the largest text model
    # this key can reach and is the independent non-Anthropic peer D022 wants -
    # neither Anthropic nor Google, and 120B against qwen's failed 7B.
    ("groq:openai/gpt-oss-120b",       "120B open-weight, free tier"),
    # llama-3.3-70b is RETIRED here too (checked live 2026-08-25: this key sees
    # exactly TWO models, gemma-4-31b and gpt-oss-120b). Picking gemma-4-31b
    # because the other one is the SAME model already running via Groq, and a
    # different family is worth more than the same weights on a second provider.
    # NOTE the weight-digest dedup below only works for ollama, where the daemon
    # reports a digest; two hosted providers serving identical weights cannot be
    # detected automatically, so that has to be checked by hand when adding one.
    ("cerebras:gemma-4-31b",           "Gemma family, free tier"),
    # Verified still live 2026-08-25 (95 models visible, this one among them) -
    # the only configured id of the four hosted providers that had not expired.
    ("nvidia:meta/llama-3.3-70b-instruct", "Llama family, free tier"),
    # meta-llama/llama-3.3-70b-instruct:free is RETIRED here too (checked live
    # 2026-08-28: 431 models, 22 free, and it is not among them). FOURTH of four
    # hosted providers whose configured id had expired -- treat every id in
    # docs/MODEL_ACCESS.md as dead until listed against the live endpoint.
    #
    # Chosen for FAMILY diversity, which is the whole reason to use OpenRouter:
    # one key reaches many lineages, and the open question is whether the
    # identity-contradiction asymmetry (D070) is a general property or a
    # coincidence of two models. Sonnet is Anthropic and gpt-oss-120b is OpenAI
    # open-weight, so these add GLM, MiniMax, Gemma and Nemotron.
    #
    # NOTE the weight-digest dedup only works for ollama. By hand:
    # google/gemma-4-31b-it here is the SAME weights as cerebras:gemma-4-31b,
    # which is 402-blocked, so there is no live duplicate today -- but if
    # Cerebras ever gets billing, one of the two must go.
    ("openrouter:z-ai/glm-5.2:free",    "GLM family, free"),
    ("openrouter:minimax/minimax-m3:free", "MiniMax family, free"),
    ("openrouter:google/gemma-4-31b-it:free", "Gemma family, free"),
    ("openrouter:nvidia/nemotron-3-super-120b-a12b:free", "Nemotron 120B, free"),
    ("cli:sonnet",                     "Anthropic via the local CLI subscription"),
]


def ollama_tags():
    """{tag: digest}, or None if the daemon is not answering."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as r:
            return {m["name"]: m.get("digest", "") for m in json.loads(r.read()).get("models", [])}
    except Exception:                                             # noqa: BLE001
        return None


def dedupe_by_weights(runnable, tags):
    """Drop backends whose weights are byte-identical to one already selected.

    Two ollama tags can point at the same blob - `qwen2.5:7b` and
    `qwen2.5:7b-instruct` share digest 845dbda0ea48, because the bare tag already
    resolves to the instruct build. Running both costs hours of CPU and yields a
    second column that reads as an independent model and is not one. Compared by
    the digest the daemon reports, not by tag string, so a rename cannot fool it.
    """
    kept, dropped, seen = [], [], {}
    for backend, why in runnable:
        dig = (tags or {}).get(backend.split(":", 1)[1]) if backend.startswith("ollama:") else None
        if dig and dig in seen:
            dropped.append((backend, "same weights as %s (digest %s)" % (seen[dig], dig[:12])))
            continue
        if dig:
            seen[dig] = backend
        kept.append((backend, why))
    return kept, dropped


def availability(backend, _tags_cache={}):
    """(ok, reason). Never guesses: a missing key and a missing daemon differ."""
    provider = backend.split(":", 1)[0]
    prov = PROVIDERS.get(provider)
    if prov is None:
        return False, "provider %r is not wired in PROVIDERS" % provider

    if provider == "ollama":
        if "tags" not in _tags_cache:
            _tags_cache["tags"] = ollama_tags()
        tags = _tags_cache["tags"]
        if tags is None:
            return False, "ollama daemon not answering on 127.0.0.1:11434"
        tag = backend.split(":", 1)[1]
        if tag not in tags:
            return False, "model %r not pulled (`ollama pull %s`)" % (tag, tag)
        return True, "daemon up, model present"

    if provider == "cli":
        # An explicit OAuth token wins over the credentials file. Checking only
        # the file reported "expired" even with a good token exported, which is
        # a false negative that would silently drop the backend from the run.
        if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
            return True, "CLAUDE_CODE_OAUTH_TOKEN is set"
        exe = None
        for d in os.environ.get("PATH", "").split(os.pathsep):
            for name in ("claude.exe", "claude.cmd", "claude"):
                p = os.path.join(d, name)
                if os.path.exists(p):
                    exe = p
                    break
            if exe:
                break
        if not exe:
            return False, "`claude` CLI not on PATH"
        # A logged-out CLI still exists, so presence is not availability. The
        # credential file is the honest signal.
        cred = os.path.expanduser("~/.claude/.credentials.json")
        if os.path.exists(cred):
            try:
                d = json.load(open(cred, encoding="utf-8"))
                blob = json.dumps(d)
                if '"expiresAt": 0' in blob or '"expiresAt":0' in blob:
                    return False, "CLI present but OAuth expired (expiresAt 0) - re-login"
            except Exception:                                     # noqa: BLE001
                pass
        return True, "CLI on PATH"

    env = prov.key_env
    if env and not os.environ.get(env):
        return False, "%s not set - register at the provider, then set it" % env
    return True, "%s is set" % env


def preflight(backend):
    """One cheap call, to prove the backend can actually answer.

    THE MISTAKE THIS PREVENTS, made on 2026-08-25: `gemini-2.0-flash` had been
    retired, so every call returned HTTP 404. `llm.complete` recorded that
    faithfully in `Completion.error` and returned empty text - but a probe that
    printed only `.text` and `.cached` read it as success. A full run would have
    produced 56 empty responses and a usable_response_rate near zero.

    So: a backend passes only if the reply is non-empty AND `.error` is unset.
    Both conditions matter and neither implies the other - a retired model gives
    empty text WITH an error, while a thinking model given too small a token
    budget gives empty text with NO error (measured: gemini-3.7-flash returns ''
    at max_tokens=64 and 'OK' at 1024). Empty output is a failure either way.

    Model ids are pinned deliberately. `gemini-flash-latest` and friends are
    moving aliases; a benchmark whose model silently changes underneath it is
    not reproducible.
    """
    sys.path.insert(0, os.getcwd())
    from vmag import llm
    try:
        c = llm.complete("Reply with exactly one word: OK", system="You are terse.",
                         backend=backend, temperature=0.0, max_tokens=llm.DEFAULT_MAX_TOKENS)
    except Exception as e:                                        # noqa: BLE001
        return False, "%s: %s" % (type(e).__name__, _scrub(str(e))[:110])
    err = _scrub(getattr(c, "error", None) or "")
    txt = (getattr(c, "text", "") or "").strip()
    if err:
        return False, "call returned an error: %s" % err[:110]
    if not txt:
        return False, "call succeeded but returned EMPTY text (retired model, or budget eaten by thinking)"
    return True, "answered %r" % txt[:20]


def _scrub(s):
    """Never let a provider echo a key back into the transcript."""
    out = str(s)
    for prov in PROVIDERS.values():
        env = getattr(prov, "key_env", None)
        val = os.environ.get(env) if env else None
        if val:
            out = out.replace(val, "<REDACTED>")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", nargs="*", default=None,
                    help="provider prefixes to restrict to, e.g. gemini groq")
    ap.add_argument("--store", default="disk", choices=("disk", "http"))
    ap.add_argument("--extra", nargs=argparse.REMAINDER, default=[],
                    help="passed through to run_eval verbatim")
    args = ap.parse_args()

    loaded = load_env_local()
    if loaded:
        print("  loaded %d key(s) from .env.local (names only, never values)" % loaded)
        print()

    todo = CANDIDATES
    if args.only:
        todo = [c for c in todo if c[0].split(":", 1)[0] in set(args.only)]

    print("  %-52s %-9s %s" % ("backend", "status", "reason"))
    print("  " + "-" * 108)
    runnable = []
    for backend, why in todo:
        ok, reason = availability(backend)
        print("  %-52s %-9s %s" % (backend, "READY" if ok else "skip", reason))
        if ok:
            runnable.append((backend, why))
    runnable, dup = dedupe_by_weights(runnable, ollama_tags())
    for backend, reason in dup:
        print("  %-52s %-9s %s" % (backend, "dup", reason))

    print()
    print("  %d runnable, %d skipped, %d duplicate weights"
          % (len(runnable), len(todo) - len(runnable) - len(dup), len(dup)))
    if args.dry_run or not runnable:
        return 0

    print()
    print("  preflight (one call each, checks .error AND non-empty output):")
    live = []
    for backend, why in runnable:
        ok, reason = preflight(backend)
        print("    %-52s %-5s %s" % (backend, "pass" if ok else "FAIL", reason))
        if ok:
            live.append((backend, why))
        else:
            print("      -> skipping the full run; %d calls would have been wasted" % 56)
    if not live:
        print()
        print("  no backend passed preflight, nothing run")
        return 1
    runnable = live

    results = []
    for backend, why in runnable:
        print()
        print("  ==== %s  (%s) ====" % (backend, why))
        cmd = [sys.executable, "-m", "vmag.run_eval",
               "--model-backend", backend, "--store", args.store] + list(args.extra)
        p = subprocess.run(cmd, text=True, capture_output=True,
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        tail = (p.stdout or "").strip().splitlines()
        for line in tail[-14:]:
            print("    " + line[:150])
        if p.returncode != 0:
            print("    EXIT %d" % p.returncode)
            for line in (p.stderr or "").strip().splitlines()[-8:]:
                print("    err: " + line[:150])
        results.append((backend, p.returncode))

    print()
    print("  ---- summary ----")
    for backend, rc in results:
        print("  %-52s %s" % (backend, "ok" if rc == 0 else "FAILED rc=%d" % rc))
    return 0 if all(rc == 0 for _, rc in results) else 1


# Guarded so scripts/scope_probe.py can import availability(), preflight() and
# load_env_local() instead of copying them. Two copies of an availability check
# is two answers to the question can this backend run.
if __name__ == "__main__":
    sys.exit(main())
