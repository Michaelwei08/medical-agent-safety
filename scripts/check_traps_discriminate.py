"""Prove the held-out traps can fail.

The frozen policy passes all seven held-out cases. On its own that number is
worthless: a set of cases that no plausible bug would break is decoration, and
"0/7 policy error" would be reporting the absence of a test rather than the
presence of correctness.

So this injects, one at a time, the specific implementation bug each trap was
written to catch, and requires that the trap flips. A trap that survives its own
mutation is not testing anything and is reported as such.

    python scripts/check_traps_discriminate.py

Exit 0 means every trap is discriminating.
"""
from __future__ import annotations

import datetime as _dt
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from vmag.benchmark import load_cases                # noqa: E402
from vmag.environment import Environment             # noqa: E402
from vmag.fhir_store import FhirStore, _days_between  # noqa: E402

CASES_DIR = os.path.join(ROOT, "benchmark", "cases_heldout")
FHIR_DIR = os.path.join(ROOT, "data", "synthea_s2", "fhir")
AS_OF = "2026-07-11"


def load_policy(mutation: tuple[str, str] | None = None):
    """Import vmag/policy.py, optionally with one string substitution applied."""
    src = open(os.path.join(ROOT, "vmag", "policy.py"), encoding="utf-8").read()
    if mutation:
        old, new = mutation
        if old not in src:
            raise SystemExit(f"mutation target not found in policy.py: {old!r}")
        src = src.replace(old, new, 1)
    module = types.ModuleType("policy_mutant")
    module.__dict__["__name__"] = "vmag.policy_mutant"
    exec(compile(src, "policy_mutant", "exec"), module.__dict__)
    return module


# --- store-level bugs, as buggy subclasses -----------------------------------
class AbsoluteAgeStore(FhirStore):
    """Compares |age| to the window, so a post-dated result counts as recent."""

    def latest_observation(self, pid, code_substr, within_days, as_of, numeric_only=False):
        for o in self.search(pid, "Observation", code_substr):
            age = _days_between(o.get("date"), as_of)
            if age is None or abs(age) > within_days:
                continue
            if numeric_only and o.get("value_num") is None:
                continue
            return o
        return None


class IgnoreRecencyStore(FhirStore):
    """Ignores the window entirely and returns the most recent match at any age."""

    def latest_observation(self, pid, code_substr, within_days, as_of, numeric_only=False):
        for o in self.search(pid, "Observation", code_substr):
            if numeric_only and o.get("value_num") is None:
                continue
            return o
        return None


class AnyValueStore(FhirStore):
    """Drops numeric_only, so a value-less panel row masks the real score."""

    def latest_observation(self, pid, code_substr, within_days, as_of, numeric_only=False):
        return super().latest_observation(pid, code_substr, within_days, as_of, False)


class ExclusiveWindowStore(FhirStore):
    """Treats the window as exclusive at the upper end."""

    def latest_observation(self, pid, code_substr, within_days, as_of, numeric_only=False):
        for o in self.search(pid, "Observation", code_substr):
            age = _days_between(o.get("date"), as_of)
            if age is None or not (0 <= age < within_days):
                continue
            if numeric_only and o.get("value_num") is None:
                continue
            return o
        return None


# (label, expected trap to flip, policy mutation, store class)
MUTANTS = [
    ("threshold uses > instead of >=", "heldout_screen_equal",
     ("val >= sc.get(\"threshold\", 1e9)", "val > sc.get(\"threshold\", 1e9)"), FhirStore),
    ("recency window is exclusive at the top", "heldout_recency_inclusive",
     None, ExclusiveWindowStore),
    ("age compared by absolute value", "heldout_future_dated",
     None, AbsoluteAgeStore),
    ("screens ignore recency", "heldout_stale_screen",
     None, IgnoreRecencyStore),
    ("unknown intent falls through to act", "heldout_unseen_intent",
     ("return A.ABSTAIN, f\"unknown intent '{intent}'; abstain by default (fail safe).\"",
      "return A.ACT, f\"unknown intent '{intent}'; proceeding.\""), FhirStore),
]


# Clauses of the frozen spec that NO held-out trap currently covers, with the
# reason. Listed rather than quietly omitted: an uncovered clause is a hole in the
# evidence, and a coverage report that only shows what passed is the same mistake
# as a metrics table that only shows what succeeded.
UNCOVERED = [
    ("protocol item 3: screens must skip value-less rows",
     "AnyValueStore",
     "In the seed-2 cohort the numeric 'Fall risk total' row always sorts ahead of "
     "the value-less 'Fall risk level' row at the same date, so dropping "
     "numeric_only changes no outcome. Covering this needs a record where the "
     "value-less row comes first -- the situation that actually bit the PHQ-9 check "
     "in v0, but which seed 2 does not contain."),
]


def evaluate_all(policy_mod, store, cases) -> dict[str, str]:
    return {
        c.id: policy_mod.evaluate_policy(Environment(store, c, as_of=AS_OF))[0]
        for c in cases
    }


def main() -> None:
    cases = load_cases(CASES_DIR)
    baseline_store = FhirStore(FHIR_DIR)
    baseline = evaluate_all(load_policy(), baseline_store, cases)
    expected = {c.id: c.correct_action for c in cases}

    unclean = [cid for cid in expected if baseline[cid] != expected[cid]]
    if unclean:
        raise SystemExit(f"baseline policy already fails {unclean}; fix that first.")
    print(f"baseline: frozen policy passes all {len(cases)} held-out traps\n")

    failures = []
    for label, trap, mutation, store_cls in MUTANTS:
        mutated = evaluate_all(load_policy(mutation), store_cls(FHIR_DIR), cases)
        caught = [cid for cid in expected if mutated[cid] != expected[cid]]
        hit = trap in caught
        status = "CAUGHT " if hit else "MISSED "
        print(f"  [{status}] {label}")
        print(f"            expected {trap} to flip; "
              f"traps that flipped: {caught or 'none'}")
        if not hit:
            failures.append((label, trap))

    if UNCOVERED:
        print()
        print(f"  {len(UNCOVERED)} spec clause(s) have NO trap:")
        for clause, mutant, why in UNCOVERED:
            print(f"    - {clause}")
            print(f"      {why}")

    print()
    if failures:
        print(f"{len(failures)} mutation(s) went undetected:")
        for label, trap in failures:
            print(f"  - {label}: {trap} did not flip, so it is not testing this bug")
        raise SystemExit(1)
    print(f"All {len(MUTANTS)} injected bugs were caught: every trap discriminates.")
    print(f"{len(UNCOVERED)} spec clause(s) remain untested -- see above.")


if __name__ == "__main__":
    main()
