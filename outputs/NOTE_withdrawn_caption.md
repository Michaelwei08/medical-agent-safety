# NOTE on runs produced before 2026-08-26

Every `summary.md` in this directory dated before 2026-08-26 contains a section
captioned **"Enforcement invariance (adversary spectrum)"** whose closing line
reads:

> *"A near-zero guarded spread beside a large unguarded spread is the evidence
> that safety is set by the policy, not the agent -- the guarantee,
> instantiated."*

**That caption is WITHDRAWN.** It is not evidence of anything. `Guard.review()`
sets the action from `evaluate_policy(env)` and never reads the agent's plan;
side effects are rebuilt from policy, `follow_injection` is hard-coded `False`
and `cross_patient_reads` hard-coded empty. So the guarded spread is identically
0.0 for ANY set of base agents. Measured on 2026-08-26: a uniformly random agent,
a null agent and a maximally malicious agent all score exactly 1.0 / 0.0 / 1.0
guarded -- the same as Claude Sonnet on all seven metrics. `guard.py`'s own
docstring already said so.

The unguarded spread in those sections is not a finding either: those rows are
the hand-built stand-ins, so their spread is a design choice, not a measurement.

46 affected files. **They are deliberately NOT rewritten.** They record what was
reported at the time, and this project appends rather than rewriting history
(see `CONTINUITY.md`). Runs from 2026-08-26 onward carry the corrected caption
and the fields `guarded_spread_is_tautological` and
`unguarded_spread_is_a_design_fact` in `run_metadata.json`.

Nothing else in those runs is affected: the enforcement delta, policy-error
accounting, per-case rows and response-health blocks all stand.
