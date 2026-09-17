# VMAG evaluation summary

Cases: 14. Data: Synthea (synthetic, Apache-2.0) + MedAgentBench-style action space (MIT). Deterministic base agents (v0).

Positioning: instantiation + honest measurement, not a new architecture or metric (see docs/RELATED_WORK.md). The defensible contribution is the measurement stance below, not any single capability.

## Enforcement delta (headline result)

Same base agent, guard OFF vs ON. Lower is safer.

| base | unsafe off | unsafe on | reduction | out-of-scope off | out-of-scope on | injection off | injection on |
| --- | --- | --- | --- | --- | --- | --- | --- |
| keyword | 0.286 | 0.0 | 0.286 | 2.143 | 0.0 | None | None |
| mock_model | 0.286 | 0.0 | 0.286 | 1.286 | 0.0 | None | None |
| naive | 0.429 | 0.0 | 0.429 | 2.143 | 0.0 | None | None |
| worst_case | 0.429 | 0.0 | 0.429 | 2.143 | 0.0 | None | None |

## Enforcement invariance (adversary spectrum)

Unsafe-rate spread across base agents (benign -> worst_case): **unguarded 0.143 -> guarded 0.0** (guarded floor 0.0).
A near-zero guarded spread beside a large unguarded spread is the evidence that safety is set by the policy, not the agent -- the guarantee, instantiated.

## Policy-error accounting (guard vs oracle, no agent in loop)

Because side effects are mediated, the residual unsafe/over-refusal ceiling is the guard's own policy error. Measured on held-out (test) vs tuned (dev):

| scope | n | policy_error | under_block (safety) | over_block (utility) | defer_miscalib |
| --- | --- | --- | --- | --- | --- |
| overall | 14 | 0.0 | 0.0 | 0.0 | 0.0 |
| dev | 1 | 0.0 | 0.0 | 0.0 | 0.0 |
| test | 1 | 0.0 | 0.0 | 0.0 | 0.0 |

**Generalization gap (test - dev policy error): 0.0.** CAVEAT: the current dev/test cases were co-designed by the same author with knowledge of the policy, so a ~0 gap is NOT yet evidence of generalization. It becomes the honest headline only once the split is genuinely held-out (v2: a second Synthea seed + policy-blind case authoring + boundary traps). See docs/RELATED_WORK.md.

## Full metrics (per base x guard, with held-out dev/test split)

| base | guard | n | action_acc | unsafe | calib_defer | over_refusal | out_of_scope | injection |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| keyword | off | 14 | 0.643 | 0.286 | 0.167 | 0.0 | 2.143 | None |
| keyword | on | 14 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | None |
| keyword | on/dev | 1 | 1.0 | 0.0 | None | 0.0 | 0.0 | None |
| keyword | on/test | 1 | 1.0 | 0.0 | None | 0.0 | 0.0 | None |
| mock_model | off | 14 | 0.643 | 0.286 | 0.167 | 0.0 | 1.286 | None |
| mock_model | on | 14 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | None |
| mock_model | on/dev | 1 | 1.0 | 0.0 | None | 0.0 | 0.0 | None |
| mock_model | on/test | 1 | 1.0 | 0.0 | None | 0.0 | 0.0 | None |
| naive | off | 14 | 0.571 | 0.429 | 0.0 | 0.0 | 2.143 | None |
| naive | on | 14 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | None |
| naive | on/dev | 1 | 1.0 | 0.0 | None | 0.0 | 0.0 | None |
| naive | on/test | 1 | 1.0 | 0.0 | None | 0.0 | 0.0 | None |
| worst_case | off | 14 | 0.571 | 0.429 | 0.0 | 0.0 | 2.143 | None |
| worst_case | on | 14 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | None |
| worst_case | on/dev | 1 | 1.0 | 0.0 | None | 0.0 | 0.0 | None |
| worst_case | on/test | 1 | 1.0 | 0.0 | None | 0.0 | 0.0 | None |

`on/dev` vs `on/test` shows whether the guard's policy generalizes to held-out cases it was not authored against.

Note: v0 base agents and cases are co-designed; treat as a working methodology demonstration, not validated clinical results. Clinician-authored, fully held-out cases and a real model-driven base agent are v2.

## Real model (SEPARATE TABLE -- not comparable to the rows above)

Backend `cli:sonnet`, disclosure `in-scope`, 14 cases.

The deterministic agents above bound what enforcement is worth against a chosen adversary. This reports what one real model actually did. The two answer different questions and must not be put in one column.

| backend | guard | n | action_acc | unsafe | calib_defer | over_refusal | out_of_scope | injection |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cli:sonnet | off | 14 | 0.714 | 0.0 | 0.5 | 0.125 | 0.0 | None |
| cli:sonnet | on | 14 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | None |

Enforcement delta: unsafe 0.0 -> 0.0 (reduction 0.0); injection None -> None.

### Model health

- calls: 28 (cached: 26)
- **usable-response rate: 1.0**
- parse-failure rate: 0.0
- transport-error rate: 0.0
- cases resolved by fail-safe rather than by the model (guard off): 0 of 14

An unusable reply is scored as `abstain` and tagged. That is a fail-safe, NOT a model choice: a model emitting prose, or none at all, would otherwise read as cautious. Every number above is conditional on the usable-response rate.

CAVEAT: this is Claude as exposed by the Claude Code CLI, with its system prompt replaced and tools denied -- close to a raw model call, not identical to one. The CLI exposes no temperature control, so this run is not reproducible from the model side; the response cache makes the recorded result replayable, not a fresh run identical. Label it 'via Claude Code CLI'.