"""Run the R1 claim-execution-divergence measurement over the benchmark.

    python scripts/run_r1.py --backend mock
    python scripts/run_r1.py --backend ollama:qwen2.5:7b
    VMAG_LLM_OFFLINE=1 python scripts/run_r1.py --backend ollama:qwen2.5:7b   # replay

Writes outputs/r1_<ts>/ with r1_rows.csv (one auditable row per case, including the
matched sentence for every claim), summary.md and run_metadata.json.

Reporting rules enforced here, not left to discipline:
  - rates are computed over SCORABLE rows only; unusable replies are counted and
    printed, never coerced into a category (D018);
  - the ambiguous rate is printed beside every divergence rate, because it bounds
    how much of the classification the reader should trust;
  - a run whose usable rate is too low is marked INVALID and its rates suppressed,
    so a dead backend cannot render as a clean result (D026 / D034).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vmag import __version__                       # noqa: E402
from vmag import r1_divergence as R1               # noqa: E402
from vmag.benchmark import load_cases              # noqa: E402
from vmag.environment import Environment           # noqa: E402
from vmag.fhir_store import FhirStore              # noqa: E402

MIN_USABLE_RATE = 0.5

FIELDS = [
    "case_id", "tag", "action", "unusable", "parse_error",
    "plan_order", "plan_message", "note_order", "note_message",
    "amb_order", "amb_message",
    "phantom_order", "phantom_message", "silent_order", "silent_message",
    "action_note_mismatch", "span_order", "span_message", "note",
]


def row_dict(r: R1.R1Row) -> dict:
    return {
        "case_id": r.case_id, "tag": r.tag, "action": r.action,
        "unusable": r.unusable or "", "parse_error": r.parse_error,
        "plan_order": r.plan_order, "plan_message": r.plan_message,
        "note_order": r.note_order, "note_message": r.note_message,
        "amb_order": r.amb_order, "amb_message": r.amb_message,
        "phantom_order": r.phantom_order, "phantom_message": r.phantom_message,
        "silent_order": r.silent_order, "silent_message": r.silent_message,
        "action_note_mismatch": r.action_note_mismatch,
        "span_order": r.span_order, "span_message": r.span_message,
        "note": (r.note or "").replace("\n", " ")[:600],
    }


def fmt(value) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="mock",
                    help="mock | ollama:<model> | <provider>:<model>")
    ap.add_argument("--cases-dir", default=os.path.join("benchmark", "cases"))
    ap.add_argument("--fhir-dir", default=os.path.join("data", "synthea", "fhir"))
    ap.add_argument("--as-of", default="2026-07-11")
    ap.add_argument("--disclosure", default="in-scope",
                    choices=("in-scope", "none", "all"))
    ap.add_argument("--output-root", default="outputs")
    ap.add_argument("--label", default="", help="suffix for the output directory")
    args = ap.parse_args()

    store = FhirStore(args.fhir_dir)
    cases = load_cases(args.cases_dir)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(args.output_root, f"r1_{ts}" + (f"_{args.label}" if args.label else ""))
    os.makedirs(out_dir, exist_ok=True)

    print(f"R1 claim-execution divergence")
    print(f"  backend   : {args.backend}")
    print(f"  cases     : {len(cases)} from {args.cases_dir}")
    print(f"  cohort    : {args.fhir_dir}")
    print(f"  output    : {out_dir}\n")

    rows: list[R1.R1Row] = []
    for case in cases:
        env = Environment(store, case, as_of=args.as_of)
        row = R1.run_row(env, case.id, case.tag, backend=args.backend,
                         disclosure=args.disclosure)
        rows.append(row)
        flags = []
        if row.unusable:
            flags.append(f"UNUSABLE:{row.unusable}")
        else:
            if row.phantom_any:
                flags.append("PHANTOM")
            if row.silent_any:
                flags.append("SILENT")
            if row.action_note_mismatch:
                flags.append("ACTION/NOTE-MISMATCH")
            if row.ambiguous_any:
                flags.append("ambiguous")
        print(f"  {case.id:<28} {row.action or '-':<22} {' '.join(flags)}")

    s = R1.summarize(rows)
    usable = s["usable_rate"] or 0.0
    valid = s["cases_scorable"] > 0 and usable >= MIN_USABLE_RATE

    with open(os.path.join(out_dir, "r1_rows.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(row_dict(r))

    lines = [
        "# R1: claim-execution divergence", "",
        f"- backend: `{args.backend}`",
        f"- cases: {s['cases_total']} ({args.cases_dir}), cohort `{args.fhir_dir}`",
        f"- as_of: {args.as_of}, disclosure: {args.disclosure}",
        f"- vmag {__version__}, run {ts}", "",
        "## Health", "",
        f"- usable rate: {fmt(s['usable_rate'])} "
        f"({s['cases_scorable']}/{s['cases_total']} scorable)",
        f"- unusable: parse={s['unusable_parse']} transport={s['unusable_transport']} "
        f"no-note={s['unusable_no_note']}",
        f"- plans declaring a write: {s['plans_with_write']}/{s['cases_scorable']}; "
        f"notes claiming a write: {s['notes_with_claim']}/{s['cases_scorable']}", "",
    ]
    if valid and not s["write_arm_live"]:
        lines += [
            "## WARNING: the write arm never ran", "",
            "No scorable reply declared any side effect, so the silent-write rates have",
            "no population and are reported `n/a` rather than 0.000 -- they could not",
            "have fired. Read the phantom rate against `plans declaring a write` above:",
            "with that count at zero, a phantom is any note claiming a completed write,",
            "and this run cannot distinguish narrative/action divergence from a model",
            "that never uses the structured side-effect field at all. Diagnose the",
            "cause before quoting any number from this run.", "",
        ]
    if not valid:
        lines += [
            "## INVALID RUN", "",
            f"Usable rate {fmt(s['usable_rate'])} is below {MIN_USABLE_RATE}, so the "
            "divergence rates are SUPPRESSED. A backend that mostly fails to answer "
            "would otherwise render as a model with no divergence.", "",
        ]
        with open(os.path.join(out_dir, "INVALID_R1.txt"), "w", encoding="utf-8") as fh:
            fh.write(f"usable_rate={usable} < {MIN_USABLE_RATE}; rates suppressed\n")
    else:
        lines += [
            "## Divergence (over scorable rows only)", "",
            "| metric | rate |", "| --- | --- |",
            f"| phantom write (note claims, plan lacks) | {fmt(s['phantom_write_rate'])} |",
            f"| .. order | {fmt(s['phantom_order_rate'])} |",
            f"| .. message | {fmt(s['phantom_message_rate'])} |",
            f"| silent write (plan writes, note silent) | {fmt(s['silent_write_rate'])} |",
            f"| .. order | {fmt(s['silent_order_rate'])} |",
            f"| .. message | {fmt(s['silent_message_rate'])} |",
            f"| action/note mismatch (deferral + claimed write) | {fmt(s['action_note_mismatch_rate'])} |",
            f"| ambiguous note (classification withheld) | {fmt(s['ambiguous_rate'])} |", "",
            "Read the ambiguous rate first: it bounds how much of the rest to trust.",
            "", "## Scope of the claim", "",
            "This is narrative/action self-consistency inside one model reply, in a",
            "plan-then-execute harness. It is NOT MedAgentBench-style",
            "narrative-vs-server-state divergence and must not share a column with it.",
            "Every classification's matched sentence is in `r1_rows.csv` for audit.", "",
        ]

    with open(os.path.join(out_dir, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    with open(os.path.join(out_dir, "run_metadata.json"), "w", encoding="utf-8") as fh:
        json.dump({"vmag_version": __version__, "timestamp": ts, "backend": args.backend,
                   "cases_dir": args.cases_dir, "fhir_dir": args.fhir_dir,
                   "as_of": args.as_of, "disclosure": args.disclosure,
                   "valid": valid, "summary": s}, fh, indent=1)

    print("\n" + "\n".join(lines[lines.index("## Health"):]))
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())
