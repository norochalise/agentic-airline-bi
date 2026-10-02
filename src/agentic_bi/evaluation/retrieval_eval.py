import json
from pathlib import Path
from typing import Any

from agentic_bi.tools.knowledge_search import search_private_knowledge


PROJECT_ROOT = Path(__file__).resolve().parents[3]

CASES_FILE = PROJECT_ROOT / "evals" / "retrieval_cases.json"
QRELS_FILE = PROJECT_ROOT / "evals" / "retrieval_qrels.json"

TOP_K = 5


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def first_relevant_rank(
    results: list[dict[str, Any]],
    relevant_chunk_ids: set[str],
) -> int | None:

    for rank, result in enumerate(results, start=1):
        if result["chunk_id"] in relevant_chunk_ids:
            return rank

    return None


def reciprocal_rank(rank: int | None) -> float:
    if rank is None:
        return 0.0

    return 1.0 / rank


def run_evaluation() -> None:

    dataset = load_json(CASES_FILE)
    qrels = load_json(QRELS_FILE)

    cases = dataset["cases"]

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

        relevant_chunk_ids = set(
            qrels[case_id]
        )

        response = search_private_knowledge(
            query=question,
            top_k=TOP_K,
        )

        results = response["results"]

        rank = first_relevant_rank(
            results,
            relevant_chunk_ids,
        )

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

        print(
            "Relevant chunks:",
            ", ".join(sorted(relevant_chunk_ids)),
        )

        if rank is None:
            print("First relevant evidence: NOT FOUND")

        else:
            matched = results[rank - 1]

            print(
                f"First relevant evidence: rank {rank}"
            )

            print(
                f"Matched chunk: {matched['chunk_id']}"
            )

            print(
                f"Source: {matched['source']}"
            )

            print(
                f"Page: {matched['page_number']}"
            )

            print(
                f"Similarity score: {matched['score']:.4f}"
            )

        print(
            f"Hit@1={int(h1)} | "
            f"Hit@3={int(h3)} | "
            f"Hit@5={int(h5)} | "
            f"RR={rr:.3f}"
        )

    total = len(cases)

    hit_at_1 = hit_1 / total
    hit_at_3 = hit_3 / total
    hit_at_5 = hit_5 / total

    mrr_at_5 = (
        sum(reciprocal_ranks) / total
    )

    print()
    print("=" * 72)
    print("STRICT EVIDENCE RETRIEVAL RESULTS")
    print("=" * 72)

    print(
        f"Hit@1 : {hit_1}/{total} "
        f"({hit_at_1:.1%})"
    )

    print(
        f"Hit@3 : {hit_3}/{total} "
        f"({hit_at_3:.1%})"
    )

    print(
        f"Hit@5 : {hit_5}/{total} "
        f"({hit_at_5:.1%})"
    )

    print(
        f"MRR@5 : {mrr_at_5:.3f}"
    )

    print()
    print(
        "NOTE: These metrics use frozen, manually verified "
        "answer-bearing chunk IDs."
    )

    print(
        "retrieval_002 contains fragmented evidence across "
        "two chunks; Hit@K measures retrieval of at least "
        "one relevant chunk, not complete combined-evidence coverage."
    )


if __name__ == "__main__":
    run_evaluation()