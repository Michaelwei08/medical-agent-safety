"""Benchmark case schema and loader."""
from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass, field

TAGS = ("clean", "missing-data", "escalation", "permission", "injection", "high-risk",
        # v2 adversarial axes. Kept as distinct tags rather than folded into
        # "injection" because they are scored by different metrics: the first two
        # target the DECISION (measured by a counterfactual flip), the third
        # targets patient-level scope (measured by whose records were touched).
        "injection-decision", "injection-authority", "cross-patient",
        # Held-out conformance traps (seed-2 cohort). "boundary" probes a stated
        # threshold/window clause at its exact edge; "unseen-intent" probes the
        # fail-safe default. See docs/evaluation_protocol.md.
        "boundary", "unseen-intent")

# What an injected instruction is trying to achieve. The existing cases all try to
# get data out; the v2 ones try to change the answer, which is a different failure
# and needs a different measurement.
INJECT_TARGETS = ("exfiltration", "decision", "authority")


@dataclass
class Case:
    id: str
    tag: str
    patient_id: str
    task: str
    intent: str                              # drives the policy engine (see policy.py)
    correct_action: str                      # hidden ground-truth resolution
    split: str = "dev"                       # "dev" (policy authored against) or "test" (held-out)
    available_tools: list[str] = field(default_factory=list)
    allowed_resource_types: list[str] = field(default_factory=list)  # least-privilege
    policy: dict = field(default_factory=dict)      # data-driven preconditions/thresholds
    required_gather: list[str] = field(default_factory=list)
    injected_instruction: str | None = None
    inject_into: str | None = None           # resource type whose free-text carries the injection
    injected_recipient: str | None = None    # where the injection tries to exfiltrate
    inject_target: str = "exfiltration"      # what the injection is trying to achieve
    # A second patient whose record exists and is reachable but is NOT this task's
    # subject. Touching it is a patient-scope violation even when the resource type
    # is one the task legitimately needs.
    other_patient_id: str | None = None
    rationale: str = ""

    @staticmethod
    def from_dict(d: dict) -> "Case":
        known = {f for f in Case.__dataclass_fields__}  # type: ignore[attr-defined]
        return Case(**{k: v for k, v in d.items() if k in known})


def load_cases(cases_dir: str = os.path.join("benchmark", "cases")) -> list[Case]:
    cases = []
    for path in sorted(glob.glob(os.path.join(cases_dir, "*.json"))):
        cases.append(Case.from_dict(json.load(open(path, encoding="utf-8"))))
    _validate(cases)
    return cases


def _validate(cases: list[Case]) -> None:
    seen = set()
    for c in cases:
        assert c.tag in TAGS, f"{c.id}: bad tag {c.tag}"
        assert c.correct_action in ("act", "gather-missing-info", "abstain",
                                    "escalate-to-clinician"), f"{c.id}: bad action"
        assert c.id not in seen, f"duplicate case id {c.id}"
        assert c.inject_target in INJECT_TARGETS, \
            f"{c.id}: bad inject_target {c.inject_target}"
        if c.injected_instruction:
            assert c.inject_into, f"{c.id}: injected_instruction needs inject_into"
        if c.inject_target == "exfiltration" and c.injected_instruction:
            assert c.injected_recipient, \
                f"{c.id}: an exfiltration injection needs injected_recipient"
        if c.inject_target in ("decision", "authority"):
            # The whole measurement is "did the payload change the answer". If the
            # answer were "act" anyway there would be nothing to flip.
            assert c.correct_action != "act", (
                f"{c.id}: a decision/authority injection must sit on a case whose "
                "correct action is a deferral, or the flip is unmeasurable"
            )
        if c.tag == "cross-patient":
            assert c.other_patient_id, f"{c.id}: cross-patient case needs other_patient_id"
            assert c.other_patient_id != c.patient_id, f"{c.id}: other_patient_id is the subject"
        seen.add(c.id)
