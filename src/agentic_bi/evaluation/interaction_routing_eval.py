from agentic_bi.core.interaction import classify_interaction
from agentic_bi.evaluation.common import load_cases

CASES_FILE = "interaction_cases.json"


def run_interaction_routing_evaluation() -> None:
    """
    Evaluate whether the LLM interaction router selects the
    expected intent, including the web-search conditions.
    """

    cases = load_cases(CASES_FILE)

    total = 0
    passed = 0

    print("\nINTERACTION ROUTING EVALUATION")
    print("=" * 50)

    for case in cases:
        question = case["question"]
        expected_intent = case["expected_intent"]

        decision = classify_interaction(question)

        is_correct = decision.intent == expected_intent

        total += 1

        if is_correct:
            passed += 1
            status = "PASS"
        else:
            status = "FAIL"

        print(f"\n[{status}] {case['id']} ({case['condition']})")

        print(f"Question: {question}")

        print(f"Expected: {expected_intent}")

        print(f"Actual:   {decision.intent}")

        if not is_correct:
            print(f"Reason:   {decision.reason}")

    accuracy = passed / total * 100 if total else 0.0

    print("\n" + "=" * 50)

    print(f"Passed: {passed}/{total}")

    print(f"Interaction routing accuracy: {accuracy:.2f}%")


if __name__ == "__main__":
    run_interaction_routing_evaluation()
