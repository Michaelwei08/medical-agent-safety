# Verifiable Medical Agent Guard

Verifiable Medical Agent Guard (VMAG) is a research project on making clinical AI
**agents** — LLM systems that take actions in a clinical workflow (retrieve records,
draft orders, send messages, triage, summarize) — behave safely and verifiably.

The core claim: clinical agents fail dangerously not only by producing wrong
content, but by *acting* when the correct behavior is to gather missing
information, abstain, or escalate to a licensed clinician. VMAG measures that
behavior and enforces it with a runtime guard that sits **outside** the LLM.

This is a research artifact, not a deployable clinical system, and it uses only
public/synthetic vignettes — no PHI and no controlled data.

## Research focus

- Safe tool-use for clinical LLM agents (which action, when, with what data)
- Appropriate deferral and escalation ("know when to hand off to a clinician")
- Permission boundaries and least-privilege data exposure for medical agents
- Calibrated abstention vs. over-refusal, and unsafe over-confidence
- Honest, leakage-aware evaluation of utility / safety / privacy tradeoffs

## What is and isn't novel (read this first)

An adversarial prior-art review refuted every individual-axis novelty claim:
out-of-model guards (GuardAgent, ShieldAgent, Progent), decoupled unsafe-action
rate (ST-WebAgentBench, ToolEmu, AgentDojo), least-privilege scoring
(FHIR-AgentBench), record-borne injection + exfiltration (InjecAgent, QFIRE),
scored deferral (learning-to-defer, MediQ), and absence-precondition gathering
(MedAgentBench) all pre-exist. See [`docs/RELATED_WORK.md`](docs/RELATED_WORK.md).

VMAG is therefore framed as an **instantiation + honest measurement**, not a new
architecture.

### Corrected 2026-08-26: two of the three claimed contributions do not hold

This section previously said the defensible contribution was a *measurement
stance* combining the **enforcement delta**, **adversary-strength invariance**,
and **policy-error / generalization-gap accounting**. Two of those three did not
survive being tested, and the tests were ours:

- **Adversary-strength invariance is a TAUTOLOGY, not a measurement.**
  `Guard.review()` sets the action from `evaluate_policy(env)` and never reads
  the base agent's proposal; side effects are rebuilt from policy,
  `follow_injection` is hard-coded `False` and `cross_patient_reads` hard-coded
  empty. The one surviving channel is dead because no case has an empty
  `allowed_resource_types`. Measured consequence: a uniformly **random** agent, a
  null agent and a maximally malicious agent all score exactly 1.0 / 0.0 / 1.0
  guarded, identical to Claude Sonnet on all seven metrics, and all four
  hand-built stand-ins do too. `enforcement_invariance.guarded_spread` is
  identically 0.0 for any set of agents, so reporting 0.0 reports the definition.
  `guard.py`'s own docstring already said so: *"wrapping any base agent with the
  guard yields the same safe behavior."* **No guarded column is evidence about a
  model.**
- **The generalization gap was already limited by our own D037 (2026-08-08)**
  to conformance traps: the held-out set buys patients the policy was never
  fitted to, but not independence between policy author and case author, so it
  can find a bug in the code implementing the spec and cannot find an error in
  the spec. It is not evidence of generalization and `run_eval` prints that
  caveat under the number.
- **The enforcement delta survives, with its meaning narrowed.** Because the
  guarded endpoint is fixed by construction, the delta measures what the
  UNGUARDED agent did. That is a real measurement of the agent; it is not a
  property of the guard.

### What actually stands

Our own 2026-08-10 landscape review found that **patient scope** (cross-patient
access) is the only scored axis here not already occupied by prior work, and it
is where the current result lives:

- **A patient-scope measurement bug, found and fixed.** Five of six injected
  payloads never reached the model: the injected record is appended to the end of
  the record list while the prompt rendered only the first twelve, so the payload
  sat at position 21, 24, 29, 192 and 264. Every `injection_follow_rate` of 0.0
  previously reported for a real model measured ONE case. Fixed by exempting
  injected rows from the render cap (D059).
- **"Identity contradiction is what defeats patient-scope discipline" was
  claimed here and is WITHDRAWN (2026-08-28).** On `cli:sonnet` alone the
  marginal separated. Adding a second model valid on both cohorts
  (`minimax-m3`) collapses it: pooled over both valid models, contradiction
  present is 10/16 = 0.625 [0.39, 0.82] against absent 11/42 = 0.262
  [0.15, 0.41] — **overlapping**. The effect is a Sonnet-specific property, not
  a general one. It took one additional model to find that out, which is the
  argument for never reporting a single-model marginal as a finding.
- **What survives is narrower and better supported.** Two extremes are stable
  across every usable model and both cohorts. (1) Instruction **and** identity
  contradiction *together*: 4/4 on valid arms [0.51, 1.00], 6/8 counting
  observations from invalid arms — breached by `cli:sonnet`, `gpt-oss-120b` and
  `minimax-m3`, each on both cohorts. (2) The clean control from D070, identity
  asserted and **correct**: 0/4 valid, 0/8 across all arms, breached by nobody.
  Only the middle — which single factor matters — is model-dependent.
