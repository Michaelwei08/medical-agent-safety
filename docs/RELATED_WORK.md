# Related Work & Honest Positioning

A multi-agent adversarial prior-art review (2026-07-11) tested eight novelty
claims for VMAG. **All eight were refuted** — every individual thing VMAG
measures has prior art, several near-exact. This file records that honestly so
the project is never pitched as inventing what it did not.

## Do not claim as novel

| VMAG element | Prior art that already does it |
| --- | --- |
| Out-of-model, data-driven guard that decides the safe action | **GuardAgent** + EICU-AC healthcare benchmark (arXiv:2406.09187, ICML 2025); **ShieldAgent** (2503.22738); **Progent** (2504.11703); **AgentSpec** (2503.18666); **Conseca** (2501.17070); safe-RL shielding (Alshiekh et al., AAAI 2018) |
| Unsafe-action rate decoupled from answer correctness | **ST-WebAgentBench** CuP (2410.06703); **tau-bench**; **ToolEmu** (2309.15817); **AgentDojo** (2406.13352); medical: **MedCUA-Bench** (2606.03203) |
| Least-privilege / data-minimization metric | **FHIR-AgentBench** "Retrieval Precision" (2509.19319); **MedPriv-Bench** (2603.14265); ToolPrivBench (2606.20023) |
| Prompt injection in retrieved records + exfiltration rate | **InjecAgent** (2403.02691) — near-exact, incl. a medical-records exfiltration case; **AgentDojo**; EHR-specific **QFIRE** (medRxiv, Jun 2026) |
| Deferral / escalate-to-clinician as a scored discrete action | Learning-to-defer: **CoDoC** (Nature Medicine 2023), Mozannar & Sontag; **MediQ** (2406.00922); **ClinDet-Bench** (2602.22771); selective-prediction survey (TACL 2024) |
| "Gather missing info" gated by a store-absence precondition | **MedAgentBench** itself (Task 10: no HbA1c / >1yr → order; naloxone; catheter) |
| Joint over-refusal + safety on one set | **XSTest** (2308.01263); **OR-Bench** (2405.20947); Health-ORSC-Bench |
| Multi-tag safety-failure taxonomy on an agentic substrate | **ST-WebAgentBench**; χ-Bench (2605.16679) |

## The one defensible framing (state carefully, never "first")

VMAG is an **instantiation + honest measurement**, not a new architecture or a
new metric. The composition that the review could *not* find done together in a
clinical FHIR setting is a **measurement stance**, not a capability:

1. **Enforcement delta** — the reduction in unsafe-action rate from wrapping the
   *same* base agent with the guard (a clean causal intervention, not a
   cross-system comparison of different agents).
2. **Adversary-strength invariance** — the guarded unsafe rate stays ~flat as the
   base agent sweeps benign → worst-case, because every side effect is mediated.
   The flat guarded line beside a rising unguarded line is the evidence for the
   shielding-style guarantee, *instantiated* on a clinical substrate.
3. **Policy-error accounting + generalization gap** — because side effects are
   mediated, the residual unsafe rate equals the guard's own policy-error rate.
   Measuring that on **held-out, untuned** cases is what lets "verifiable" earn
   its place, and converts the safety claim into a falsifiable, decomposable
   number rather than an assertion.

Phrase as: *"to our knowledge not previously reported together in a clinical
FHIR agent setting."* Never "first," never "novel architecture," never "provably
safe" (the guard is only as safe as its policy — condition every claim on
"policy correct AND side effects mediated").

## Honesty rules carried into the project

- Co-designed `unsafe=0.0` numbers are a **methodology demonstration**, not
  validated results, until frozen-policy held-out and second-cohort numbers exist.
- Illustrative thresholds (PHQ-9≥10, creatinine 365d, etc.) are author-set,
  **clinician-review-pending** — not clinically validated, not deployment-ready.
- The deterministic mock agents demonstrate the **enforcement mechanism**, not
  real-model safety; real-model rates require the Claude adapter and a separate,
  clearly-labeled table.
- Synthea has limited distributional fidelity; external/EHR validity is out of
  scope and MIMIC-based validation is deliberately deferred (no credentialed data).
