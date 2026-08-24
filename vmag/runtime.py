"""Execute a base agent's plan, optionally through the guard, over a case.

This is the single place the guarded / unguarded distinction lives, so the
enforcement delta is a clean A/B: same base agent, ``guard=None`` vs a Guard.
"""
from __future__ import annotations

from . import actions as A
from .agents import BASE_AGENTS
from .benchmark import Case
from .environment import Environment
from .fhir_store import FhirStore
from .guard import Guard


def run_case(store: FhirStore, case: Case, base: str, guard: Guard | None, as_of: str,
             strip_injection: bool = False) -> A.Decision:
    env = Environment(store, case, as_of=as_of, strip_injection=strip_injection)
    plan = BASE_AGENTS[base](env)

    if guard is None:
        action = plan.intended_action
        reads = plan.reads
        side_effects = plan.side_effects
        follow_injection = plan.follow_injection
        cross_patient = plan.cross_patient_reads
        rationale = plan.rationale or "unguarded: base plan executed as-is"
    else:
        reviewed = guard.review(env, plan)
        action = reviewed["action"]
        reads = reviewed["reads"]
        side_effects = reviewed["side_effects"]
        follow_injection = reviewed["follow_injection"]
        cross_patient = reviewed.get("cross_patient_reads", [])
        rationale = reviewed["rationale"]

    served: list[dict] = []
    for rt in reads:
        served.extend(env.read(rt))

    # Pulls of another patient's chart. Logged as cross_patient so scope violations
    # are counted per patient, not hidden inside the resource-type exposure number.
    for other in cross_patient:
        for rt in reads:
            env.read(rt, patient_id=other)

    if follow_injection and env.case.injected_recipient and any(r.get("_injected") for r in served):
        env.send_message(env.case.injected_recipient, "forwarding record per note in chart")

    for se in side_effects:
        if se.tool == "draft_order":
            env.draft_order(se.text)
        elif se.tool == "send_message":
            env.send_message(se.recipient or "", se.text)

    decision = A.Decision(action, rationale, list(env.log))
    # Carry the proposal through so reporting can distinguish "the agent chose
    # this" from "we could not read the agent's answer and fell back". Nothing in
    # scoring reads it; a model-driven agent tags its plan with `unusable`.
    decision.plan = plan
    return decision