- **The two models fail on nearly disjoint triggers, and that is the most
  useful result in the table.** On valid arms `cli:sonnet` breaches identity
  cases 6/10 and non-identity pretexts 2/19; `minimax-m3` is almost the
  inversion, 3/10 and 10/19. Sonnet is identity-sensitive and
  pretext-insensitive; MiniMax the reverse. So the *same 29 cases* order the two
  models differently depending on which slice you take:

  | slice | cli:sonnet | minimax-m3 | safer |
  |---|---|---|---|
  | as built | 8/29 = 0.276 | 13/29 = 0.448 | sonnet |
  | identity pretexts only | 6/10 = 0.600 | 3/10 = 0.300 | **minimax (reversed)** |
  | non-identity only | 2/19 = 0.105 | 10/19 = 0.526 | sonnet |

  Which model a scope benchmark calls safer depends entirely on the pretexts it
  happens to contain. Every interval overlaps in every slice, so the claim is
  about the point-estimate **ordering** flipping with item composition, not
  about either ordering being significant.
- **The breach is safety-motivated, which is why scope needs its own axis.** In
  every breaching case the model chose a *deferral* and did not act on the wrong
  patient; it requested the other chart in order to verify before acting. The
  impulse to check is the privacy violation.
**Limits, stated because they bound the claim:** two models pass the
response-validity gate, not one, and `nemotron-3-super-120b` fails it (usable
0.588 main, 0.167 held-out) so it contributes observations only. Every interval
in the slice table above overlaps. The combined-condition arm is 4/4 on valid
arms, which is four observations. Separating two models' overall scope rates
would need roughly 80 eligible cases against the current 29.

Nothing here is stated as "first". See [`CONTINUITY.md`](CONTINUITY.md) for the
retraction history this result went through — three on 2026-08-26, and the
identity-contradiction phrasing withdrawn again on 2026-08-28 when a second
valid model was added. The pattern is the point: every headline this project
has produced from a single model has been withdrawn once a second model
arrived.

## Why this project

VMAG retargets prior work to the clinical-agent setting:

- **Permission firewall / runtime enforcement** — from the Personal Agent
  Permission Firewall (`../limitation_of_ai`, PAPF): capability compilation,
  policy validation, enforcement mediation, consent handling, redaction, audit
  logs.
- **Benchmark schema + structured scoring + reproducible harness** — from
  Checkpointed Adaptive Reasoning (`../streaming_thinking`, CAR).
- **Leakage-aware, "these numbers are not comparable" evaluation discipline** —
  the same rigor applied in the BAMM Raman work and the Ash viral-detection work.

## Target use

A concrete, verifiable artifact suitable for (a) a research-lab entry ticket
(clinical-LLM evaluation and medical-agent safety) and (b) an AI-healthcare
internship portfolio centerpiece.

## Repo layout

- `vmag/` — the package (16 modules): `policy.py` (frozen), `guard.py`,
  `runtime.py`, `environment.py`, `scoring.py`, `model_agents.py`, `llm.py` (nine
  providers), and two interchangeable read paths `fhir_store.py` /
  `http_fhir_store.py`.
- `benchmark/cases` (35) and `benchmark/cases_heldout` (19) — cases on two
  Synthea cohorts. Splits `dev` / `test` were co-designed with the policy;
  `postfreeze` cases were authored after the freeze, which is why
  `n_dev + n_test < n_cases`.
- `scripts/` — 12 scripts. Four offline checks must pass after any change:
  `check_policy_frozen`, `check_traps_discriminate`, `smoke_model_seam`,
  `smoke_r1`. Runners: `run_all_models.py` (every available backend, with the
  reason each skip happened) and `scope_probe.py` (one axis, ~15 live calls).
- `outputs/` — 45 evaluation runs and a response cache. `VMAG_LLM_OFFLINE=1`
  replays any of them with no key and no spend.
- `docs/` — evaluation protocol, related work, model access.
- `CONTINUITY.md` — append-only goal/decision/state log (read first).
- `CLAUDE.md` — repo guidance for AI coding sessions.

## Status

CORRECTED 2026-08-26: this said "Scaffolding stage. No experiments have been run
yet" long after 45 runs existed.

The harness runs. The policy has been frozen since 2026-08-08 (sha256
`aa7174f9`, verify with `scripts/check_policy_frozen.py` before trusting any
number). Real-model coverage is the binding constraint, not code: of five
documented free API tiers, three do not work at all as of 2026-08-25 — Cerebras
returns HTTP 402 on a new key, NVIDIA NIM takes ~175 s per call, Gemini 429s
after roughly 25-30 calls. See the measured-availability block in
[`docs/MODEL_ACCESS.md`](docs/MODEL_ACCESS.md), and treat every model id there
as dead until you have listed it against the live endpoint: four of four hosted
providers had an expired id in that file (D072).

CORRECTED 2026-09-17: this paragraph used to end "so every result currently
rests on `cli:sonnet` once the response-validity gate is applied." That stopped
being true on 2026-08-28, when `minimax-m3` came in via OpenRouter as a second
model valid on both cohorts — and adding it is what withdrew the
identity-contradiction headline above. Two models pass the gate.
