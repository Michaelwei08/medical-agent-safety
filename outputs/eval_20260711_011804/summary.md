# VMAG evaluation summary

Cases: 14. Data: Synthea (synthetic, Apache-2.0) + MedAgentBench-style action space (MIT). Deterministic base agents (v0).

## Enforcement delta (the headline result)

Same base agent, guard OFF vs ON. Lower is safer.

| base | unsafe off | unsafe on | reduction | out-of-scope off | out-of-scope on | injection off | injection on |
| --- | --- | --- | --- | --- | --- | --- | --- |
| naive | 0.714 | 0.0 | 0.714 | 1.571 | 0.0 | 1.0 | 0.0 |
| keyword | 0.5 | 0.0 | 0.5 | 1.571 | 0.0 | 1.0 | 0.0 |
| mock_model | 0.429 | 0.0 | 0.429 | 0.714 | 0.0 | 0.5 | 0.0 |

The guard makes safety independent of the base agent: any base, wrapped, converges to the same low unsafe-action rate.

## Full metrics (per base x guard, with held-out dev/test split)

| base | guard | n | action_acc | unsafe | calib_defer | over_refusal | out_of_scope | injection |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| naive | off | 14 | 0.429 | 0.714 | 0.0 | 0.0 | 1.571 | 1.0 |
| naive | on | 14 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| naive | on/dev | 9 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| naive | on/test | 5 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| keyword | off | 14 | 0.571 | 0.5 | 0.25 | 0.0 | 1.571 | 1.0 |
| keyword | on | 14 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| keyword | on/dev | 9 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| keyword | on/test | 5 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| mock_model | off | 14 | 0.571 | 0.429 | 0.25 | 0.0 | 0.714 | 0.5 |
| mock_model | on | 14 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| mock_model | on/dev | 9 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| mock_model | on/test | 5 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |

`on/dev` vs `on/test` shows whether the guard's policy generalizes to held-out cases it was not authored against.

Note: v0 base agents and cases are co-designed; treat as a working methodology demonstration, not validated clinical results. Clinician-authored, fully held-out cases and a real model-driven base agent are v2.