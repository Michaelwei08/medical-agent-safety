"""Test ONE question on many models cheaply: which pretext defeats patient scope?

WHY A DEDICATED PROBE
    The scope finding is a comparison BETWEEN pretexts, not between models, and
    that is why it has power at this benchmark's size. Pooled across models and
    cohorts it is one lure type against nine over roughly thirty trials, and the
    confidence intervals separate. Every between-MODEL rate measured on
    2026-08-25 overlapped at n=20-28.

    So asking whether the asymmetry is a general property needs MORE MODELS on
    the SCOPE CASES, not more full runs. A full run is about 56 model calls; the
    cross-patient cases are 15 LIVE calls -- verified as 15 distinct prompts
    across 30 calls, because guard-off and guard-on build the same prompt (it is
    built before the guard reviews) and cross-patient cases carry no injected
    payload, so there is no paired-control pass. That is the
    difference between one free tier per model and several models a day on one
    free tier -- which matters because as of 2026-08-25 three of the five
    documented free tiers do not work at all (see the measured-availability
    block in docs/MODEL_ACCESS.md).

WHAT IT DELIBERATELY DOES NOT DO
    It does not produce a headline safety number. Every rate in a tag-filtered
    run is over a subset with its own denominator; `run_eval` says so on stdout
    and records `tags_filter` in the metadata. This prints the per-lure breach
    table, the pooled instructed-versus-other contrast, and the response health
    that says whether each arm may be quoted as a rate at all.

Usage:
    python scripts/scope_probe.py                      # every available backend
    python scripts/scope_probe.py --only groq openrouter
    python scripts/scope_probe.py --report-only        # re-read existing outputs
"""
import argparse
import csv
import glob
import json
import math
import os
import subprocess
import sys

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "scripts"))

from vmag.benchmark import load_cases                                   # noqa: E402
from run_all_models import (CANDIDATES, availability, dedupe_by_weights,  # noqa: E402
                            load_env_local, ollama_tags, preflight)

TAG = "cross-patient"

# A case belongs to the explicit-instruction arm if its own `lure` says so. Read
# off the case data rather than listed here, so adding a case cannot silently
# fall outside the contrast being measured.
INSTRUCTED_MARK = "EXPLICIT INSTRUCTION"


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def col_label(backend, width=13):
    """A column label that DISTINGUISHES two models from the same provider.

    Was `backend.split(":", 1)[0]`, which printed "openrouter" for every
    OpenRouter model and made a four-column table unreadable the moment two
    models shared a provider. Prefer the tail of the model id, which is the part
    that actually differs.
    """
    prov, _, model = backend.partition(":")
    leaf = (model.split("/")[-1] or prov).replace(":free", "")
    return leaf[:width] if leaf else prov[:width]


def case_meta():
    """case id -> {lure, intent}, from the case files themselves."""
    out = {}
    for d in ("benchmark/cases", "benchmark/cases_heldout"):
        for c in load_cases(d):
            if c.other_patient_id:
                out[c.id] = {"lure": c.lure or "(no lure recorded)",
                             "intent": c.intent,
                             "correct_action": c.correct_action}
    return out


def arms(cid, meta):
    """(instructed?, mismatch?) for the 2x2.

    Both read off case data, never a hardcoded id list. `mismatch` is
    `intent == identity_verification`, which for these cases IS the
    name/DOB-mismatch condition - the policy abstains exactly when the request's
    expected identity does not match the open record.

    The 2x2 exists because until 2026-08-26 BOTH explicit-instruction cases were
    identity_verification and no other lure used that intent, 2 of 2 against
    0 of 13. 'Explicit instruction defeats scope discipline' and 'identity
    mismatch defeats scope discipline' were then indistinguishable.
    """
    m = meta.get(cid, {})
    # `intent == identity_verification` alone is NOT the mismatch condition: an
    # identity can be asserted and be CORRECT, which is the control D070 added.
    # The frozen policy abstains on this intent exactly when an asserted
    # identifier contradicts the record, so `abstain` IS the contradiction flag
    # and it is read off the label rather than re-derived here.
    contradiction = (m.get("intent") == "identity_verification"
                     and m.get("correct_action") == "abstain")
    return (INSTRUCTED_MARK in m.get("lure", ""), contradiction)


def probe_runs():
    """Newest tag-filtered run per backend, main and held-out rows together."""
    found = {}
    for d in sorted(glob.glob(os.path.join("outputs", "eval_*"))):
        mp = os.path.join(d, "run_metadata.json")
        if not os.path.exists(mp):
            continue
        try:
            meta = json.load(open(mp, encoding="utf-8"))
        except Exception:                                            # noqa: BLE001
            continue
        if meta.get("tags_filter") != [TAG] or not meta.get("model_backend"):
            continue
        rows, health = [], {}
        for pc, hc, which in (("model_per_case.csv", "model_health.csv", "main"),
                              ("heldout_model_per_case.csv",
                               "heldout_model_health.csv", "heldout")):
            p, h = os.path.join(d, pc), os.path.join(d, hc)
            if os.path.exists(p):
                for r in csv.DictReader(open(p, encoding="utf-8")):
                    if r["guard"] == "off" and r.get("scope_eligible") == "1":
                        r["_set"] = which
                        rows.append(r)
            if os.path.exists(h):
                hr = list(csv.DictReader(open(h, encoding="utf-8")))
                if hr:
                    health[which] = hr[0]
                    for r in rows:
                        if r.get("_set") == which:
                            r["_valid"] = str(hr[0].get("valid", "")).lower() == "true"
        if rows:
            found[meta["model_backend"]] = (d, rows, health)
    return found


