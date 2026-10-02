import json
from pathlib import Path

import numpy as np


def save_embedding_cache(
    embeddings: np.ndarray,
    chunks: list[dict],
    output_dir: Path,
) -> None:
    """
    Persist document embeddings and chunk metadata for reuse.
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    np.save(
        output_dir / "chunk_embeddings.npy",
        embeddings,
    )

    with (output_dir / "chunks.json").open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            chunks,
            file,
            ensure_ascii=False,
            indent=2,
        )
        
def load_embedding_cache(
    input_dir: Path,
) -> tuple[np.ndarray, list[dict]]:
    """
    Load persisted document embeddings and chunk metadata.
    """

    embeddings_path = input_dir / "chunk_embeddings.npy"
    chunks_path = input_dir / "chunks.json"

    if not embeddings_path.exists():
        raise FileNotFoundError(
            f"Embedding cache not found: {embeddings_path}"
        )

    if not chunks_path.exists():
        raise FileNotFoundError(
            f"Chunk metadata not found: {chunks_path}"
        )

    embeddings = np.load(embeddings_path)

    with chunks_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        chunks = json.load(file)

    return embeddings, chunks