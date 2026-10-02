from agentic_bi.core.agent import run_agent
from agentic_bi.evaluation.common import load_cases

CASES_FILE = "agent_cases.json"


def get_actual_tools(tool_history: list[dict]) -> list[str]:

    tools = []

    for item in tool_history:
        tool_name = item.get("tool")

        if tool_name is not None:
            tools.append(tool_name)

    return tools


def main() -> None:

    cases = load_cases(CASES_FILE)

    passed = 0
    evaluated = 0

    print("\n# TOOL SELECTION EVALUATION\n")

    for case in cases:
        expected_tool = case.get("expected_tool")

        # Skip cases that do not specify
        # an expected tool.
        if expected_tool is None:
            continue

        evaluated += 1

        print(f"Running: {case['id']} ...")

        result = run_agent(case["question"], verbose=False)

        actual_tools = get_actual_tools(result.tool_history)

        success = expected_tool in actual_tools

        if success:
            passed += 1

        status = "PASS" if success else "FAIL"

        print(f"[{status}] {case['id']}")

        print("Question:", case["question"])

        print("Expected tool:", expected_tool)

        print("Actual tools:", actual_tools)

        print("Selected skill:", result.selected_skill)

        print("Stop reason:", result.stop_reason)

        print()

    print("=" * 50)

    print(f"Passed: {passed}/{evaluated}")

    if evaluated > 0:
        accuracy = passed / evaluated * 100

        print(f"Tool selection accuracy: {accuracy:.2f}%")

    else:
        print("No tool-selection cases found.")


if __name__ == "__main__":
    main()
