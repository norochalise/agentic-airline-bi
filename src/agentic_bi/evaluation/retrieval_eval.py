from agentic_bi.evaluation.common import (
    first_relevant_rank,
    load_cases,
    load_qrels,
    reciprocal_rank,
)
from agentic_bi.tools.knowledge_search import search_private_knowledge

CASES_FILE = "retrieval_cases.json"

TOP_K = 5


def run_evaluation() -> None:

    cases = load_cases(CASES_FILE)
    qrels = load_qrels()

    hit_1 = 0
    hit_3 = 0
    hit_5 = 0

    reciprocal_ranks: list[float] = []

    print()
    print("=" * 72)
    print("M14 STRICT EVIDENCE RETRIEVAL EVALUATION")
    print("=" * 72)

    print(f"Cases: {len(cases)}")
    print(f"Retrieval depth: {TOP_K}")
    print()

    for case in cases:
        case_id = case["id"]
        question = case["question"]

        relevant_chunk_ids = qrels[case_id]

        response = search_private_knowledge(query=question, top_k=TOP_K)

        results = response["results"]

        rank = first_relevant_rank(results, relevant_chunk_ids)

        h1 = rank is not None and rank <= 1
        h3 = rank is not None and rank <= 3
        h5 = rank is not None and rank <= 5

        hit_1 += int(h1)
        hit_3 += int(h3)
        hit_5 += int(h5)

        rr = reciprocal_rank(rank)
        reciprocal_ranks.append(rr)

        print("-" * 72)
        print(f"{case_id}: {question}")

        print("Relevant chunks:", ", ".join(sorted(relevant_chunk_ids)))

        if rank is None:
            print("First relevant evidence: NOT FOUND")

        else:
            matched = results[rank - 1]

            print(f"First relevant evidence: rank {rank}")

            print(f"Matched chunk: {matched['chunk_id']}")

            print(f"Source: {matched['source']}")

            print(f"Page: {matched['page_number']}")

            print(f"Similarity score: {matched['score']:.4f}")

        print(f"Hit@1={int(h1)} | Hit@3={int(h3)} | Hit@5={int(h5)} | RR={rr:.3f}")

    total = len(cases)

    hit_at_1 = hit_1 / total
    hit_at_3 = hit_3 / total
    hit_at_5 = hit_5 / total

    mrr_at_5 = sum(reciprocal_ranks) / total

    print()
    print("=" * 72)
    print("STRICT EVIDENCE RETRIEVAL RESULTS")
    print("=" * 72)

    print(f"Hit@1 : {hit_1}/{total} ({hit_at_1:.1%})")

    print(f"Hit@3 : {hit_3}/{total} ({hit_at_3:.1%})")

    print(f"Hit@5 : {hit_5}/{total} ({hit_at_5:.1%})")

    print(f"MRR@5 : {mrr_at_5:.3f}")

    print()
    print("NOTE: These metrics use frozen, manually verified answer-bearing chunk IDs.")

    print(
        "retrieval_002 contains fragmented evidence across "
        "two chunks; Hit@K measures retrieval of at least "
        "one relevant chunk, not complete combined-evidence coverage."
    )


if __name__ == "__main__":
    run_evaluation()
