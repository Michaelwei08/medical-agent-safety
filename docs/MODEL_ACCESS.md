# Model access for the real-agent runs

Checked 2026-08-07. Rate limits and program terms move; re-check before relying on
a number here.

The blocker for putting real models behind the guard is not code -- the seam is
built and tested (`vmag/llm.py`, `scripts/smoke_model_seam.py`). It is access.
This records what is actually available with a Stanford affiliation and no budget.

## Stanford: what does and does not work

| Resource | Scriptable? | Cost | Verdict for this project |
|---|---|---|---|
| [AI Playground](https://uit.stanford.edu/service/aiplayground) | No -- web UI | Broad access with a SUNet ID | Useless for a benchmark. You cannot run 14 cases x N models through a chat window and call it reproducible. |
| [AI API Gateway](https://uit.stanford.edu/service/ai-api-gateway) | Yes, OpenAI-compatible | **Requires a PTA** (a billing account) | The right answer *if* a PI or course gives you a PTA. Worth one email. |
| [Sherlock](https://www.sherlock.stanford.edu/) | Yes | **Free to all Stanford researchers, GPUs included** | The strongest option you already have. See below. |
| [Marlowe](https://srcc.stanford.edu/) (DGX H100 SuperPod) | Yes | Managed by Stanford Data Science | Overkill here, but it exists. |

Two things worth being precise about:

- The Playground is *approved for moderate-risk and high-risk non-PHI data but not
  for PHI*. VMAG is synthetic-only, so that restriction does not bind us -- and it
  should stay that way. Do not let real patient data near any of this.
- The Gateway is OpenAI-compatible, so `vmag/llm.py` already speaks it. If you get
  a PTA, it is two environment variables and no code change:

```bash
export STANFORD_AI_BASE_URL=<gateway base url>
export STANFORD_AI_API_KEY=<key>
export VMAG_MODEL=stanford:gpt-4o
```

## The `claude` CLI: a real model with no API budget

If you have a Claude Code subscription you already have scriptable Claude access.
`VMAG_MODEL=cli:sonnet` shells out to `claude -p --output-format json` with the
system prompt replaced and tools denied, which makes it a text completion rather
than an agent turn.

```bash
export VMAG_MODEL=cli:sonnet
python scripts/check_cli_backend.py          # run from your own terminal
```

**It cannot be verified from inside a Claude Code session.** A nested `claude`
process cannot refresh the OAuth token and fails with "OAuth session expired and
could not be refreshed" -- with or without sandboxing. That is a property of
nesting, not of your credentials; run the check from your own terminal.

### The context-isolation problem, which is easy to miss

`claude` auto-discovers `CLAUDE.md` up the directory tree. This repo's `CLAUDE.md`
states the four-way action space and "safety enforcement lives outside the model",
and the workspace `CLAUDE.md` above it describes the project again. **Running the
benchmark from the repo would hand the model the answer key**, and every number you
got would be worthless.

`vmag/llm.py` therefore runs the CLI in an empty temp directory with no `CLAUDE.md`
anywhere above it, and `scripts/smoke_model_seam.py` asserts that. `--bare` would
also suppress discovery but forces `ANTHROPIC_API_KEY`, defeating the point.

### Two caveats that must reach any write-up

- **No temperature control.** The CLI exposes none, so runs are not reproducible
  from the model side. The response cache freezes whatever came back first, which
  makes a *recorded* result replayable but does not make a *fresh* run identical.
  The HTTP backends pin `temperature=0`; this one cannot.
- **It is not the API.** The reply is Claude as exposed by the Claude Code CLI.
  With the system prompt replaced and tools denied it is close to a raw model call,
  but residual harness scaffolding is possible. Label the row **"via Claude Code
  CLI"**, never plain "Claude", and do not put it in the same column as an API
  result.

For a headline number, prefer the Stanford Gateway or the API. Use the CLI to get
the first real-model signal today, for free.

## Sherlock is the free path to a real model

Sherlock is free to Stanford researchers, has GPU nodes, and has no charge and no
total-usage cap. That makes an open-weight model at 7B-70B effectively free for
this project, with three properties a hosted free tier cannot match:

- **No rate limit.** A 50-case x 4-model sweep does not need to be spread over days.
- **No data leaving Stanford.** Irrelevant for synthetic vignettes, but it removes
  the question entirely if the benchmark ever grows real cases.
- **Version pinning.** A hosted `gemini-2.0-flash` can change under you between
  runs; a local checkpoint cannot. For a benchmark, that matters more than raw
  capability.

Serve a model with an OpenAI-compatible endpoint (vLLM or Ollama) on the compute
node, tunnel the port, and point the seam at it:

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export VMAG_MODEL=ollama:qwen2.5:7b
```

You already run Ollama locally in `../software_paper_into_mp4`, so the smallest
possible first step is on your own machine -- no cluster allocation needed to get
the first real-model number.

## Free hosted tiers, no credit card

For the "one non-Anthropic model" half of the comparison, these need no billing
setup. All are OpenAI-compatible and already wired in `PROVIDERS`.

| Provider | Env var | Notes |
|---|---|---|
| Google AI Studio (Gemini) | `GEMINI_API_KEY` | The usual recommendation as the best free baseline; ~1,500 requests/day on Flash after the late-2025 reductions. |
| Groq | `GROQ_API_KEY` | Fast; ~30 RPM / 1,000 RPD on `llama-3.3-70b-versatile`. |
| Cerebras | `CEREBRAS_API_KEY` | Largest reported free daily token budget (~1M tokens/day). |
| NVIDIA NIM | `NVIDIA_API_KEY` | 120+ open-weight models, ~40 RPM, no daily cap reported. |
| OpenRouter | `OPENROUTER_API_KEY` | Widest model variety, but only ~50 free-model requests/day until $10 of credit is bought. |

Rate limits are per provider, so a sweep can be spread across several. At 14 cases
this is irrelevant -- a full run is 14 calls per model.

## Claude specifically

The comparison as scoped wants Claude plus one non-Anthropic model, and Claude is
the one that costs money. Options, honestly ranked:

1. **A PTA through a PI or course.** The Gateway carries Anthropic models, so this
   solves Claude and the non-Anthropic side at once.
2. **[Claude for Open Source](https://www.anthropic.com/) (launched Feb 2026)** --
   six months of Claude Max for qualifying open-source maintainers, 10,000 spots.
   VMAG would need to be public first. Worth checking eligibility, not worth
   restructuring the project around.
3. **Run the non-Anthropic half first.** The seam does not care. A table with one
   real model and a stated absence is publishable; a table with a model you could
   not afford to run properly is not.

## MIMIC: why credentialing was never the real blocker

`D005` deferred MIMIC-based benchmarks "because they require PhysioNet
credentialing". If you are credentialed, that sentence no longer applies -- but it
was the shallowest of the reasons, and three deeper ones remain.

**1. The DUA forbids precisely what the next experiment does.** PhysioNet's
guidance on [use of MIMIC data with LLMs and online
services](https://physionet.org/news/post/llm-responsible-use/) states that
sending the data to an external API endpoint is a DUA violation and names Claude
and OpenAI explicitly. The whole point of the current work is putting real models
behind the guard. With a hosted model, MIMIC cannot be part of it -- **and the
`claude` CLI is no exception: the binary is local, the inference is not.**

**2. The public site.** `../agent_medicine` exports case data into a static page on
`cpwei.qzz.io`. Synthea is Apache-2.0 and safe to publish; MIMIC-derived records
can never go there, not even one field. Keeping the public artifact synthetic-only
is what makes it publishable at all.

**3. The workspace rule.** `research/CLAUDE.md`: "No PHI, no controlled-access
data, ever." That is a standing constraint, not a placeholder for "until I get
access".

### What is actually permitted

PhysioNet allows running an LLM **on your own or access-controlled hardware**, or
deploying one inside a cloud environment you administer (Azure OpenAI, Bedrock).
Combined with the Sherlock finding above, that is a real path:

> **MIMIC + an open-weight model on Sherlock or your own machine is compliant.**
> MIMIC + Claude, Gemini, Groq, the Stanford Gateway, or the `claude` CLI is not.

So the honest recommendation is two tracks that never touch:

| | Public track | Private track |
|---|---|---|
| Data | Synthea (Apache-2.0) | MIMIC (credentialed) |
| Models | any, including hosted | local only |
| Ships to the website | yes | never |
| Publishable | cases and numbers | aggregate numbers only, no records |

MIMIC would buy real clinical language, real messiness, and cases nobody authored
to match a policy -- which is exactly what `D014`'s generalization caveat needs. It
is worth doing on the private track. It is not worth doing by loosening the rule
that keeps the public track publishable.

### This is enforced in code, not by discipline

`vmag/llm.py` takes a `provenance` argument. Marking content `controlled-access`
makes `complete()` **raise** on every remote backend, the CLI included, and permit
only `mock` and `ollama`. It raises rather than warns, because a warning makes
compliance depend on somebody reading a log.

A project whose thesis is "safety should not depend on the agent choosing to
comply" should not rely on its author choosing to comply either.

## What the numbers will and will not mean

Whatever backend you use, `run_eval` must report real-model results as a
**separate labeled table**. The mock agents' unsafe rate and a real model's unsafe
rate are not comparable numbers and must never share a column.

Two failure modes to watch for, both of which the seam already records:

- **Parse failures are not caution.** A model that emits prose instead of JSON gets
  a fail-safe `abstain`, tagged `unusable="parse"`. Reported as an abstention it
  would look like a well-behaved model. Report the parse-failure rate next to any
  deferral rate, always.
- **A small local model may fail the task, not the safety test.** If a 7B model
  cannot follow the output format, you have measured its formatting, not its
  clinical judgment. Check the parse-failure rate before reading anything else.

One outcome is worth pre-committing to: **if frontier models already behave safely
on these 14 cases, say so plainly and prominently.** That result would mean the
enforcement delta measured on stand-in agents overstates the value of the guard for
capable models, and the interesting question moves to where the guard still earns
its place (injection, cross-patient scope, adversarial phrasing). Learning that in
week one is worth more than a favourable table in week six.

## Reproducing without credentials

Every response is cached on disk under `outputs/llm_cache/`, keyed by the exact
request. The cache holds only synthetic vignettes, so it can be committed with the
results. Anyone can then recompute the published numbers with no key and no spend:

```bash
VMAG_LLM_OFFLINE=1 python -m vmag.run_eval
```

A cache miss under that flag is an error, not a silent live call -- so a run that
claims to be a reproduction cannot quietly become a fresh one.

### Model ids go stale -- checked again 2026-08-25

The table above was checked 2026-08-07 and its Gemini model id has since been
RETIRED: `gemini-2.0-flash` now returns HTTP 404 "no longer available", and so
does `gemini-2.5-flash`. Enumerated from the live `/models` endpoint on
2026-08-25, this key sees 51 models; the flash line currently runs to
`gemini-3.7-flash`.

Use `gemini-3.6-flash`. It is verified working through `vmag/llm.py` and it
answers correctly even at a 64-token budget, so its output budget is not shared
with hidden reasoning. `gemini-3.7-flash` also works but returns EMPTY at 64
tokens and only answers at 1024, which means a hard case could truncate a JSON
plan and look like model incompetence rather than a budget artifact.

Never use a `-latest` alias (`gemini-flash-latest`, `gemini-pro-latest`) in a
benchmark. They move, and a run whose model changed underneath it is not
reproducible. Pin the version.

`scripts/run_all_models.py` now preflights every backend with one call before
spending a full run, and treats empty output as failure whether or not an error
came with it.

### Verified-live model ids, 2026-08-25

Checked against each provider's own `/models` endpoint on 2026-08-25, with a key
in hand. THREE OF FOUR configured ids had expired in the eighteen days since the
2026-08-07 table above. Treat every model id in this file as expired until you
have listed it against the live endpoint; `scripts/run_all_models.py` preflights
each backend with one call, so a stale id costs one call rather than one run.

| provider | id in use | state on 2026-08-25 |
|---|---|---|
| Gemini | `gemini-3.6-flash` | `gemini-2.0-flash` and `gemini-2.5-flash` both RETIRED (HTTP 404). 51 models visible; flash line runs to `gemini-3.7-flash`. |
| Groq | `openai/gpt-oss-120b` | `llama-3.3-70b-versatile` RETIRED. 13 models visible. |
| Cerebras | `gemma-4-31b` | `llama-3.3-70b` RETIRED. Only TWO models visible: `gemma-4-31b` and `gpt-oss-120b`. |
| NVIDIA NIM | `meta/llama-3.3-70b-instruct` | still live; 95 models visible. The only id of the four that had not expired. |

Two traps worth carrying:

- **Never use a `-latest` alias** (`gemini-flash-latest`, `gemini-pro-latest`).
  They move, and a run whose model changed underneath it is not reproducible
  while looking identical in the artifacts.
- **Cerebras and Groq both serve `gpt-oss-120b`.** The weight-digest dedup in
  `run_all_models.py` only works for ollama, where the daemon reports a digest;
  two hosted providers serving the same weights cannot be detected
  automatically. Running both gives a PROVIDER comparison, not a second model -
  useful for asking whether serving stack changes the numbers, but it must not
  be presented as model diversity.

Quota, measured rather than quoted: a brand-new Gemini key hit HTTP 429 after
roughly 25-30 live calls, not the ~1,500/day the 2026-08-07 table records. One
VMAG run is about 56 calls before caching, so a single free key does not reliably
cover one run. `outputs/llm_cache/` plus `VMAG_LLM_OFFLINE=1` are load-bearing,
not a convenience.

### Measured availability, 2026-08-25 -- three of five are NOT usable

The "Free hosted tiers, no credit card" table above was checked 2026-08-07 by
reading provider documentation. Re-checked 2026-08-25 by holding a key and making
a call, the picture is different. Trust this block over that table.

| provider | measured state |
|---|---|
| Groq | **WORKS.** Main-set run valid on `openai/gpt-oss-120b`. Held-out pass hit a per-model org rate limit. Needs a `User-Agent` or Cloudflare answers 403 code 1010. |
| Gemini | HTTP 429 after roughly 25-30 live calls, on three separate attempts. Not the ~1,500/day this file previously recorded. |
| Cerebras | HTTP 402 `payment_required_error`, `param: quota`, on a brand-new key and on BOTH models it can see. Billing must be attached first; there is no usable free path. |
| NVIDIA NIM | Reachable, but ~175 s per trivial completion in steady state (177.3 s / timeout at 240 s / 178.3 s / 173.3 s) and it failed to echo one word at temperature 0. Not viable for a 40-prompt run. |
| OpenRouter | Not registered. This file's own note is ~50 requests/day until $10 of credit. |

So the real-model column that can actually be filled today is **cli:sonnet on a
subscription plus groq `openai/gpt-oss-120b`**. Plan for two, not five.
