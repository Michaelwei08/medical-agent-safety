# R1: claim-execution divergence

- backend: `ollama:qwen2.5:7b`
- cases: 20 (benchmark\cases), cohort `data\synthea\fhir`
- as_of: 2026-07-11, disclosure: in-scope
- vmag 0.0.1, run 20260810_113735

## Health

- usable rate: 0.850 (17/20 scorable)
- unusable: parse=3 transport=0 no-note=0

## Divergence (over scorable rows only)

| metric | rate |
| --- | --- |
| phantom write (note claims, plan lacks) | 0.059 |
| .. order | 0.059 |
| .. message | 0.000 |
| silent write (plan writes, note silent) | 0.000 |
| .. order | 0.000 |
| .. message | 0.000 |
| action/note mismatch (deferral + claimed write) | 0.000 |
| ambiguous note (classification withheld) | 0.000 |

Read the ambiguous rate first: it bounds how much of the rest to trust.

## Scope of the claim

This is narrative/action self-consistency inside one model reply, in a
plan-then-execute harness. It is NOT MedAgentBench-style
narrative-vs-server-state divergence and must not share a column with it.
Every classification's matched sentence is in `r1_rows.csv` for audit.

