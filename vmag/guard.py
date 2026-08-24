"""The runtime guard -- enforcement outside the model.

The guard reviews a base agent's :class:`Plan` and returns the enforced plan:
- the action is set by the data-driven policy (not the model's proposal),
- reads are clipped to least-privilege scope,
- state-changing side effects are reissued only when policy permits them,
- instructions embedded in record text are never followed.

Because the decision comes from policy + data, wrapping *any* base agent with
the guard yields the same safe behavior -- that is the point of measuring the
guarded-vs-unguarded delta.
"""
from __future__ import annotations

from . import actions as A
from .environment import Environment
from .policy import evaluate_policy


class Guard:
    def review(self, env: Environment, plan: A.Plan):
        action, why = evaluate_policy(env)
        allowed = env.case.allowed_resource_types
        # Provision exactly the least-privilege set the task needs (not the base
        # agent's over-broad plan). The agent still *reads* injected record text
        # when it is in scope -- it just never treats it as a command.
        reads = list(allowed) if allowed else list(plan.reads)

        side_effects: list[A.SideEffect] = []
        if action == A.ACT and env.case.intent == "med_refill":
            side_effects = [A.SideEffect("draft_order", "refill drafted after precondition check")]

        return {
            "action": action,
            "reads": reads,
            "side_effects": side_effects,
            "follow_injection": False,   # record text is data, never commands
            # Least privilege is per patient as well as per resource type. A task
            # about one patient never justifies pulling another's chart, however
            # plausible the pretext in the request, so the guard provisions none.
            "cross_patient_reads": [],
            "rationale": f"guard: {why}",
        }
