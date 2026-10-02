from pathlib import Path

import faiss
import numpy as np


def build_faiss_index(embeddings: np.ndarray) -> faiss.Index:
    """
    Build an exact inner-product index from normalized embeddings.

    With normalized vectors, inner product is equivalent to
    cosine similarity.
    """

    vectors = np.asarray(embeddings, dtype="float32")

    if vectors.ndim != 2:
        raise ValueError("embeddings must be a 2D array")

    dimension = vectors.shape[1]

    index = faiss.IndexFlatIP(dimension)
    index.add(vectors)

    return index


def save_faiss_index(index: faiss.Index, file_path: Path) -> None:
    """
    Persist a FAISS index for reuse across runs.
    """

    file_path.parent.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(file_path))


def load_faiss_index(file_path: Path) -> faiss.Index:
    """
    Load a persisted FAISS index.
    """

    if not file_path.exists():
        raise FileNotFoundError(f"FAISS index not found: {file_path}")

    return faiss.read_index(str(file_path))


def search_faiss(
    index: faiss.Index, query_embedding: np.ndarray, top_k: int = 5
) -> list[tuple[int, float]]:
    """
    Return the nearest vector IDs and similarity scores.
    """

    query_vector = np.asarray(query_embedding, dtype="float32").reshape(1, -1)

    scores, indices = index.search(query_vector, top_k)

    return list(zip(indices[0].tolist(), scores[0].tolist(), strict=True))
