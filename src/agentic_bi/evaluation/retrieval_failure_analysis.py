from agentic_bi.tools.knowledge_search import search_private_knowledge

FAILURE_CASES = {
    "retrieval_007": {
        "question": (
            "According to Delta's Customer Service Plan, which airport "
            "officials ensure services are properly implemented for customers "
            "with disabilities, and how can a passenger request one?"
        ),
        "expected_chunk": ("delta_customer_service_plan_2026-09-25:c12"),
    },
    "retrieval_009": {
        "question": (
            "In the aircraft-fuel-price risk factor in Delta's 2025 Form "
            "10-K, what percentages of operating expense are stated for "
            "fuel costs in 2025, 2024, and 2023?"
        ),
        "expected_chunk": ("delta_2025_form_10k:p20:c4"),
    },
}


def analyze_case(case_id: str, question: str, expected_chunk: str) -> None:

    # Retrieve deeper than normal top-5 so we can see
    # where the correct evidence actually ranks.
    response = search_private_knowledge(query=question, top_k=15)

    results = response["results"]

    print()
    print("=" * 80)
    print(case_id)
    print("=" * 80)

    print(f"Question: {question}")
    print(f"Expected chunk: {expected_chunk}")
    print()

    expected_rank = None

    for rank, result in enumerate(results, start=1):
        is_expected = result["chunk_id"] == expected_chunk

        if is_expected:
            expected_rank = rank

        marker = " <-- EXPECTED EVIDENCE" if is_expected else ""

        print("-" * 80)
        print(f"RANK {rank} | SCORE {result['score']:.4f}{marker}")

        print(f"Chunk:  {result['chunk_id']}")
        print(f"Source: {result['source']}")
        print(f"Page:   {result['page_number']}")

        print()
        print(result["text"])
        print()

    print("=" * 80)

    if expected_rank is None:
        print("Expected evidence was NOT found in the top 15.")
    else:
        print(f"Expected evidence rank: {expected_rank}")

        if expected_rank > 5:
            print("This explains the strict Hit@5 failure.")


def main() -> None:

    print()
    print("=" * 80)
    print("M14 RETRIEVAL FAILURE ANALYSIS")
    print("=" * 80)

    for case_id, case in FAILURE_CASES.items():
        analyze_case(
            case_id=case_id,
            question=case["question"],
            expected_chunk=case["expected_chunk"],
        )


if __name__ == "__main__":
    main()
