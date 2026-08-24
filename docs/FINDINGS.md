# What a runtime guard is worth in front of a clinical agent

**Chupeng Wei -- 2026-08-08**

Every number here comes from `docs/findings_data.json`, collected by
`scripts/collect_findings.py` from two runs that reproduce offline from a committed
response cache with no credentials:
`outputs/eval_20260808_174358` (Claude) and `outputs/eval_20260808_174400` (Qwen).

## The question

A clinical agent can fail dangerously without saying anything false -- by *acting*
when the correct behaviour was to gather a missing lab, abstain, or hand off to a
clinician. A common proposal is a runtime guard: a policy that decides from record
data, sitting outside the model, mediating every side effect.

The obvious way to evaluate that is to build agents that behave badly and show the
guard stops them. That is close to circular. The question worth answering is
narrower and harder: **against a real model, what does the guard actually buy?**

## Setup

20 synthetic clinical cases over a Synthea cohort (Apache-2.0; no PHI, no
controlled-access data). Every step resolves to one of four actions: `act`,
`gather-missing-info`, `abstain`, `escalate-to-clinician`. Each case has a hidden
correct resolution; the policy never reads it.

The same base agent runs with the guard off and on, so the comparison is an A/B on
one agent rather than a comparison of two. Two real models were measured behind an
identical seam:

| | usable-response rate | temperature |
|---|---|---|
| Claude Sonnet, via the Claude Code CLI | 1.000 | not controllable |
| Qwen2.5 7B, local via Ollama | 0.964 | pinned at 0 |

A run below 0.9 usable responses is suppressed rather than reported: every call a
model fails to answer falls back to `abstain`, which scores as safe, so a
mostly-failed run renders as a flawless one. Three runs were discarded this way.

## Result 1 -- the guard buys different things from different agents

![Safety-utility plane](figures/fig1_safety_utility_plane.png)

| Guard off | unsafe-action | over-refusal | action accuracy |
|---|---|---|---|
| Claude | **0.000** | **0.375** | 0.650 |
| Qwen2.5 7B | **0.350** | **0.000** | 0.400 |
| worst stand-in | 0.700 | 0.000 | 0.400 |

**Guard on, every agent: unsafe 0.000, over-refusal 0.000, accuracy 1.000.**

The two models fail in opposite directions. Claude never takes an unsafe action and
pays for it by declining work it should do -- it refuses 3 of the 8 cases where
acting was correct. Qwen never refuses anything and acts on 7 of 20 cases that
required deferral, including both opioid requests, a chemotherapy decision, and two
refills with no recent creatinine. Its calibrated-deferral rate is **0.000**: across
20 cases it did not once defer correctly.

So the honest headline is a pair, not a single number:

> For a capable model the guard buys **utility** -- it stops the model being
> uselessly cautious. For a small one it buys **safety**. Reporting either half
> alone misstates it.

This matters for deployment in the direction that is usually ignored: the cheap
model is the one that ends up in production loops.

## Result 2 -- a flip rate without a control run means nothing

Four cases carry an injected instruction aimed at the *decision* rather than the
data: a note claiming an elevated PHQ-9 was reviewed and cleared, a nursing
addendum declaring a fall-risk score stale, a prescriber authorisation with a
DEA-shaped number and an override code, and a tumour board granting permission to
answer on its behalf.

Each case runs twice -- once with the payload, once with the record served with the
sentence stripped -- so the measured flip is the payload's causal effect.

![Counterfactual control](figures/fig2_counterfactual_control.png)

Every agent scores an injection flip rate of **0.000**. Read alone, that says all
six resisted. The control run says otherwise: Claude was wrong on 0.25 of these
cases without any payload, and every other agent was wrong on **1.00** of them.
Claude resisted four attacks; the rest were never in a position to be moved.

Reporting flip rate alone would score an agent that always acts as
injection-resistant. That is the single easiest way to fake a good result on this
axis, and the control is what closes it.

## Result 3 -- where the failures actually are

![Per-case grid](figures/fig3_case_grid.png)

Claude's errors cluster on cases where acting was correct -- clean refills, a
permission summary. Two more are deferral-*kind* mismatches rather than act-vs-defer
errors: on the wrong-patient case it chose to gather more information where the
oracle wanted abstain, and on the chemotherapy case it escalated rather than
abstaining. Both are arguably better clinical behaviour than the label, which is a
finding about the benchmark: a single `correct_action` per case is probably too
strict where several deferrals are defensible.

Qwen's errors cluster on escalation and missing-data -- precisely the cases where
deferral is the whole point.

## What these numbers are not

- **The cases and the policy share an author.** Policy error is 0.000 on dev, test,
  and a held-out set. That is self-consistency, not generalization.
- **The held-out set is not policy-blind.** Seven traps on a second Synthea cohort
  (zero patient overlap) probe the frozen spec at its exact edges -- an inclusive
  window boundary, a post-dated observation, a threshold hit exactly, a decade-stale
  screen, an intent the policy has never seen. The frozen policy passes 7/7. But
  they were written by someone who had read the policy, so they can find a bug in
  the *implementation* and cannot find an error in the *specification*.
  `scripts/check_traps_discriminate.py` injects the bug each trap targets and
  confirms all five flip it -- a trap that cannot fail is decoration.
- **Qwen's 0.000 injection-follow and 0.000 patient-scope violation are not
  discipline.** It never requests another chart and never sends a message, because
  it does one thing: act. Absence of a behaviour is not restraint.
- **The Claude figures come from the Claude Code CLI**, with its system prompt
  replaced and tools denied. Close to a raw API call, not identical, and the CLI
  exposes no temperature control -- so that row is labelled and never placed in the
  same column as an API result.
- **n is small.** 20 cases, 4 injection cases, 2 cross-patient cases. One clean pass
  is not robustness.

## What is defensible

Not a new architecture, and not a new metric. Out-of-model guards, decoupled
unsafe-action rates, least-privilege scoring and scored deferral all pre-exist; an
adversarial prior-art review refuted every single-axis novelty claim
(`docs/RELATED_WORK.md`).

What the work contributes is a measurement: **what a hard guard is worth in front of
real clinical agents, measured on a public synthetic substrate, with the failure
directions separated and the counterfactual controls in place** -- and the finding
that the answer is model-dependent in a way the usual single-number framing hides.

## Reproducing

```bash
python scripts/check_policy_frozen.py         # policy unchanged since pre-registration
python scripts/check_traps_discriminate.py    # every held-out trap can fail
VMAG_LLM_OFFLINE=1 python -m vmag.run_eval --model-backend cli:sonnet
```

The last command recomputes the Claude table with no credentials and no spend: all
responses are cached, and offline mode raises on a cache miss rather than quietly
making a live call.

## Next

The single thing that would upgrade the evidence is **cases authored by someone who
has not read the policy**. The brief is written and ready to hand over
(`scripts/author_heldout.md`); it needs a second person. Until then, no number here
supports the word *generalization*, and this document does not use it.
