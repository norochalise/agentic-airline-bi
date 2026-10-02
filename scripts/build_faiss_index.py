from agentic_bi.config import FAISS_INDEX_PATH, RAG_CACHE_DIR
from agentic_bi.rag.faiss_store import build_faiss_index, save_faiss_index
from agentic_bi.rag.storage import load_embedding_cache

CACHE_DIR = RAG_CACHE_DIR
INDEX_PATH = FAISS_INDEX_PATH


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
