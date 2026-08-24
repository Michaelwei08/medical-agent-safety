# Verifiable Medical Agent Guard

Verifiable Medical Agent Guard (VMAG) is a research project on making clinical AI
**agents** — LLM systems that take actions in a clinical workflow (retrieve records,
draft orders, send messages, triage, summarize) — behave safely and verifiably.

The core claim: clinical agents fail dangerously not only by producing wrong
content, but by *acting* when the correct behavior is to gather missing
information, abstain, or escalate to a licensed clinician. VMAG measures that
behavior and enforces it with a runtime guard that sits **outside** the LLM.

This is a research artifact, not a deployable clinical system, and it uses only
public/synthetic vignettes — no PHI and no controlled data.

## Research focus

- Safe tool-use for clinical LLM agents (which action, when, with what data)
- Appropriate deferral and escalation ("know when to hand off to a clinician")
- Permission boundaries and least-privilege data exposure for medical agents
- Calibrated abstention vs. over-refusal, and unsafe over-confidence
- Honest, leakage-aware evaluation of utility / safety / privacy tradeoffs

## What is and isn't novel (read this first)

An adversarial prior-art review refuted every individual-axis novelty claim:
out-of-model guards (GuardAgent, ShieldAgent, Progent), decoupled unsafe-action
rate (ST-WebAgentBench, ToolEmu, AgentDojo), least-privilege scoring
(FHIR-AgentBench), record-borne injection + exfiltration (InjecAgent, QFIRE),
scored deferral (learning-to-defer, MediQ), and absence-precondition gathering
(MedAgentBench) all pre-exist. See [`docs/RELATED_WORK.md`](docs/RELATED_WORK.md).

VMAG is therefore framed as an **instantiation + honest measurement**, not a new
architecture. Its one defensible contribution is a *measurement stance* — the
**enforcement delta**, **adversary-strength invariance**, and **policy-error /
generalization-gap accounting** measured together on a public, synthetic clinical
FHIR substrate — stated only as "to our knowledge not reported together in this
setting," never "first."

## Why this project

VMAG retargets prior work to the clinical-agent setting:

- **Permission firewall / runtime enforcement** — from the Personal Agent
  Permission Firewall (`../limitation_of_ai`, PAPF): capability compilation,
  policy validation, enforcement mediation, consent handling, redaction, audit
  logs.
- **Benchmark schema + structured scoring + reproducible harness** — from
  Checkpointed Adaptive Reasoning (`../streaming_thinking`, CAR).
- **Leakage-aware, "these numbers are not comparable" evaluation discipline** —
  the same rigor applied in the BAMM Raman work and the Ash viral-detection work.

## Target use

A concrete, verifiable artifact suitable for (a) a research-lab entry ticket
(clinical-LLM evaluation and medical-agent safety) and (b) an AI-healthcare
internship portfolio centerpiece.

## Repo layout

- `benchmark/` — synthetic clinical-agent traces and the case schema.
- `src/` — agent environment, runtime guard, baselines, scoring (to be built).
- `docs/` — project brief, evaluation protocol, and design notes.
- `CONTINUITY.md` — append-only goal/decision/state log (read first).
- `CLAUDE.md` — repo guidance for AI coding sessions.
- `task.md` — actionable checklist.

## Status

Scaffolding stage. No experiments have been run yet.
