from agentic_bi.evaluation.common import load_cases
from agentic_bi.skills.router import select_skill

CASES_FILE = "agent_cases.json"


def run_routing_evaluation() -> None:
    """
    Evaluate whether the router selects
    the expected skill for each case.
    """

    cases = load_cases(CASES_FILE)

    total = 0
    passed = 0

    print("\nROUTING EVALUATION")
    print("=" * 50)

    for case in cases:
        question = case["question"]
        expected_skill = case["expected_skill"]

        actual_skill = select_skill(question)

        is_correct = actual_skill == expected_skill

        total += 1

        if is_correct:
            passed += 1
            status = "PASS"
        else:
            status = "FAIL"

        print(f"\n[{status}] {case['id']}")

        print(f"Question: {question}")

        print(f"Expected: {expected_skill}")

        print(f"Actual:   {actual_skill}")

    accuracy = passed / total * 100 if total else 0.0

    print("\n" + "=" * 50)

    print(f"Passed: {passed}/{total}")

    print(f"Routing accuracy: {accuracy:.2f}%")


if __name__ == "__main__":
    run_routing_evaluation()
