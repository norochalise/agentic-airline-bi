"""Evaluate skill, tool and key arguments for the flight-analytics tools.

Calls the real model (paid). Only the arguments listed in a case are
checked, so cases state what the question pins down and nothing more.
"""

from typing import Any

from agentic_bi.core.agent import run_agent
from agentic_bi.evaluation.common import load_cases, print_banner

CASES_FILE = "analytics_cases.json"


def _same(expected: Any, actual: Any) -> bool:
    if isinstance(expected, list) and isinstance(actual, list):
        return sorted(expected) == sorted(actual)

    return expected == actual


def evaluate_case(case: dict[str, Any], tool_history: list[dict]) -> list[str]:
    """Return the problems found for one case (empty when it passes)."""

    calls = [
        entry for entry in tool_history if entry.get("tool") == case["expected_tool"]
    ]

    if not calls:
        used = [entry.get("tool") for entry in tool_history]
        return [f"expected {case['expected_tool']}, used {used}"]

    arguments = calls[0].get("arguments", {})

    return [
        f"{name}: expected {expected!r}, got {arguments.get(name)!r}"
        for name, expected in case["expected_arguments"].items()
        if not _same(expected, arguments.get(name))
    ]


def main() -> None:
    cases = load_cases(CASES_FILE)
    passed = 0

    print_banner("FLIGHT ANALYTICS TOOL EVALUATION")

    for case in cases:
        result = run_agent(case["question"], verbose=False)

        problems = evaluate_case(case, result.tool_history)

        if result.selected_skill != "data-analysis":
            problems.insert(0, f"skill: {result.selected_skill}")

        if result.errors:
            problems.append(f"errors: {[e['error_type'] for e in result.errors]}")

        status = "PASS" if not problems else "FAIL"
        passed += not problems

        print(f"\n[{status}] {case['id']}: {case['question']}")

        for problem in problems:
            print(f"  - {problem}")

    print()
    print(f"Passed: {passed}/{len(cases)}")


if __name__ == "__main__":
    main()
