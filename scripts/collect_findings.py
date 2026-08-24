"""Collect every number the writeup and figures quote, from the citable runs.

One source, so a figure and a sentence can never disagree. Each value carries the
run directory it came from; anything not present in a run is absent here rather
than filled in, so a missing number fails loudly instead of being rounded into a
claim.

    python scripts/collect_findings.py        # writes docs/findings_data.json
"""
from __future__ import annotations

import csv
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "findings_data.json")

def discover_runs() -> dict[str, str]:
    """Newest VALID run per model backend.

    Auto-discovered rather than pinned, so adding a model is a run rather than a
    code edit. Runs whose `valid` flag is false are skipped entirely: their tables
    are suppressed for a reason, and a collector that picked them up would put a
    failed run into the writeup by the back door.
    """
    found: dict[str, tuple[str, str]] = {}
    for run in sorted(glob.glob(os.path.join(ROOT, "outputs", "eval_*"))):
        health = os.path.join(run, "model_health.csv")
        if not os.path.exists(health):
            continue
        with open(health, encoding="utf-8") as fh:
            row = next(csv.DictReader(fh), None)
        if not row or row.get("valid") != "True":
            continue
        rel = os.path.relpath(run, ROOT).replace("\\", "/")
        stamp = os.path.basename(run)
        backend = row["backend"]
        if backend not in found or stamp > found[backend][0]:
            found[backend] = (stamp, rel)
    return {backend: rel for backend, (_, rel) in found.items()}


def rows(run: str, name: str) -> list[dict]:
    path = os.path.join(ROOT, run, name)
    if not os.path.exists(path):
        raise SystemExit(f"missing {path}: rerun the eval before collecting")
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def num(value):
    if value in ("", None):
        return None
    try:
        return float(value)
    except ValueError:
        return value


def main() -> None:
    runs = discover_runs()
    if not runs:
        raise SystemExit("no valid model runs found under outputs/")
    any_run = sorted(runs.values())[-1]
    data: dict = {"runs": runs, "agents": {}}

    # Deterministic stand-ins: identical across runs, take them from any one.
    for r in rows(any_run, "metrics.csv"):
        if r["guard"] not in ("off", "on"):
            continue
        data["agents"].setdefault(r["base"], {"kind": "stand-in"})[r["guard"]] = {
            k: num(r[k]) for k in (
                "n_cases", "action_accuracy", "unsafe_action_rate",
                "calibrated_deferral", "over_refusal_rate",
                "mean_out_of_scope_reads", "injection_follow_rate",
                "patient_scope_violation_rate")
        }

    for label, run in sorted(runs.items()):
        for r in rows(run, "model_metrics.csv"):
            data["agents"].setdefault(label, {"kind": "real model"})[r["guard"]] = {
                k: num(r[k]) for k in (
                    "n_cases", "action_accuracy", "unsafe_action_rate",
                    "calibrated_deferral", "over_refusal_rate",
                    "mean_out_of_scope_reads", "injection_follow_rate",
                    "patient_scope_violation_rate")
            }
        health = rows(run, "model_health.csv")[0]
        data["agents"][label]["health"] = {k: num(v) for k, v in health.items()
                                           if k not in ("backend",)}

    # Counterfactual injection flips, guard off only (guard on is trivially 0).
    data["flips"] = {}
    for run in sorted(set(runs.values())):
        for r in rows(run, "injection_flips.csv"):
            if r["guard"] != "off":
                continue
            data["flips"][r["base"]] = {
                "n": num(r["n"]),
                "flip_rate": num(r["injection_decision_flip_rate"]),
                "flip_to_unsafe": num(r["injection_flip_to_unsafe_rate"]),
                "wrong_without_payload": num(r["wrong_without_injection_rate"]),
            }

    # Per-case outcomes, guard off, for the two real models.
    data["per_case"] = {}
    for label, run in sorted(runs.items()):
        data["per_case"][label] = [
            {"case_id": r["case_id"], "tag": r["tag"], "split": r["split"],
             "correct_action": r["correct_action"], "chosen_action": r["chosen_action"],
             "correct": r["correct"] == "1", "unsafe": r["unsafe"] == "1",
             "unusable": r.get("unusable") or ""}
            for r in rows(run, "model_per_case.csv") if r["guard"] == "off"
        ]

    # Held-out conformance traps (frozen policy, seed-2 cohort, no agent).
    ho = rows(any_run, "heldout_per_case.csv")
    data["heldout"] = {
        "n": len(ho),
        "errors": sum(1 for r in ho if r["error"] == "1"),
        "cases": [{"case_id": r["case_id"], "tag": r["tag"],
                   "policy_action": r["policy_action"],
                   "correct_action": r["correct_action"],
                   "error": r["error"] == "1"} for r in ho],
    }

    pol = {r["scope"]: {k: num(r[k]) for k in r if k != "scope"}
           for r in rows(any_run, "policy_error.csv")}
    data["policy_error"] = pol

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=1, sort_keys=False)
        fh.write("\n")

    print(f"wrote {OUT}")
    print(f"  model runs discovered: {len(runs)}")
    for backend, run in sorted(runs.items()):
        print(f"    {backend:26} {run}")
    print(f"  held-out: {data['heldout']['errors']}/{data['heldout']['n']} policy error")
    for label in sorted(runs):
        off = data["agents"][label]["off"]
        print(f"  {label:18} guard off: unsafe={off['unsafe_action_rate']} "
              f"over_refusal={off['over_refusal_rate']} acc={off['action_accuracy']}")


if __name__ == "__main__":
    main()
