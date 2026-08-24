# VMAG Project Brief

## Problem

Clinical LLM agents increasingly take *actions* — pulling records, drafting
orders, messaging patients/clinicians, triaging, summarizing. The dangerous
failure mode is not only wrong content but wrong *action*: acting on incomplete
information, exceeding the data access a task needs, following instructions
embedded in retrieved records, or answering when the safe move is to escalate to
a licensed clinician. Standard medical-QA benchmarks do not measure any of this.

## Contribution (target)

1. A synthetic clinical-agent **environment** with a small, well-defined action
   space and tool set.
2. A **benchmark** of hand-curated cases, each with a hidden correct-action
   label and a scenario tag, including adversarial temptation/injection cases.
3. A **runtime guard** (ported from PAPF) that enforces least-privilege data
   access and safe-action gating outside the LLM.
4. An **honest evaluation** reporting utility, unsafe-action rate, calibrated
   deferral, over-refusal, and data-exposure across baseline vs. guarded agents.

## Action space

Each agent step resolves to one of:

- `act` — take the clinical action (the task warrants it and data is sufficient)
- `gather-missing-info` — request the specific missing input before acting
- `abstain` — decline; the request is out of safe scope
- `escalate-to-clinician` — hand off to a licensed human

## Scenario tags

- **clean** — action is warranted; agent should `act`.
- **missing-data** — key input absent; agent should `gather-missing-info`.
- **escalation** — high-risk/uncertain; agent should `escalate-to-clinician`.
- **permission** — task tempts broader data access than needed; agent should
  stay least-privilege.
- **injection** — retrieved content contains instructions aimed at the agent;
  agent should treat it as data, not commands.

## Metrics

- Task utility (correct action on clean cases)
- Unsafe-action rate (acted when it should have deferred/escalated) — the
  headline safety number
- Calibrated deferral (correct `abstain`/`escalate` on the cases that need it)
- Over-refusal rate (deferred on clean cases) — the utility cost of safety
- Least-privilege data exposure (fraction of accessed fields actually needed)

## Non-goals / guardrails

- Not a clinical decision-support tool; no real patient data; no PHI.
- No claim of clinical validity — labels are researcher-authored in v1 and
  clinician validation is an explicit v2 ask (and a reason to join a lab).
- Safety must not depend on the model choosing to comply; enforcement is
  external.

## Positioning

VMAG operationalizes the stated direction: turn a clinical problem into a
verifiable, deployable AI system, evaluated rigorously. It reuses PAPF
(enforcement) and CAR (benchmark/scoring) so time-to-artifact is short.
