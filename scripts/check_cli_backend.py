"""Verify the `claude` CLI backend with one real call, then one real case.

Run this from YOUR OWN terminal. It cannot be verified from inside a Claude Code
session: a nested `claude` process cannot refresh the OAuth token and fails with
"OAuth session expired and could not be refreshed", regardless of sandboxing.

    python scripts/check_cli_backend.py
    python scripts/check_cli_backend.py --model opus --case escalation_opioid_001

What it proves, in order:

1. `claude` is on PATH.
2. A completion comes back through the seam and is cached.
3. The CLI runs in a neutral directory, so this repo's CLAUDE.md -- which states
   the four-way action space and the safety thesis -- is NOT in the model's
   context. Without this the benchmark would be scoring an answer key.
4. A real case runs end to end: the model proposes, the guard decides.

Two caveats this cannot remove, both of which belong in any write-up:

- The CLI exposes no temperature control, so runs are not guaranteed reproducible
  from the model side. The response cache freezes whatever came back first.
- The reply is Claude as exposed by the Claude Code CLI with its system prompt
  replaced and tools denied -- close to a raw model call, not identical to one.
  Label results "via Claude Code CLI", never plain "Claude".
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vmag import actions as A                                    # noqa: E402
from vmag.agents import BASE_AGENTS                              # noqa: E402
from vmag.benchmark import load_cases                            # noqa: E402
from vmag.environment import Environment                         # noqa: E402
from vmag.fhir_store import FhirStore                            # noqa: E402
from vmag.guard import Guard                                     # noqa: E402
from vmag.llm import _neutral_cwd, complete                      # noqa: E402
from vmag.model_agents import build_prompt, make_model_agent      # noqa: E402
from vmag.runtime import run_case                                # noqa: E402
from vmag.scoring import score_case                              # noqa: E402

AS_OF = "2026-07-11"


def main() -> None:
    ap = argparse.ArgumentParser(description="Check the claude CLI backend.")
    ap.add_argument("--model", default="sonnet", help="CLI model alias (sonnet, opus, ...)")
    ap.add_argument("--case", default="missing_data_refill_001")
    args = ap.parse_args()
    backend = f"cli:{args.model}"

    print(f"backend: {backend}")
    print(f"cli cwd: {_neutral_cwd()}  (must contain no CLAUDE.md)\n")

    # -- 1 & 2: one real completion ---------------------------------------
    print("[1/3] one completion through the seam ...")
    probe = complete(
        'Reply with exactly this and nothing else: {"ok": true}',
        system="You output one JSON object and no other text.",
        backend=backend,
    )
    if not probe.ok:
        print(f"      FAILED: {probe.error}\n")
        if "OAuth" in (probe.error or ""):
            print("      This is the nested-process failure. Run this script from your")
            print("      own terminal, or re-authenticate with `claude` first.")
        raise SystemExit(1)
    print(f"      ok, {len(probe.text)} chars, cached={probe.cached}")
    print(f"      reply: {probe.text.strip()[:120]}\n")

    # -- 3: context isolation ---------------------------------------------
    print("[2/3] confirming the repo's CLAUDE.md is NOT visible to the CLI ...")
    leak = complete(
        "Do you have any project instructions, CLAUDE.md content, or repository "
        "context in your system prompt? Answer only YES or NO.",
        system="Answer with one word.",
        backend=backend,
    )
    verdict = leak.text.strip().upper()[:3] if leak.ok else "?"
    print(f"      model says: {verdict}   (NO is what we want)")
    print("      note: a model's self-report is weak evidence. The hard guarantee is")
    print("      the cwd above, which has no CLAUDE.md anywhere up the tree.\n")

    # -- 4: one real case end to end --------------------------------------
    print(f"[3/3] running case {args.case} ...")
    store = FhirStore()
    cases = {c.id: c for c in load_cases()}
    if args.case not in cases:
        raise SystemExit(f"unknown case; try one of: {', '.join(sorted(cases))}")
    case = cases[args.case]

    agent = make_model_agent(backend=backend)
    BASE_AGENTS["_cli"] = agent
    try:
        print(f"      task: {case.task}")
        print(f"      prompt is {len(build_prompt(Environment(store, case, as_of=AS_OF)))} chars")

        for label, guard in (("guard OFF", None), ("guard ON", Guard())):
            decision = run_case(store, case, "_cli", guard, AS_OF)
            scored = score_case(case, decision)
            unusable = getattr(decision.plan, "unusable", None) if hasattr(decision, "plan") else None
            print(f"      {label}: action={decision.action:24} "
                  f"unsafe={scored.unsafe}  correct={scored.correct}"
                  + (f"  UNUSABLE={unusable}" if unusable else ""))
        print(f"\n      safe resolution for this case: {case.correct_action}")
        print(f"      agent stats: {agent.stats}")
    finally:
        BASE_AGENTS.pop("_cli", None)

    if agent.stats["parse_errors"]:
        print("\n      WARNING: the model did not return usable JSON on every call.")
        print("      Check the parse-failure rate before reading any safety number --")
        print("      you may be measuring output formatting, not clinical judgment.")

    print("\nCLI backend works. Remember: label results 'via Claude Code CLI',")
    print("report the parse-failure rate, and never point this backend at MIMIC.")


if __name__ == "__main__":
    main()
