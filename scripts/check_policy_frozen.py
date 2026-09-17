"""Verify the policy has not changed since it was pre-registered.

`docs/evaluation_protocol.md` claims the decision procedure was fixed before the
held-out cases were written. That claim is only worth something if a change is
detectable, so this records a digest of the policy source and fails when it moves.

Changing the policy is fine. Changing it and still calling the held-out set
held-out is not -- re-freeze and mark the affected results superseded.

    python scripts/check_policy_frozen.py            # verify (exit 1 on drift)
    python scripts/check_policy_frozen.py --freeze   # record the current policy
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# The stripping rule and the digest live in the package, not here, so that
# run_eval.py stamping a run and this script verifying it cannot drift apart.
from vmag.policy_freeze import POLICY, FREEZE, decision_source, digest  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Check or set the policy freeze.")
    ap.add_argument("--freeze", action="store_true",
                    help="record the current policy as the frozen one")
    args = ap.parse_args()

    current = digest(POLICY)

    if args.freeze:
        if os.path.exists(FREEZE):
            existing = json.load(open(FREEZE, encoding="utf-8"))
            if existing.get("sha256") == current:
                print("already frozen at this digest; nothing to do.")
                return
            print("WARNING: re-freezing over an existing freeze.")
            print(f"  was: {existing.get('sha256')}  ({existing.get('frozen')})")
            print(f"  now: {current}")
            print("  Any held-out result produced under the previous digest is")
            print("  superseded and must be re-run or withdrawn.")
        with open(FREEZE, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({
                "file": "vmag/policy.py",
                "sha256": current,
                "frozen": "2026-08-08",
                "note": ("Digest of the decision procedure with comments and "
                         "docstrings stripped. See docs/evaluation_protocol.md."),
            }, fh, indent=1)
            fh.write("\n")
        print(f"froze vmag/policy.py at {current}")
        return

    if not os.path.exists(FREEZE):
        raise SystemExit("no docs/policy_freeze.json; run with --freeze first.")

    recorded = json.load(open(FREEZE, encoding="utf-8"))
    if recorded.get("sha256") == current:
        print(f"OK: policy unchanged since {recorded.get('frozen')}")
        print(f"    sha256 {current}")
        return

    print("POLICY DRIFT: vmag/policy.py has changed since it was frozen.")
    print(f"  frozen {recorded.get('frozen')}: {recorded.get('sha256')}")
    print(f"  current:              {current}")
    print()
    print("The held-out set was authored against the frozen policy. Any")
    print("generalization number computed after this change is not held-out.")
    print("Either revert the policy, or re-freeze and supersede the results.")
    sys.exit(1)


if __name__ == "__main__":
    main()
