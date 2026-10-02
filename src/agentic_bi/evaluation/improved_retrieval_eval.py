import json
from pathlib import Path

from agentic_bi.tools.improved_knowledge_search import (
    search_private_knowledge_improved,
)
from agentic_bi.tools.knowledge_search import (
    search_private_knowledge,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]

CASES_PATH = PROJECT_ROOT / "evals" / "retrieval_cases.json"


# ============================================================
# FROZEN STRICT RELEVANCE LABELS
# ============================================================
#
# These are manually verified answer-bearing chunks.
#
# IMPORTANT:
# Do not change these labels simply because a retrieval method
# succeeds or fails.
#
# For normal cases, one complete answer-bearing chunk is enough.
#
# retrieval_002 is different:
# its complete evidence is split across two adjacent chunks.
# Therefore it is handled separately below as fragmented evidence.
# ============================================================

RELEVANT_CHUNKS = {
    "retrieval_001": {
        "delta_domestic_contract_plain_language_2026-08-18:p21:c1",
    },

    # Fragmented evidence.
    # No single chunk contains the complete verified answer.
    "retrieval_002": set(),

    "retrieval_003": {
        "delta_domestic_contract_plain_language_2026-08-18:p8:c2",
    },

    "retrieval_004": {
        "delta_domestic_contract_plain_language_2026-08-18:p19:c2",
    },

    "retrieval_005": {
        "delta_customer_service_plan_2026-09-25:c2",
    },

    "retrieval_006": {
        "delta_customer_service_plan_2026-09-25:c17",
    },

    "retrieval_007": {
        "delta_customer_service_plan_2026-09-25:c12",
    },

    "retrieval_008": {
        "delta_2025_form_10k:p5:c2",
    },

    "retrieval_009": {
        "delta_2025_form_10k:p20:c4",
    },

    "retrieval_010": {
        "dot_september_2026_atcr_july_data:p6:c0",
        "dot_september_2026_atcr_july_data:p8:c0",
    },
}


# ============================================================
# FRAGMENTED EVIDENCE
# ============================================================
#
# Some questions require multiple chunks together.
#
# retrieval_002 requires:
#
# c0 -> general $4,700 baggage liability cap
# c1 -> wheelchair / assistive-device exception
#
# Neither chunk alone should count as a complete strict
# answer-bearing retrieval hit.
#
# However, if BOTH appear in the final expanded context,
# the system has enough evidence to answer the question.
# ============================================================

FRAGMENTED_EVIDENCE_GROUPS = {
    "retrieval_002": {
        "delta_domestic_contract_plain_language_2026-08-18:p14:c0",
        "delta_domestic_contract_plain_language_2026-08-18:p14:c1",
    },
}


def load_cases() -> list[dict]:
    """
    Load the frozen M14 retrieval evaluation dataset.
    """

    with CASES_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    return data["cases"]


def first_relevant_rank(
    results: list[dict],
    relevant_chunks: set[str],
) -> int | None:
    """
    Return the rank of the first complete answer-bearing chunk.

    If the case has no single complete relevant chunk,
    or no relevant chunk appears in the results,
    return None.
    """

    if not relevant_chunks:
        return None

    for rank, result in enumerate(results, start=1):
        if result["chunk_id"] in relevant_chunks:
            return rank

    return None


def hit_at_k(
    rank: int | None,
    k: int,
) -> int:
    """
    Return 1 if relevant evidence appears within rank K.
    Otherwise return 0.
    """

    if rank is None:
        return 0

    return int(rank <= k)


def reciprocal_rank(
    rank: int | None,
    max_rank: int = 5,
) -> float:
    """
    Calculate reciprocal rank.

    Examples:

    rank 1 -> 1.0
    rank 2 -> 0.5
    rank 3 -> 0.333...
    rank > max_rank -> 0
    not found -> 0
    """

    if rank is None:
        return 0.0

    if rank > max_rank:
        return 0.0

    return 1.0 / rank


