from pathlib import Path

from agentic_bi.rag.faiss_store import build_faiss_index, save_faiss_index
from agentic_bi.rag.storage import load_embedding_cache

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CACHE_DIR = PROJECT_ROOT / "data" / "processed" / "rag"

INDEX_PATH = CACHE_DIR / "delta_knowledge.faiss"


def main() -> None:
    # Load previously generated embeddings and metadata.
    embeddings, chunks = load_embedding_cache(CACHE_DIR)

    # Build the vector index.
    index = build_faiss_index(embeddings)

    # Persist the index for future searches.
    save_faiss_index(index=index, file_path=INDEX_PATH)

    print("Chunks:", len(chunks))
    print("Vectors indexed:", index.ntotal)
    print("Dimensions:", index.d)
    print("Saved index:", INDEX_PATH)


if __name__ == "__main__":
    main()
