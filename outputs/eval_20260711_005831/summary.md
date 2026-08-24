# VMAG evaluation summary

Cases: 9. Data: Synthea (synthetic, Apache-2.0) + MedAgentBench-style action space (MIT). Deterministic rule-based agents (v0).

| agent | n_cases | action_accuracy | unsafe_action_rate | calibrated_deferral | over_refusal_rate | mean_out_of_scope_reads | injection_follow_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ambient | 9 | 0.444 | 0.667 | 0.0 | 0.0 | 1.556 | 1.0 |
| prompt_only | 9 | 0.556 | 0.444 | 0.2 | 0.0 | 1.556 | 1.0 |
| vmag | 9 | 1.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |

Lower is better: `unsafe_action_rate`, `over_refusal_rate`, `mean_out_of_scope_reads`, `injection_follow_rate`.
Higher is better: `action_accuracy`, `calibrated_deferral`.

Note: v0 agents and cases are co-designed; treat these as a working methodology demonstration, not validated clinical results. Clinician-authored cases are a v2 item.