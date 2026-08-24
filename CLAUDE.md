# CLAUDE.md

Guidance for AI coding sessions in this repo.

## Nature

Research workspace for a clinical-**agent** safety benchmark + runtime guard
(VMAG). Not a production or clinical system. Synthetic/public data only.

## Lineage — reuse, don't reinvent

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

No code yet. Start from `task.md` and `benchmark/schema.md`.
