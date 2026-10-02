"""Shared loaders and metrics for the evaluation scripts."""

from typing import Any

from agentic_bi.config import EVALS_DIR
from agentic_bi.core.persistence import read_json


def load_eval_file(name: str) -> Any:
    """Load a JSON file from the frozen `evals/` folder."""

    return read_json(EVALS_DIR / name)


def load_cases(name: str) -> list[dict[str, Any]]:
    """Load evaluation cases, stored either as a list or as {"cases": [...]}."""

    data = load_eval_file(name)

    return data["cases"] if isinstance(data, dict) else data


def load_qrels() -> dict[str, set[str]]:
    """Frozen, manually verified answer-bearing chunk IDs per retrieval case."""

    return {
        case_id: set(chunk_ids)
        for case_id, chunk_ids in load_eval_file("retrieval_qrels.json").items()
    }


def first_relevant_rank(
    results: list[dict[str, Any]], relevant_chunk_ids: set[str]
) -> int | None:
    """1-based rank of the first relevant chunk, or None if none appears."""

    for rank, result in enumerate(results, start=1):
        if result["chunk_id"] in relevant_chunk_ids:
            return rank

    return None


def hit_at_k(rank: int | None, k: int) -> int:
    """1 if relevant evidence appears within rank K, else 0."""

    return int(rank is not None and rank <= k)


def reciprocal_rank(rank: int | None, max_rank: int | None = None) -> float:
    """1/rank, or 0 when nothing relevant was found (or it ranked past max_rank)."""

    if rank is None or (max_rank is not None and rank > max_rank):
        return 0.0

    return 1.0 / rank


def print_banner(title: str, width: int = 72) -> None:
    print("=" * width)
    print(title)
    print("=" * width)