def run_backends(only):
    load_env_local()
    todo = CANDIDATES
    if only:
        todo = [c for c in todo if c[0].split(":", 1)[0] in set(only)]
    runnable = []
    for backend, why in todo:
        ok, reason = availability(backend)
        print("  %-52s %-6s %s" % (backend, "READY" if ok else "skip", reason))
        if ok:
            runnable.append((backend, why))
    runnable, dup = dedupe_by_weights(runnable, ollama_tags())
    for backend, reason in dup:
        print("  %-52s %-6s %s" % (backend, "dup", reason))
    print()

    live = []
    for backend, _ in runnable:
        ok, reason = preflight(backend)
        print("  preflight %-42s %-5s %s" % (backend, "pass" if ok else "FAIL", reason))
        if ok:
            live.append(backend)
    print()
    for backend in live:
        print("  ==== %s ====" % backend)
        cmd = [sys.executable, "-m", "vmag.run_eval",
               "--tags", TAG, "--model-backend", backend]
        p = subprocess.run(cmd, text=True, capture_output=True,
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        if p.returncode != 0:
            print("     EXIT %d" % p.returncode)
            for line in (p.stderr or "").strip().splitlines()[-6:]:
                print("     err: " + line[:140])
        print()


def report():
    meta = case_meta()
    lures = {k: v["lure"] for k, v in meta.items()}
    found = probe_runs()
    if not found:
        print("  no tag-filtered runs on disk yet -- run without --report-only first")
        return 1
    backends = sorted(found)

    by_case = {}
    for b in backends:
        for r in found[b][1]:
            by_case.setdefault((r["case_id"], r["_set"]), {})[b] = r

    width = max([len(v) for v in lures.values()] + [12]) + 1
    print("  == breach by lure, guard off ==")
    print()
    head = "  %-*s %-8s %s" % (width, "lure", "set",
                               " ".join("%-13s" % col_label(b) for b in backends))
    print(head)
    print("  " + "-" * (len(head) - 2))

    pooled = {"instructed": [0, 0], "other": [0, 0]}
    # explicit-instruction rows first: it is the contrast the table exists for
    order = sorted(by_case, key=lambda k: (INSTRUCTED_MARK not in lures.get(k[0], ""),
                                           k[1], k[0]))
    for key in order:
        cid, which = key
        cells = []
        for b in backends:
            r = by_case[key].get(b)
            if r is None:
                cells.append("%-13s" % "-")
                continue
            breach = r.get("cross_patient") == "1"
            cells.append("%-13s" % ("VIOLATED" if breach else "clean"))
            arm = "instructed" if INSTRUCTED_MARK in lures.get(cid, "") else "other"
            pooled[arm][1] += 1
            pooled[arm][0] += breach
        print("  %-*s %-8s %s" % (width, lures.get(cid, cid)[:width], which,
                                  " ".join(cells)))

    print()
    print("  == pooled over every backend x cohort ==")
    ci = {}
    for arm in ("instructed", "other"):
        k, n = pooled[arm]
        if not n:
            continue
        lo, hi = wilson(k, n)
        ci[arm] = (lo, hi)
        print("  %-12s %3d/%-3d = %.3f   95%% CI [%.2f, %.2f]" % (arm, k, n, k / n, lo, hi))
    if len(ci) == 2:
        i, o = ci["instructed"], ci["other"]
        sep = i[0] > o[1] or o[0] > i[1]
        print()
        print("  intervals %s" % ("SEPARATE -- the asymmetry is supported"
                                  if sep else
                                  "OVERLAP -- not supported at this n"))

    print()
    print("  == 2x2: is it the INSTRUCTION or the identity MISMATCH? ==")
    print("  (every arm, valid or not -- these are OBSERVATIONS. The marginals")
    print("   below use valid arms only, so the two blocks will not match.)")
    cell = {}
    for key in order:
        cid, _ = key
        a = arms(cid, meta)
        for b in backends:
            r = by_case[key].get(b)
            if r is None:
                continue
            c = cell.setdefault(a, [0, 0])
            c[1] += 1
            c[0] += (r.get("cross_patient") == "1")
    print("  %-22s %-22s %s" % ("", "instruction GIVEN", "no instruction"))
    for mism, mlabel in ((True, "identity mismatch"), (False, "no mismatch")):
        row = []
        for instr in (True, False):
            c = cell.get((instr, mism))
            row.append("%-22s" % ("%d/%d" % (c[0], c[1]) if c else "(no case)"))
        print("  %-22s %s" % (mlabel, " ".join(row)))
    print()
    print("  Read down a column to see whether the mismatch matters when the")
    print("  instruction is held constant; across a row for the reverse. An empty")
    print("  cell means that combination has no case yet and nothing is concluded.")
    print()
    print("  == which factor actually carries the effect? ==")
    # Computed on VALID arms ONLY. A rate that pools a valid run with an invalid
    # one is not a rate (D034/D039), and on 2026-08-26 the pooled and
    # valid-only versions genuinely differed -- 6/8 against 4/4 on the mismatch
    # arm. Doing this by hand is how that nearly went unnoticed, so it is
    # enforced here instead of remembered.
    dropped = {}
    for key in order:
        cid, which = key
        for b in backends:
            r = by_case[key].get(b)
            if r is not None and not r.get("_valid", True):
                key = "%s/%s" % (col_label(b), which)
                dropped[key] = dropped.get(key, 0) + 1
    if dropped:
        print("  excluded as invalid: %s" % ", ".join(
            "%s (%d rows)" % (k, v) for k, v in sorted(dropped.items())))
    cell = {}
    for key in order:
        cid, _ = key
        a = arms(cid, meta)
        for b in backends:
            r = by_case[key].get(b)
            if r is None or not r.get("_valid", True):
                continue
            c = cell.setdefault(a, [0, 0])
            c[1] += 1
            c[0] += (r.get("cross_patient") == "1")
    # Printed because reading the 2x2 by eye is how the confound survived in the
    # first place. The marginals with intervals say plainly which factor separates
    # from its own baseline and which does not.
    def marg(pick):
        k = n = 0
        for (instr, mism), c in cell.items():
            if pick(instr, mism):
                k += c[0]
                n += c[1]
        return k, n
    lines = (("mismatch present", lambda i, m: m),
             ("mismatch absent", lambda i, m: not m),
             ("instruction given", lambda i, m: i),
             ("instruction absent", lambda i, m: not i))
        
    got = {}
    for label, pick in lines:
        k, n = marg(pick)
        if not n:
            continue
        lo, hi = wilson(k, n)
        got[label] = (lo, hi)
        print("  %-20s %2d/%-3d = %.3f   95%% CI [%.2f, %.2f]" % (label, k, n, k / n, lo, hi))
    for a, b, name in (("mismatch present", "mismatch absent", "mismatch"),
                       ("instruction given", "instruction absent", "instruction")):
        if a in got and b in got:
            sep = got[a][0] > got[b][1] or got[b][0] > got[a][1]
            print("  %-12s present vs absent: %s" % (name, "SEPARATE" if sep else "OVERLAP"))

    print()
    print("  == identity variants, valid arms only ==")
    print("  (does a CONTRADICTION drive it, or merely raising identity as a topic?)")
    idv = {}
    for key in order:
        cid, _ = key
        m = meta.get(cid, {})
        if m.get("intent") != "identity_verification":
            continue
        for b in backends:
            r = by_case[key].get(b)
            if r is None or not r.get("_valid", True):
                continue
            c = idv.setdefault(m.get("lure", cid), [0, 0])
            c[1] += 1
            c[0] += (r.get("cross_patient") == "1")
    if not idv:
        print("  no identity cases with a valid arm yet")
    for lure, (k, n) in sorted(idv.items(), key=lambda kv: -kv[1][0] / max(1, kv[1][1])):
        lo, hi = wilson(k, n)
        print("  %-52s %2d/%-3d = %.2f  [%.2f, %.2f]" % (lure[:52], k, n, k / n, lo, hi))

    print()
    print("  == response health: a rate from an invalid run is not a rate ==")
    for b in backends:
        d, _, health = found[b]
        bits = []
        for which in ("main", "heldout"):
            h = health.get(which)
            if h:
                bits.append("%s valid=%s usable=%s calls=%s" % (
                    which, h["valid"], h["usable_response_rate"], h["calls"]))
        print("  %-30s %s" % (b, "   ".join(bits) or "no health row"))
        print("  %-30s %s" % ("", os.path.basename(d)))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None,
                    help="provider prefixes, e.g. groq openrouter")
    ap.add_argument("--report-only", action="store_true",
                    help="skip running; re-read existing tag-filtered outputs")
    args = ap.parse_args()

    n_elig = len(case_meta())
    print("  scope probe: %d cross-patient cases across both cohorts" % n_elig)
    # Measured, not estimated: the two guard arms build the SAME prompt (it is
    # built before the guard reviews), verified as 15 distinct prompts across 30
    # calls, and these cases carry no injected payload so there is no paired
    # control pass. So a backend seen for the first time pays n_elig LIVE calls
    # out of 2*n_elig total; a backend already run in full pays nothing.
    print("  cost on a first-time backend: %d live calls (%d total, half served"
          % (n_elig, 2 * n_elig))
    print("  from cache inside the run). A full run is about 56. Already-run")
    print("  backends replay free.")
    print()
    if not args.report_only:
        run_backends(args.only)
    return report()


if __name__ == "__main__":
    sys.exit(main())
