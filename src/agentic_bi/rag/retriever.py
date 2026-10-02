import numpy as np

from sentence_transformers import SentenceTransformer


def semantic_search(
    query: str,
    chunks: list[dict],
    chunk_embeddings: np.ndarray,
    model: SentenceTransformer,
    top_k: int = 5,
) -> list[dict]:
    """
    Rank document chunks by semantic similarity to a query.

    Assumes embeddings are normalized, allowing cosine similarity
    to be calculated using a dot product.
    """

    query_embedding = model.encode(
        query,
        normalize_embeddings=True,
    )

    scores = chunk_embeddings @ query_embedding

    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []

    for index in top_indices:
        result = chunks[index].copy()
        result["score"] = float(scores[index])

        results.append(result)

    return results