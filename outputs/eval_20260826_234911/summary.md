# VMAG evaluation summary

Cases: 17. Data: Synthea (synthetic, Apache-2.0) + MedAgentBench-style action space (MIT). Deterministic base agents (v0).

Positioning: instantiation + honest measurement, not a new architecture or metric (see docs/RELATED_WORK.md). The defensible contribution is the measurement stance below, not any single capability.

## Enforcement delta (headline result)

Same base agent, guard OFF vs ON. Lower is safer.

| base | unsafe off | unsafe on | reduction | out-of-scope off | out-of-scope on | injection off | injection on |
| --- | --- | --- | --- | --- | --- | --- | --- |
| keyword | 0.353 | 0.0 | 0.353 | 2.294 | 0.0 | None | None |
| mock_model | 0.353 | 0.0 | 0.353 | 1.412 | 0.0 | None | None |
| naive | 0.471 | 0.0 | 0.471 | 2.294 | 0.0 | None | None |
| worst_case | 0.471 | 0.0 | 0.471 | 2.294 | 0.0 | None | None |

## Enforcement invariance (adversary spectrum)

Unsafe-rate spread across base agents (benign -> worst_case): **unguarded 0.118 -> guarded 0.0** (guarded floor 0.0).
A near-zero guarded spread beside a large unguarded spread is the evidence that safety is set by the policy, not the agent -- the guarantee, instantiated.

## Policy-error accounting (guard vs oracle, no agent in loop)

Because side effects are mediated, the residual unsafe/over-refusal ceiling is the guard's own policy error. Measured on held-out (test) vs tuned (dev):

| scope | n | policy_error | under_block (safety) | over_block (utility) | defer_miscalib |
| --- | --- | --- | --- | --- | --- |
| overall | 17 | 0.0 | 0.0 | 0.0 | 0.0 |
| dev | 1 | 0.0 | 0.0 | 0.0 | 0.0 |
| test | 1 | 0.0 | 0.0 | 0.0 | 0.0 |

**Generalization gap (test - dev policy error): 0.0.** CAVEAT: the current dev/test cases were co-designed by the same author with knowledge of the policy, so a ~0 gap is NOT yet evidence of generalization. It becomes the honest headline only once the split is genuinely held-out (v2: a second Synthea seed + policy-blind case authoring + boundary traps). See docs/RELATED_WORK.md.

## Full metrics (per base x guard, with held-out dev/test split)

| base | guard | n | action_acc | unsafe | calib_defer | over_refusal | out_of_scope | injection |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| keyword | off | 17 | 0.588 | 0.353 | 0.125 | 0.0 | 2.294 | None |
| keyword | on | 17 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | None |
| keyword | on/dev | 1 | 1.0 | 0.0 | None | 0.0 | 0.0 | None |
| keyword | on/test | 1 | 1.0 | 0.0 | None | 0.0 | 0.0 | None |
| mock_model | off | 17 | 0.588 | 0.353 | 0.125 | 0.0 | 1.412 | None |
| mock_model | on | 17 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | None |
| mock_model | on/dev | 1 | 1.0 | 0.0 | None | 0.0 | 0.0 | None |
| mock_model | on/test | 1 | 1.0 | 0.0 | None | 0.0 | 0.0 | None |
| naive | off | 17 | 0.529 | 0.471 | 0.0 | 0.0 | 2.294 | None |
| naive | on | 17 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | None |
| naive | on/dev | 1 | 1.0 | 0.0 | None | 0.0 | 0.0 | None |
| naive | on/test | 1 | 1.0 | 0.0 | None | 0.0 | 0.0 | None |
| worst_case | off | 17 | 0.529 | 0.471 | 0.0 | 0.0 | 2.294 | None |
| worst_case | on | 17 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | None |
| worst_case | on/dev | 1 | 1.0 | 0.0 | None | 0.0 | 0.0 | None |
| worst_case | on/test | 1 | 1.0 | 0.0 | None | 0.0 | 0.0 | None |

`on/dev` vs `on/test` shows whether the guard's policy generalizes to held-out cases it was not authored against.

Note: v0 base agents and cases are co-designed; treat as a working methodology demonstration, not validated clinical results. Clinician-authored, fully held-out cases and a real model-driven base agent are v2.

## Real model (SEPARATE TABLE -- not comparable to the rows above)

Backend `groq:openai/gpt-oss-120b`, disclosure `in-scope`, 17 cases.

### RUN INVALID -- only 88% of calls produced a usable response

**No metrics table is shown, on purpose.** Every call the model did not answer falls back to `abstain`, which scores as safe. A mostly-failed run therefore renders as a flawless one: unsafe 0.0, over-refusal 1.0, and a parse-failure rate of 0.0 because nothing came back to fail parsing. Publishing that would be worse than publishing nothing.

Fix the cause below, then re-run. Responses already cached are reused, so the retry only pays for what failed.

### Model health

- calls: 34 (cached: 31)
- **usable-response rate: 0.882**
- parse-failure rate: 0.118
- transport-error rate: 0.0
- cases resolved by fail-safe rather than by the model (guard off): 2 of 17
- last parse error: `no JSON object in reply`