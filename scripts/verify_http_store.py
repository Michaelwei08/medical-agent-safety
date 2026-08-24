"""Prove HttpFhirStore is a drop-in for FhirStore on the same cohort.

The point is not that an HTTP client works. It is that `Environment` cannot tell
the two apart, because if it can, then any evaluation run against the real server
is measuring a different thing than the on-disk numbers and cannot be compared to
them.

For every patient in the cohort and every resource type the environment reads,
this compares the two stores' `search` output, and reports two verdicts:

  ORDERED    the sequences are identical, element for element
  UNORDERED  the same records are present, ignoring order

They differ only where a same-date tie resolves differently: the disk store
inherits Synthea's bundle order through a stable sort, while the server returns
its own order. Reporting them separately keeps that visible instead of hiding it
behind a single pass/fail. See D044 for why it changes no policy outcome here.

It then compares `latest_observation` for the codes the frozen policy actually
reads, at the as_of dates the cases actually use, because that is the call whose
answer becomes an action.

Usage:
    python scripts/verify_http_store.py
    python scripts/verify_http_store.py --fhir-dir data/synthea_s2/fhir
    python scripts/verify_http_store.py --base http://127.0.0.1:8080/fhir
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.getcwd())

from vmag.fhir_store import FhirStore                      # noqa: E402
from vmag.http_fhir_store import HttpFhirStore, DEFAULT_BASE  # noqa: E402

TYPES = ("Patient", "Condition", "MedicationRequest", "Observation")


def screen_probes(cases_dirs):
    """(code, within_days, as_of) triples the cases actually exercise."""
    out = set()
    for d in cases_dirs:
        for f in sorted(glob.glob(os.path.join(d, "*.json"))):
            c = json.load(open(f, encoding="utf-8"))
            pol = c.get("policy") or {}
            for key in ("screen", "require_recent"):
                sc = pol.get(key) or {}
                if sc.get("code"):
                    out.add((sc["code"], int(sc.get("within_days") or 730),
                             c.get("as_of") or "2026-07-11"))
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fhir-dir", default=os.path.join("data", "synthea", "fhir"))
    ap.add_argument("--base", default=DEFAULT_BASE)
    args = ap.parse_args()

    disk = FhirStore(args.fhir_dir)
    http = HttpFhirStore.from_dir(args.fhir_dir, base=args.base)
    pids = sorted(disk._patients)
    print("  cohort   : %s (%d patients)" % (args.fhir_dir, len(pids)))
    print("  server   : %s" % args.base)
    print()

    ordered = unordered = mismatch = 0
    absent = []
    notes = []
    for pid in pids:
        for rt in TYPES:
            d = disk.search(pid, rt)
            h = http.search(pid, rt)
            if not h and d:
                absent.append((pid, rt, len(d)))
                mismatch += 1
                continue
            if d == h:
                ordered += 1
                unordered += 1
            else:
                dk = sorted(json.dumps(x, sort_keys=True) for x in d)
                hk = sorted(json.dumps(x, sort_keys=True) for x in h)
                if dk == hk:
                    unordered += 1
                    if len(notes) < 6:
                        notes.append("ORDER ONLY  %s %s (n=%d)" % (pid[:8], rt, len(d)))
                else:
                    mismatch += 1
                    if len(notes) < 6:
                        only_d = [x for x in dk if x not in hk][:1]
                        only_h = [x for x in hk if x not in dk][:1]
                        notes.append("CONTENT     %s %s disk=%d http=%d\n"
                                     "                  only-disk: %s\n"
                                     "                  only-http: %s"
                                     % (pid[:8], rt, len(d), len(h),
                                        (only_d or ["-"])[0][:88],
                                        (only_h or ["-"])[0][:88]))

    total = len(pids) * len(TYPES)
    print("  search() over %d patient x resource-type pairs:" % total)
    print("    identical, in order      : %d" % ordered)
    print("    same records, any order  : %d" % unordered)
    print("    content mismatch         : %d" % mismatch)
    if absent:
        print("    not on the server        : %d  %s"
              % (len(absent), [(p[:8], r) for p, r, _ in absent[:4]]))
    for n in notes:
        print("      %s" % n)
    print()

    probes = screen_probes(["benchmark/cases", "benchmark/cases_heldout"])
    print("  latest_observation() over %d (code, window, as_of) probe(s) x %d patients:"
          % (len(probes), len(pids)))
    lo_same = lo_diff = 0
    lo_notes = []
    for code, win, as_of in probes:
        for pid in pids:
            for numeric_only in (False, True):
                a = disk.latest_observation(pid, code, win, as_of, numeric_only)
                b = http.latest_observation(pid, code, win, as_of, numeric_only)
                if a == b:
                    lo_same += 1
                else:
                    lo_diff += 1
                    if len(lo_notes) < 5:
                        lo_notes.append("%s %-18s win=%s numeric_only=%s\n"
                                        "                  disk=%s\n"
                                        "                  http=%s"
                                        % (pid[:8], code, win, numeric_only,
                                           json.dumps(a)[:84], json.dumps(b)[:84]))
    print("    agree    : %d" % lo_same)
    print("    disagree : %d" % lo_diff)
    for n in lo_notes:
        print("      %s" % n)
    print()

    drop_in = (mismatch == 0 and lo_diff == 0)
    print("  VERDICT: %s" % ("DROP-IN - Environment cannot tell them apart"
                             if drop_in else "NOT a drop-in yet, see above"))
    sys.exit(0 if drop_in else 1)


main()