def context_contains_evidence(
    case_id: str,
    context_results: list[dict],
    relevant_chunks: set[str],
) -> bool:
    """
    Check whether the final expanded RAG context contains
    enough verified evidence to answer the question.

    Normal case:
        At least one complete answer-bearing chunk must exist.

    Fragmented case:
        ALL required chunks must exist together.
    """

    context_ids = {
        result["chunk_id"]
        for result in context_results
    }

    # --------------------------------------------------------
    # Fragmented evidence
    # --------------------------------------------------------

    if case_id in FRAGMENTED_EVIDENCE_GROUPS:

        required_chunks = FRAGMENTED_EVIDENCE_GROUPS[
            case_id
        ]

        return required_chunks.issubset(context_ids)

    # --------------------------------------------------------
    # Normal answer-bearing evidence
    # --------------------------------------------------------

    return bool(
        context_ids & relevant_chunks
    )


def print_case_result(
    case_id: str,
    baseline_rank: int | None,
    reranked_rank: int | None,
    context_hit: bool,
    fragmented: bool,
) -> None:
    """
    Print one evaluation case.
    """

    baseline_display = (
        str(baseline_rank)
        if baseline_rank is not None
        else "NOT FOUND"
    )

    reranked_display = (
        str(reranked_rank)
        if reranked_rank is not None
        else "NOT FOUND"
    )

    print()
    print(case_id)

    if fragmented:
        print(
            "  Evidence type: FRAGMENTED "
            "(multiple chunks required)"
        )

    print(
        f"  Baseline strict rank: "
        f"{baseline_display}"
    )

    print(
        f"  Reranked strict rank: "
        f"{reranked_display}"
    )

    print(
        "  Expanded context evidence:",
        "YES" if context_hit else "NO",
    )


