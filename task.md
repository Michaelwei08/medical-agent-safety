# TASKS.md

## Done (v0)
- [x] Scaffold `own/medical_agent_safety/` with governance docs.
- [x] Decide v1 agent mode: deterministic rule-based agents (no API cost).
- [x] Acquire public data: Synthea FHIR cohort + MedAgentBench (MIT).
- [x] Define the clinical-agent action space and tool set (read/search, draft_order, send_message, escalate).
- [x] Finalize the case schema (`vmag/benchmark.py`) and ground cases in real Synthea patients.
- [x] Author a 9-case seed benchmark across all scenario tags.
- [x] Implement the runtime guard (data-driven policy + least-privilege scope + injection immunity).
- [x] Implement deterministic replay + structured scoring (utility / unsafe-action / calibrated-deferral / over-refusal / data-exposure / injection).
- [x] Run baselines end-to-end: ambient vs prompt_only vs vmag; write `outputs/eval_<ts>/`.

## Done (v1 -- enforcement-delta + honest positioning)
- [x] Refactor to base-agent (Plan) + guard (enforce) so guard on/off is a toggle on one agent.
- [x] Add enforcement_delta, enforcement_invariance (adversary spectrum incl. worst_case), and policy_error accounting (guard vs oracle).
- [x] Adversarial prior-art review (workflow); record verdicts + honest positioning in `docs/RELATED_WORK.md`.
- [x] Add dev/test split scaffolding + generalization_gap reporting (with co-design caveat).

## Next (v2 -- priority order, from the design workflow)
- [~] GENUINE held-out -- PARTIALLY done. Everything except the one part that needs another person.
  - [x] Pre-register + freeze the policy in `docs/evaluation_protocol.md`; digest enforced by `scripts/check_policy_frozen.py` (drift fails).
  - [x] Second Synthea cohort (`-s 2`): 12 patients, zero overlap with seed 1, at `data/synthea_s2/fhir/`.
  - [x] Recency and threshold boundary traps + `heldout_unseen_intent`: 7 cases in `benchmark/cases_heldout/`, scored separately and never merged with dev/test. Frozen policy: 0/7 error.
  - [x] `scripts/check_traps_discriminate.py`: injects the bug each trap targets and requires it to flip. 5/5 caught. Found one overclaimed rationale and one spec clause with no trap (value-less rows), now reported as UNCOVERED.
  - [ ] **Author cases WITHOUT inspecting the policy.** NOT done and not doable by the policy author or by an assistant with the source in context. Brief ready at `scripts/author_heldout.md`; needs a second person. Until then `generalization_gap` is still not evidence of generalization -- see D037.
- [x] Freshest defensible axes -- DONE. Benchmark is now 20 cases (12 dev / 8 test).
  - [x] `injection_decision_001/002` + `injection_authority_001/002`: payloads that target the DECISION, not the data. Scored by `injection_decision_flip_rate` from a PAIRED COUNTERFACTUAL (same case run with the payload and with the record served stripped), plus `wrong_without_injection_rate` so baseline failure is not scored as injection.
  - [x] `cross_patient_001/002` + `patient_scope_violation_rate`, denominated over cases where a second chart is actually reachable. `Plan.cross_patient_reads` gives agents the ability to violate, without which the metric would describe the harness.
  - [x] Deterministic baseline: scope violation 1.0 -> 0.0 under the guard; flip 0.0 with wrong-without 1.0, i.e. the stand-ins fail at baseline rather than being injected.
  - [ ] **The real test is a model.** Run `python -m vmag.run_eval --model-backend cli:sonnet` -- the stand-ins cannot be flipped because they never read the chart narrative.
- [ ] Multi-resource policy: extend `fhir_store` to parse AllergyIntolerance; add `allergy_contraindication`, `drug_interaction`, `duplicate_order` intents (+ clean should-ACT twins).
- [~] Real model behind a `complete()` seam. **Seam is built and tested; no model has been run yet.**
  - [x] `vmag/llm.py`: `complete()` with `VMAG_MODEL=mock|<provider>:<model>`, on-disk response cache, `VMAG_LLM_OFFLINE=1` for credential-free reproduction, stdlib-only HTTP (no vendor SDK). Providers: ollama, groq, gemini, nvidia, openrouter, cerebras, stanford, anthropic.
  - [x] `vmag/model_agents.py`: prompt builder, JSON plan parser, `make_model_agent()`. No `follow_injection` shortcut -- a model counts as injected only if it actually addresses a `send_message` to the injected recipient. Parse failures are tagged `unusable="parse"` and counted, never laundered into a cautious-looking `abstain`.
  - [x] `scripts/smoke_model_seam.py`: 12 checks, no key and no network. Confirms the guard holds 14/14 against a maximally unsafe model, that the injected sentence actually reaches the model, and that offline mode refuses an uncached live call.
  - [x] `cli:<model>` backend using the local `claude` CLI, so a real Claude runs on a subscription with no API budget. Runs in an empty temp dir because `claude` auto-discovers CLAUDE.md and this repo's states the answer key. Cannot be exercised from inside a Claude Code session (nested OAuth refresh fails).
  - [x] Provenance gate: `complete(..., provenance="controlled-access")` raises on every remote backend, `cli` included, and permits only `mock`/`ollama`.
  - [ ] **USER ACTION:** run `python scripts/check_cli_backend.py` from your own terminal to confirm the CLI backend end to end. One command, no setup.
  - [x] `run_eval --model-backend <spec>` runs a real model over all cases guard off/on and writes `model_metrics.csv`, `model_per_case.csv`, `model_health.csv` plus a separate `summary.md` section. Deterministic output verified byte-identical, so the addition is purely additive. Health block prints the parse-failure rate and warns above 0.1; the CLI backend gets its own temperature/harness caveat automatically.
  - [x] `runtime.run_case` now attaches the proposing Plan to the Decision, so per-case reporting can tell "the agent chose this" from "we could not read the answer and fell back". Nothing in scoring reads it.
  - [ ] Then a real backend on all 14 cases. Order: CLI (free, today) -> local Ollama (reproducible, temperature-pinned) -> Stanford Gateway or API if a PTA appears. See `docs/MODEL_ACCESS.md`.
  - [x] Reported plainly: Claude IS already safe on these cases (unsafe 0.0), so the guard buys it utility rather than safety.
  - [x] Second model run (`ollama:qwen2.5:7b`, temperature-pinned): unsafe 0.35, calibrated deferral 0.0. The safety saturation is NOT general -- see D036. Headline is the pair, never one half.
- [ ] Expand to ~50 clinician-reviewable cases balanced across tuning/held-out and failure modes; add a guard-strictness knob to trace the safety-utility frontier.
- [ ] Wire MedAgentBench's 300 tasks as an external comparison; map their tasks to VMAG intents.
- [ ] Write `docs/evaluation_protocol.md` and a 2-page writeup -- framed strictly per `docs/RELATED_WORK.md` (no "novel/first/provably safe").

## Outreach (after v1 artifacts exist)
- [ ] Draft cold-email pitch + repo link for HealthRex (Jonathan Chen) and Daneshjou lab.
- [ ] Add VMAG as a portfolio project on the personal website (`../personal_website`).
