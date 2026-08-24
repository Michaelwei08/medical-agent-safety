"""Action space and episode records for clinical agents."""
from __future__ import annotations

from dataclasses import dataclass, field

# The four resolutions of any agent step.
ACT = "act"
GATHER = "gather-missing-info"
ABSTAIN = "abstain"
ESCALATE = "escalate-to-clinician"

ACTIONS = (ACT, GATHER, ABSTAIN, ESCALATE)
DEFERRALS = (GATHER, ABSTAIN, ESCALATE)  # anything that is not autonomous action

# Side-effectful tools (attempting these is what makes a wrong action dangerous).
SIDE_EFFECT_TOOLS = ("draft_order", "send_message")


@dataclass
class ToolCall:
    tool: str                       # e.g. "read:Observation", "draft_order", "send_message"
    detail: str = ""                # free-text detail (recipient, order text, ...)
    out_of_scope: bool = False      # read of a resource type the task did not need
    exfiltration: bool = False      # side effect toward a recipient not named by the task
    # Read of a DIFFERENT PATIENT than the task concerns. Orthogonal to
    # out_of_scope, which is about resource type: reading the right resource type
    # for the wrong patient is in-scope by type and still a privacy breach, so the
    # two have to be counted separately.
    cross_patient: bool = False
    patient_id: str | None = None


@dataclass
class SideEffect:
    """A state-changing action a base agent proposes (subject to guard review)."""
    tool: str                       # "draft_order" | "send_message"
    text: str = ""
    recipient: str | None = None


@dataclass
class Plan:
    """A base agent's proposal, before any enforcement.

    Separating the proposal (Plan) from execution lets us run the *same* base
    agent with the guard on or off and measure the enforcement delta.
    """
    intended_action: str            # one of ACTIONS
    reads: list[str] = field(default_factory=list)          # resource types to read
    side_effects: list[SideEffect] = field(default_factory=list)
    follow_injection: bool = False  # would it act on instructions embedded in records?
    rationale: str = ""
    # Patient ids other than the task's subject that the agent wants to pull. An
    # agent with no way to express this cannot be observed violating patient scope,
    # so the capability has to exist for the measurement to mean anything.
    cross_patient_reads: list[str] = field(default_factory=list)


@dataclass
class Decision:
    action: str                     # one of ACTIONS
    rationale: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)

    def accessed_resource_types(self) -> set[str]:
        return {
            tc.tool.split(":", 1)[1]
            for tc in self.tool_calls
            if tc.tool.startswith("read:")
        }

    def out_of_scope_reads(self) -> set[str]:
        return {
            tc.tool.split(":", 1)[1]
            for tc in self.tool_calls
            if tc.tool.startswith("read:") and tc.out_of_scope
        }

    def did_exfiltrate(self) -> bool:
        return any(tc.exfiltration for tc in self.tool_calls)

    def cross_patient_reads(self) -> set[str]:
        """Patient ids touched that the task did not concern."""
        return {
            tc.patient_id for tc in self.tool_calls
            if tc.cross_patient and tc.patient_id
        }

    def did_cross_patient(self) -> bool:
        return any(tc.cross_patient for tc in self.tool_calls)

    def did_side_effect(self) -> bool:
        return any(tc.tool in SIDE_EFFECT_TOOLS for tc in self.tool_calls)
