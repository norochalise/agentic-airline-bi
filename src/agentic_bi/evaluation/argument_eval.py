import json
from pathlib import Path

from agentic_bi.core.agent import run_agent


PROJECT_ROOT = Path(__file__).resolve().parents[3]

EVAL_FILE = (
    PROJECT_ROOT
    / "evals"
    / "agent_cases.json"
)


def load_cases() -> list[dict]:
    with open(
        EVAL_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def find_tool_call(
    tool_history: list[dict],
    expected_tool: str,
) -> dict | None:
    """
    Find the first execution record for the expected tool.
    """

    for item in tool_history:
        if item.get("tool") == expected_tool:
            return item

    return None


def main() -> None:

    cases = load_cases()

    passed = 0
    evaluated = 0

    print("\n# TOOL ARGUMENT EVALUATION\n")

    for case in cases:

        expected_tool = case.get(
            "expected_tool"
        )

        expected_arguments = case.get(
            "expected_arguments"
        )

        # Only evaluate cases where exact arguments
        # have been specified in the dataset.
        if (
            expected_tool is None
            or expected_arguments is None
        ):
            continue

        evaluated += 1

        print(
            f"Running: {case['id']} ..."
        )

        result = run_agent(
            case["question"],
            verbose=False,
        )

        tool_call = find_tool_call(
            result.tool_history,
            expected_tool,
        )

        if tool_call is None:

            actual_arguments = None
            success = False

        else:

            actual_arguments = (
                tool_call.get("arguments")
            )

            success = (
                actual_arguments
                == expected_arguments
            )

        if success:
            passed += 1

        status = (
            "PASS"
            if success
            else "FAIL"
        )

        print(
            f"[{status}] {case['id']}"
        )

        print(
            "Expected tool:",
            expected_tool,
        )

        print(
            "Expected arguments:",
            expected_arguments,
        )

        print(
            "Actual arguments:",
            actual_arguments,
        )

        print(
            "Stop reason:",
            result.stop_reason,
        )

        print()

    print(
        "=" * 50
    )

    print(
        f"Passed: {passed}/{evaluated}"
    )

    if evaluated > 0:

        accuracy = (
            passed
            / evaluated
            * 100
        )

        print(
            f"Argument accuracy: "
            f"{accuracy:.2f}%"
        )

    else:

        print(
            "No argument-evaluation cases found."
        )


if __name__ == "__main__":
    main()