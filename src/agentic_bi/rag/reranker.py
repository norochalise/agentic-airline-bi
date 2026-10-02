from functools import lru_cache

from sentence_transformers import CrossEncoder


RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def load_reranker() -> CrossEncoder:
    """
    Load the local cross-encoder reranker once per process.
    """
    return CrossEncoder(RERANKER_MODEL_NAME)


def rerank_results(
    query: str,
    results: list[dict],
    top_k: int = 5,
) -> list[dict]:
    """
    Rerank retrieved chunks according to their relevance
    to the user's query.
    """

    if not query.strip():
        raise ValueError("query cannot be empty")

    if top_k <= 0:
        raise ValueError("top_k must be greater than zero")

    if not results:
        return []

    model = load_reranker()

    # CrossEncoder receives:
    #
    # [question, candidate chunk]
    #
    # and produces a relevance score.
    pairs = [
        [query, result["text"]]
        for result in results
    ]

    scores = model.predict(pairs)

    reranked = []

    for result, score in zip(results, scores):
        item = result.copy()

        # Preserve the original FAISS similarity.
        item["faiss_score"] = item.get("score")

        # Add the new reranker relevance score.
        item["rerank_score"] = float(score)

        reranked.append(item)

    # Highest reranker score first.
    reranked.sort(
        key=lambda item: item["rerank_score"],
        reverse=True,
    )

    return reranked[:top_k]