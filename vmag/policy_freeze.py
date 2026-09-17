"""One definition of the policy digest, so every caller hashes the same thing.

WHY THIS IS ITS OWN MODULE
    `scripts/check_policy_frozen.py` defined the stripping rule and the digest.
    `run_eval.py` now needs the same digest, to stamp every run with the policy
    it actually used. Copying the rule into a second place would mean a future
    edit to one of them silently produces two different "policy hashes" for the
    same file -- and the whole point of the freeze is that a change is
    detectable. So the rule lives here and both import it.

WHAT THIS CLOSES
    Before this, `run_metadata.json` recorded the cohort, the case count and the
    as_of date, but NOT the policy. So an artifact could not self-certify which
    decision procedure produced it, and comparing two runs from different dates
    rested on the CONTINUITY log rather than on the artifacts. That gap is why
    the cli:sonnet run of 2026-08-08 cannot be hash-verified after the fact: the
    repository's git history begins 2026-08-24, so there is no independent record
    of policy.py between those dates. Runs from here on can be verified.
"""
from __future__ import annotations

import hashlib
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY = os.path.join(ROOT, "vmag", "policy.py")
FREEZE = os.path.join(ROOT, "docs", "policy_freeze.json")


def decision_source(path: str = POLICY) -> str:
    """The decision procedure with comments and docstrings stripped.

    Hashing the raw file would flag a typo fix in a comment as a policy change,
    which trains you to re-freeze reflexively -- and a freeze you re-run without
    reading is not a freeze. Only executable lines count.
    """
    src = open(path, encoding="utf-8").read()
    src = re.sub(r'""".*?"""', "", src, flags=re.S)
    lines = []
    for line in src.splitlines():
        stripped = line.split("#")[0].rstrip()
        if stripped.strip():
            lines.append(" ".join(stripped.split()))
    return "\n".join(lines)


def digest(path: str = POLICY) -> str:
    return hashlib.sha256(decision_source(path).encode("utf-8")).hexdigest()


def recorded() -> dict:
    """The frozen record, or {} if the policy has never been frozen."""
    if not os.path.exists(FREEZE):
        return {}
    try:
        return json.load(open(FREEZE, encoding="utf-8"))
    except Exception:                                             # noqa: BLE001
        return {}


def status() -> dict:
    """What a run should record about the policy it ran under.

    `matches_freeze` is False rather than absent when there is no freeze on
    disk, because "no freeze recorded" and "freeze does not match" both mean the
    run's policy provenance is unverified, and neither should read as a pass.
    """
    cur = digest()
    rec = recorded()
    return {
        "policy_sha256": cur,
        "policy_frozen_sha256": rec.get("sha256"),
        "policy_frozen_date": rec.get("frozen"),
        "policy_matches_freeze": bool(rec.get("sha256")) and rec.get("sha256") == cur,
    }
