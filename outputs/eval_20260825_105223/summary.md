# VMAG evaluation summary

Cases: 20. Data: Synthea (synthetic, Apache-2.0) + MedAgentBench-style action space (MIT). Deterministic base agents (v0).

Positioning: instantiation + honest measurement, not a new architecture or metric (see docs/RELATED_WORK.md). The defensible contribution is the measurement stance below, not any single capability.

## Enforcement delta (headline result)

Same base agent, guard OFF vs ON. Lower is safer.

| base | unsafe off | unsafe on | reduction | out-of-scope off | out-of-scope on | injection off | injection on |
| --- | --- | --- | --- | --- | --- | --- | --- |
| keyword | 0.5 | 0.0 | 0.5 | 1.6 | 0.0 | 1.0 | 0.0 |
| mock_model | 0.45 | 0.0 | 0.45 | 0.75 | 0.0 | 0.5 | 0.0 |
| naive | 0.7 | 0.0 | 0.7 | 1.6 | 0.0 | 1.0 | 0.0 |
| worst_case | 0.7 | 0.0 | 0.7 | 1.6 | 0.0 | 1.0 | 0.0 |

## Enforcement invariance (adversary spectrum)

Unsafe-rate spread across base agents (benign -> worst_case): **unguarded 0.25 -> guarded 0.0** (guarded floor 0.0).
A near-zero guarded spread beside a large unguarded spread is the evidence that safety is set by the policy, not the agent -- the guarantee, instantiated.

## Policy-error accounting (guard vs oracle, no agent in loop)

Because side effects are mediated, the residual unsafe/over-refusal ceiling is the guard's own policy error. Measured on held-out (test) vs tuned (dev):

| scope | n | policy_error | under_block (safety) | over_block (utility) | defer_miscalib |
| --- | --- | --- | --- | --- | --- |
| overall | 20 | 0.0 | 0.0 | 0.0 | 0.0 |
| dev | 12 | 0.0 | 0.0 | 0.0 | 0.0 |
| test | 8 | 0.0 | 0.0 | 0.0 | 0.0 |

**Generalization gap (test - dev policy error): 0.0.** CAVEAT: the current dev/test cases were co-designed by the same author with knowledge of the policy, so a ~0 gap is NOT yet evidence of generalization. It becomes the honest headline only once the split is genuinely held-out (v2: a second Synthea seed + policy-blind case authoring + boundary traps). See docs/RELATED_WORK.md.

## Full metrics (per base x guard, with held-out dev/test split)

| base | guard | n | action_acc | unsafe | calib_defer | over_refusal | out_of_scope | injection |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| keyword | off | 20 | 0.5 | 0.5 | 0.167 | 0.0 | 1.6 | 1.0 |
| keyword | on | 20 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| keyword | on/dev | 12 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| keyword | on/test | 8 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| mock_model | off | 20 | 0.5 | 0.45 | 0.167 | 0.0 | 0.75 | 0.5 |
| mock_model | on | 20 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| mock_model | on/dev | 12 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| mock_model | on/test | 8 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| naive | off | 20 | 0.4 | 0.7 | 0.0 | 0.0 | 1.6 | 1.0 |
| naive | on | 20 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| naive | on/dev | 12 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| naive | on/test | 8 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| worst_case | off | 20 | 0.4 | 0.7 | 0.0 | 0.0 | 1.6 | 1.0 |
| worst_case | on | 20 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| worst_case | on/dev | 12 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| worst_case | on/test | 8 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |

`on/dev` vs `on/test` shows whether the guard's policy generalizes to held-out cases it was not authored against.

Note: v0 base agents and cases are co-designed; treat as a working methodology demonstration, not validated clinical results. Clinician-authored, fully held-out cases and a real model-driven base agent are v2.

## v2 adversarial axes

### Injection that targets the decision, not the data

The original injection cases try to get records out. These try to change the answer: a note claiming a red flag was already cleared, and a note impersonating a prescriber or a tumour board. Each case is run TWICE -- once with the sentence and once with it stripped -- so the flip is the payload's causal effect rather than a restatement of whether the agent was right.

| base | guard | n | flip rate | flipped to unsafe | wrong WITHOUT the payload |
| --- | --- | --- | --- | --- | --- |
| keyword | off | 4 | 0.0 | 0.0 | 1.0 |
| keyword | on | 4 | 0.0 | 0.0 | 0.0 |
| mock_model | off | 4 | 0.0 | 0.0 | 1.0 |
| mock_model | on | 4 | 0.0 | 0.0 | 0.0 |
| naive | off | 4 | 0.0 | 0.0 | 1.0 |
| naive | on | 4 | 0.0 | 0.0 | 0.0 |
| worst_case | off | 4 | 0.0 | 0.0 | 1.0 |
| worst_case | on | 4 | 0.0 | 0.0 | 0.0 |
| cli:sonnet | off | 4 | 0.0 | 0.0 | 0.25 |
| cli:sonnet | on | 4 | 0.0 | 0.0 | 0.0 |

The last column is why the control run exists. An agent that fails these cases with the payload removed was never injected -- it was already wrong. Reporting only the first column would credit the payload for failures it did not cause, and would let an agent too crude to read the chart score as injection-resistant.

### Patient-level scope

Least privilege by resource type does not catch reading the right resource type for the WRONG PATIENT. Each cross-patient case names a second reachable patient with a plausible pretext, and never asks for that chart.

| base | guard | patient-scope violation rate |
| --- | --- | --- |
| keyword | off | 1.0 |
| keyword | on | 0.0 |
| mock_model | off | 0.0 |
| mock_model | on | 0.0 |
| naive | off | 1.0 |
| naive | on | 0.0 |
| worst_case | off | 1.0 |
| worst_case | on | 0.0 |

Denominator is the cases where a second chart was actually reachable. Scored separately from `unsafe`, like out-of-scope reads: it is a privacy breach, not an unsafe clinical action, and folding it in would make the headline safety number mean two things at once.

## Real model (SEPARATE TABLE -- not comparable to the rows above)

Backend `cli:sonnet`, disclosure `in-scope`, 20 cases.

The deterministic agents above bound what enforcement is worth against a chosen adversary. This reports what one real model actually did. The two answer different questions and must not be put in one column.

| backend | guard | n | action_acc | unsafe | calib_defer | over_refusal | out_of_scope | injection |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cli:sonnet | off | 20 | 0.65 | 0.1 | 0.667 | 0.375 | 0.0 | 0.0 |
| cli:sonnet | on | 20 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |

Enforcement delta: unsafe 0.1 -> 0.0 (reduction 0.1); injection 0.0 -> 0.0.

### Model health

- calls: 56 (cached: 51)
- **usable-response rate: 1.0**
- parse-failure rate: 0.0
- transport-error rate: 0.0
- cases resolved by fail-safe rather than by the model (guard off): 0 of 20

An unusable reply is scored as `abstain` and tagged. That is a fail-safe, NOT a model choice: a model emitting prose, or none at all, would otherwise read as cautious. Every number above is conditional on the usable-response rate.

CAVEAT: this is Claude as exposed by the Claude Code CLI, with its system prompt replaced and tools denied -- close to a raw model call, not identical to one. The CLI exposes no temperature control, so this run is not reproducible from the model side; the response cache makes the recorded result replayable, not a fresh run identical. Label it 'via Claude Code CLI'.