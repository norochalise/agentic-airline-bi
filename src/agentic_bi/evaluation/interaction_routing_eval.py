import json
from pathlib import Path

from agentic_bi.core.interaction import classify_interaction

PROJECT_ROOT = Path(__file__).resolve().parents[3]

EVAL_FILE = PROJECT_ROOT / "evals" / "interaction_cases.json"


def load_cases() -> list[dict]:
    """
    Load interaction-routing cases from JSON.
    """

    with open(EVAL_FILE, encoding="utf-8") as file:
        return json.load(file)


def run_interaction_routing_evaluation() -> None:
    """
    Evaluate whether the LLM interaction router selects the
    expected intent, including the web-search conditions.
    """

    cases = load_cases()

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