def main() -> None:
    """
    Compare:

    1. Baseline FAISS top-5 retrieval
    2. FAISS top-15 + CrossEncoder reranking to top-5
    3. Reranked retrieval + neighbor-expanded context

    Ranked retrieval metrics and final context coverage
    are deliberately kept separate.
    """

    cases = load_cases()

    # --------------------------------------------------------
    # Baseline metrics
    # --------------------------------------------------------

    baseline_hit_1 = 0
    baseline_hit_3 = 0
    baseline_hit_5 = 0
    baseline_rr = 0.0

    # --------------------------------------------------------
    # Reranked metrics
    # --------------------------------------------------------

    reranked_hit_1 = 0
    reranked_hit_3 = 0
    reranked_hit_5 = 0
    reranked_rr = 0.0

    # --------------------------------------------------------
    # Final context coverage
    # --------------------------------------------------------

    context_hits = 0

    # Count fragmented cases for reporting.
    fragmented_case_count = 0

    print("=" * 72)
    print(
        "M14 BASELINE VS IMPROVED "
        "RETRIEVAL EVALUATION"
    )
    print("=" * 72)

    print(
        f"Cases: {len(cases)}"
    )

    print(
        "FAISS baseline depth: 5"
    )

    print(
        "Improved candidate depth: 15"
    )

    print(
        "Reranked depth: 5"
    )

    print()

    # ========================================================
    # RUN ALL FROZEN CASES
    # ========================================================

    for case in cases:

        # The verified dataset uses "id".
        case_id = case["id"]

        question = case["question"]

        relevant_chunks = RELEVANT_CHUNKS[
            case_id
        ]

        fragmented = (
            case_id
            in FRAGMENTED_EVIDENCE_GROUPS
        )

        if fragmented:
            fragmented_case_count += 1

        # ====================================================
        # 1. BASELINE FAISS
        # ====================================================

        baseline = search_private_knowledge(
            query=question,
            top_k=5,
        )

        baseline_rank = first_relevant_rank(
            results=baseline["results"],
            relevant_chunks=relevant_chunks,
        )

        baseline_hit_1 += hit_at_k(
            baseline_rank,
            1,
        )

        baseline_hit_3 += hit_at_k(
            baseline_rank,
            3,
        )

        baseline_hit_5 += hit_at_k(
            baseline_rank,
            5,
        )

        baseline_rr += reciprocal_rank(
            baseline_rank,
            max_rank=5,
        )

        # ====================================================
        # 2. IMPROVED RERANKED RETRIEVAL
        # ====================================================

        improved = (
            search_private_knowledge_improved(
                query=question,
                candidate_k=15,
                top_k=5,
            )
        )

        reranked_rank = first_relevant_rank(
            results=improved[
                "reranked_results"
            ],
            relevant_chunks=relevant_chunks,
        )

        reranked_hit_1 += hit_at_k(
            reranked_rank,
            1,
        )

        reranked_hit_3 += hit_at_k(
            reranked_rank,
            3,
        )

        reranked_hit_5 += hit_at_k(
            reranked_rank,
            5,
        )

        reranked_rr += reciprocal_rank(
            reranked_rank,
            max_rank=5,
        )

        # ====================================================
        # 3. FINAL EXPANDED CONTEXT
        # ====================================================

        context_hit = context_contains_evidence(
            case_id=case_id,
            context_results=improved[
                "context_results"
            ],
            relevant_chunks=relevant_chunks,
        )

        context_hits += int(
            context_hit
        )

        # ====================================================
        # CASE OUTPUT
        # ====================================================

        print_case_result(
            case_id=case_id,
            baseline_rank=baseline_rank,
            reranked_rank=reranked_rank,
            context_hit=context_hit,
            fragmented=fragmented,
        )

    total = len(cases)

    # ========================================================
    # BASELINE RESULTS
    # ========================================================

    print()
    print("=" * 72)
    print(
        "STRICT BASELINE FAISS RESULTS"
    )
    print("=" * 72)

    print(
        f"Hit@1: "
        f"{baseline_hit_1}/{total} "
        f"= {baseline_hit_1 / total:.1%}"
    )

    print(
        f"Hit@3: "
        f"{baseline_hit_3}/{total} "
        f"= {baseline_hit_3 / total:.1%}"
    )

    print(
        f"Hit@5: "
        f"{baseline_hit_5}/{total} "
        f"= {baseline_hit_5 / total:.1%}"
    )

    print(
        f"MRR@5: "
        f"{baseline_rr / total:.3f}"
    )

    # ========================================================
    # RERANKED RESULTS
    # ========================================================

    print()
    print("=" * 72)
    print(
        "STRICT RERANKED RESULTS"
    )
    print("=" * 72)

    print(
        f"Hit@1: "
        f"{reranked_hit_1}/{total} "
        f"= {reranked_hit_1 / total:.1%}"
    )

    print(
        f"Hit@3: "
        f"{reranked_hit_3}/{total} "
        f"= {reranked_hit_3 / total:.1%}"
    )

    print(
        f"Hit@5: "
        f"{reranked_hit_5}/{total} "
        f"= {reranked_hit_5 / total:.1%}"
    )

    print(
        f"MRR@5: "
        f"{reranked_rr / total:.3f}"
    )

    # ========================================================
    # FINAL CONTEXT COVERAGE
    # ========================================================

    print()
    print("=" * 72)
    print(
        "EXPANDED CONTEXT EVIDENCE COVERAGE"
    )
    print("=" * 72)

    print(
        f"Evidence coverage: "
        f"{context_hits}/{total} "
        f"= {context_hits / total:.1%}"
    )

    print(
        f"Fragmented evidence cases: "
        f"{fragmented_case_count}"
    )

    # ========================================================
    # IMPORTANT EVALUATION NOTES
    # ========================================================

    print()
    print("=" * 72)
    print("EVALUATION NOTES")
    print("=" * 72)

    print(
        "1. Hit@K and MRR measure only complete "
        "single-chunk answer-bearing evidence."
    )

    print(
        "2. retrieval_002 is intentionally NOT counted "
        "as a strict ranked hit because its complete "
        "answer requires two adjacent chunks."
    )

    print(
        "3. Expanded context coverage can count "
        "retrieval_002 only when BOTH required chunks "
        "are present."
    )

    print(
        "4. Expanded context coverage is NOT Hit@K. "
        "Neighbor chunks do not receive artificial "
        "retrieval ranks."
    )

    print(
        "5. These results describe this frozen "
        "10-case M14 development evaluation set only."
    )


if __name__ == "__main__":
    main()