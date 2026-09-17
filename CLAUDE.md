# CLAUDE.md

Guidance for AI coding sessions in this repo.

## Nature

Research workspace for a clinical-**agent** safety benchmark + runtime guard
(VMAG). Not a production or clinical system. Synthetic/public data only.

## Lineage -- reuse, don't reinvent

- Enforcement architecture derives from PAPF at `../limitation_of_ai` (intent
  records, capability compilation, policy validation, enforcement mediation,
  consent, redaction, audit logs). Port the pattern; adapt the capabilities to
  clinical actions.
- Benchmark schema, deterministic replay, and scoring conventions derive from
  CAR at `../streaming_thinking`.

## Conventions

- `CONTINUITY.md` is the append-only source of truth: `## Snapshot`
  (Goal/Now/Next/Open questions), `## Invariants / Constraints`, `## Decisions`
  (`Dnnn ACTIVE|SUPERSEDED`), `## State`. Preserve `[USER]`/`[CODE]`/`[TOOL]`/
  `[ASSUMPTION]` tags. Dates are YYYY-MM-DD. Read it first.
- Keep tracking files ASCII (matches the `future_healthcare` PowerShell lesson).
- No PHI, no controlled-access data, ever. Vignettes are synthetic or public.
- Safety enforcement lives outside the model; never make a safety claim that
  depends on the LLM choosing to comply.
- Report metrics with explicit methodology; label incomparable numbers as such.

## Core design (target)

- Action space per step: `act` | `gather-missing-info` | `abstain` |
  `escalate-to-clinician`.
- A case = context + available tools + a hidden correct-action label +
  scenario tag (clean / missing-data / escalation / permission / injection).
- Metrics: task utility, unsafe-action rate, calibrated deferral (correct
  abstain/escalate), over-refusal rate, least-privilege data exposure.

## Status

STALE ENTRY CORRECTED 2026-08-26: this said "No code yet" long after the harness
existed. The harness is built and running. `CONTINUITY.md` is the current state
(D001-D066); read it first, not this section.

Shape of what exists:

- `vmag/` -- `policy.py` (FROZEN, sha256 `aa7174f9`, frozen 2026-08-08; verify
  with `scripts/check_policy_frozen.py` before trusting any run), `guard.py`,
  `runtime.py`, `environment.py`, `scoring.py`, `model_agents.py`, `llm.py`
  (nine providers), `fhir_store.py` and `http_fhir_store.py` (interchangeable
  read paths, proven by `scripts/verify_http_store.py`).
- `benchmark/cases` 28 cases, `benchmark/cases_heldout` 12 on a second Synthea
  seed. Splits `dev` / `test` were co-designed with the policy (D014); `postfreeze`
  cases were authored after the freeze, which is why `n_dev + n_test < n_cases`.
- Runners: `scripts/run_all_models.py` (every available backend, with the reason
  each skip happened), `scripts/scope_probe.py` (one axis, ~15 live calls).
- Four offline checks that must pass after any change: `check_policy_frozen`,
  `check_traps_discriminate`, `smoke_model_seam`, `smoke_r1`.

Two things a new session should know before reading any number:

- Every GUARDED metric is agent-independent BY CONSTRUCTION. `guard.review()`
  discards the model's plan, so a uniformly random agent scores the same
  1.0 / 0.0 / 1.0 as Sonnet. `enforcement_invariance` is a tautology with a
  name, not a measurement. Guarded columns are not evidence about a model.
- The held-out set is a check on the POLICY's correctness. Model-behaviour
  numbers on it (added D063) compare against a deliberately harder edge-case
  set, so they are not a clean transfer measurement in either direction.
