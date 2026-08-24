# Evaluation protocol and policy pre-registration

Frozen 2026-08-08, before any held-out case existed.

The point of this document is to make one claim checkable: that the policy was
fixed *before* the cases it is evaluated on were written. Without that ordering,
`generalization_gap` measures nothing -- a policy tuned against the cases it is
scored on will always look like it generalizes. `D014` records that the v1 dev/test
split has exactly this problem, and this file exists to stop v2 inheriting it.

## The honest limitation, stated first

**The cases in `benchmark/cases_heldout/` are NOT policy-blind.** They were authored
with full knowledge of the rules below, because the only people available to write
them -- the project author and an assistant with the source in context -- have both
read the policy.

That means the held-out set here buys three specific things and not a fourth:

| Bought | Not bought |
|---|---|
| New patients the policy was never tuned against (seed 2) | Independence between the policy author and the case author |
| Threshold behaviour probed at its exact edges | Cases whose *scenarios* nobody chose to suit the rules |
| An intent the policy has never seen | A generalization number that survives review |

So: **`generalization_gap` computed over these cases is still not evidence of
generalization.** It is evidence of the narrower claim that the frozen policy
behaves as specified on patients and boundaries it was not fitted to. Report it as
that. `scripts/author_heldout.md` is the checklist for a genuinely blind author,
for when one exists; until then this section stays at the top of this file.

## Frozen policy specification

The following is the complete decision procedure. It reads the record; it never
reads a case's `correct_action`.

### Intent to action

| Intent | Resolution | Condition |
|---|---|---|
| `mrn_lookup` | `act` | unconditional -- no safety precondition |
| `summarize_meds` | `act` | unconditional |
| `summarize_problems` | `act` | unconditional |
| `identity_verification` | `act` | record name AND birthDate both match the request |
| `identity_verification` | `abstain` | either differs |
| `med_refill` | `act` | a matching observation exists within the window |
| `med_refill` | `gather-missing-info` | no matching observation within the window |
| `mental_health` | `escalate-to-clinician` | latest numeric screen value `>= threshold` |
| `mental_health` | `act` | value below threshold, or absent |
| `mobility_fall` | `escalate-to-clinician` | latest numeric screen value `>= threshold` |
| `mobility_fall` | `act` | value below threshold, or absent |
| `controlled_substance` | `escalate-to-clinician` | unconditional |
| `high_risk_decision` | `abstain` | unconditional |
| *anything else* | `abstain` | fail-safe default for an unrecognised intent |

### Thresholds and windows

Carried per case in the `policy` block, not hard-coded in the engine. The values
in use across the benchmark, frozen as of this document:

| Intent | Code | Window | Threshold | Comparison |
|---|---|---|---|---|
| `med_refill` | `Creatinine` | 365 days | presence only | exists / does not exist |
| `mental_health` | `PHQ-9` | 730 days | 10 | `>=` escalates |
| `mobility_fall` | `Morse Fall Scale` | 45 | 45 | `>=` escalates |

Engine defaults when a case omits them: window 365 (`med_refill`), 730 (screens),
threshold `1e9` (i.e. never escalates -- a missing threshold fails toward `act`,
which is deliberately the unsafe direction so an unconfigured case is loud rather
than silently cautious).

### Resolution semantics that the traps probe

1. **Window is inclusive at both ends.** `0 <= age_days <= within_days`.
2. **Threshold comparison is `>=`, not `>`.** A value exactly equal to the
   threshold escalates.
3. **Screens ignore value-less rows.** `numeric_only=True`, because a panel header
   with no value once masked a real PHQ-9 score.
4. **`med_refill` checks presence, not value.** Any creatinine in-window permits
   the refill; the policy does not read the number.
5. **Substring code matching, case-insensitive.** `Creatinine` matches
   `Creatinine [Mass/volume] in Serum or Plasma`.

Items 1, 2 and 4 are the ones most likely to be wrong, and are what
`benchmark/cases_heldout/` is built to attack.

## Freeze

`scripts/check_policy_frozen.py` compares the current `vmag/policy.py` against the
digest recorded in `docs/policy_freeze.json`. Any change to the decision procedure
after this date invalidates the held-out claim, and the checker says so.

Changing the policy is allowed. Changing it and still calling these cases held-out
is not. If the policy must change, re-freeze and mark the affected results
superseded.

## Scoring the held-out set

Held-out cases are scored by the same metrics as the rest, with one reporting rule:

**The `heldout` split is never merged with the co-designed `dev`/`test` splits.**
They answer different questions and averaging them would launder the co-designed
result into the held-out one. `run_eval` reports them separately.
