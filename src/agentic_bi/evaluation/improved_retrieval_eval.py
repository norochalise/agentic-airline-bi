from agentic_bi.config import RETRIEVAL_CANDIDATE_K, RETRIEVAL_TOP_K
from agentic_bi.evaluation.common import (
    first_relevant_rank,
    hit_at_k,
    load_cases,
    load_qrels,
    reciprocal_rank,
)
from agentic_bi.tools.improved_knowledge_search import search_private_knowledge_improved
from agentic_bi.tools.knowledge_search import search_private_knowledge

CASES_FILE = "retrieval_cases.json"


# ============================================================
# FROZEN STRICT RELEVANCE LABELS
# ============================================================
#
# Labels come from evals/retrieval_qrels.json: manually verified
# answer-bearing chunks. Do not change them because a retrieval
# method succeeds or fails.
#
# For normal cases, one complete answer-bearing chunk is enough.
#
# Fragmented cases are different: their complete evidence is split
# across chunks (retrieval_002: c0 has the general $4,700 baggage
# liability cap, c1 the wheelchair / assistive-device exception).
# Neither chunk alone is a strict ranked hit, but the expanded context
# has enough evidence when it contains ALL of them.
# ============================================================

FRAGMENTED_CASES = {"retrieval_002"}

QRELS = load_qrels()

RELEVANT_CHUNKS = {
    case_id: set() if case_id in FRAGMENTED_CASES else chunk_ids
    for case_id, chunk_ids in QRELS.items()
}

FRAGMENTED_EVIDENCE_GROUPS = {case_id: QRELS[case_id] for case_id in FRAGMENTED_CASES}


def context_contains_evidence(
    case_id: str, context_results: list[dict], relevant_chunks: set[str]
) -> bool:
    """
    Check whether the final expanded RAG context contains
    enough verified evidence to answer the question.

    Normal case:
        At least one complete answer-bearing chunk must exist.

    Fragmented case:
        ALL required chunks must exist together.
    """

    context_ids = {result["chunk_id"] for result in context_results}

    # --------------------------------------------------------
    # Fragmented evidence
    # --------------------------------------------------------

    if case_id in FRAGMENTED_EVIDENCE_GROUPS:
        required_chunks = FRAGMENTED_EVIDENCE_GROUPS[case_id]

        return required_chunks.issubset(context_ids)

    # --------------------------------------------------------
    # Normal answer-bearing evidence
    # --------------------------------------------------------

    return bool(context_ids & relevant_chunks)


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

    baseline_display = str(baseline_rank) if baseline_rank is not None else "NOT FOUND"

    reranked_display = str(reranked_rank) if reranked_rank is not None else "NOT FOUND"

    print()
    print(case_id)

    if fragmented:
        print("  Evidence type: FRAGMENTED (multiple chunks required)")

    print(f"  Baseline strict rank: {baseline_display}")

    print(f"  Reranked strict rank: {reranked_display}")

    print("  Expanded context evidence:", "YES" if context_hit else "NO")


def main() -> None:
    """
    Compare:

    1. Baseline FAISS top-5 retrieval
    2. FAISS top-15 + CrossEncoder reranking to top-5
    3. Reranked retrieval + neighbor-expanded context

    Ranked retrieval metrics and final context coverage
    are deliberately kept separate.
    """

    cases = load_cases(CASES_FILE)

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
    print("M14 BASELINE VS IMPROVED RETRIEVAL EVALUATION")
    print("=" * 72)

    print(f"Cases: {len(cases)}")

    print("FAISS baseline depth: 5")

    print("Improved candidate depth: 15")

    print("Reranked depth: 5")

    print()

    # ========================================================
    # RUN ALL FROZEN CASES
    # ========================================================

    for case in cases:
        # The verified dataset uses "id".
        case_id = case["id"]

        question = case["question"]

        relevant_chunks = RELEVANT_CHUNKS[case_id]

        fragmented = case_id in FRAGMENTED_EVIDENCE_GROUPS

        if fragmented:
            fragmented_case_count += 1

        # ====================================================
        # 1. BASELINE FAISS
        # ====================================================

        baseline = search_private_knowledge(query=question, top_k=5)

        baseline_rank = first_relevant_rank(
            results=baseline["results"], relevant_chunk_ids=relevant_chunks
        )

        baseline_hit_1 += hit_at_k(baseline_rank, 1)

        baseline_hit_3 += hit_at_k(baseline_rank, 3)

        baseline_hit_5 += hit_at_k(baseline_rank, 5)

        baseline_rr += reciprocal_rank(baseline_rank, max_rank=5)

        # ====================================================
        # 2. IMPROVED RERANKED RETRIEVAL
        # ====================================================

        improved = search_private_knowledge_improved(
            query=question, candidate_k=RETRIEVAL_CANDIDATE_K, top_k=RETRIEVAL_TOP_K
        )

        reranked_rank = first_relevant_rank(
            results=improved["reranked_results"], relevant_chunk_ids=relevant_chunks
        )

        reranked_hit_1 += hit_at_k(reranked_rank, 1)

        reranked_hit_3 += hit_at_k(reranked_rank, 3)

        reranked_hit_5 += hit_at_k(reranked_rank, 5)

        reranked_rr += reciprocal_rank(reranked_rank, max_rank=5)

        # ====================================================
        # 3. FINAL EXPANDED CONTEXT
        # ====================================================

        context_hit = context_contains_evidence(
            case_id=case_id,
            context_results=improved["context_results"],
            relevant_chunks=relevant_chunks,
        )

        context_hits += int(context_hit)

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
    print("STRICT BASELINE FAISS RESULTS")
    print("=" * 72)

    print(f"Hit@1: {baseline_hit_1}/{total} = {baseline_hit_1 / total:.1%}")

    print(f"Hit@3: {baseline_hit_3}/{total} = {baseline_hit_3 / total:.1%}")

    print(f"Hit@5: {baseline_hit_5}/{total} = {baseline_hit_5 / total:.1%}")

    print(f"MRR@5: {baseline_rr / total:.3f}")

    # ========================================================
    # RERANKED RESULTS
    # ========================================================

    print()
    print("=" * 72)
    print("STRICT RERANKED RESULTS")
    print("=" * 72)

    print(f"Hit@1: {reranked_hit_1}/{total} = {reranked_hit_1 / total:.1%}")

    print(f"Hit@3: {reranked_hit_3}/{total} = {reranked_hit_3 / total:.1%}")

    print(f"Hit@5: {reranked_hit_5}/{total} = {reranked_hit_5 / total:.1%}")

    print(f"MRR@5: {reranked_rr / total:.3f}")

    # ========================================================
    # FINAL CONTEXT COVERAGE
    # ========================================================

    print()
    print("=" * 72)
    print("EXPANDED CONTEXT EVIDENCE COVERAGE")
    print("=" * 72)

    print(f"Evidence coverage: {context_hits}/{total} = {context_hits / total:.1%}")

    print(f"Fragmented evidence cases: {fragmented_case_count}")

    # ========================================================
    # IMPORTANT EVALUATION NOTES
    # ========================================================

    print()
    print("=" * 72)
    print("EVALUATION NOTES")
    print("=" * 72)

    print(
        "1. Hit@K and MRR measure only complete single-chunk answer-bearing evidence."
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
