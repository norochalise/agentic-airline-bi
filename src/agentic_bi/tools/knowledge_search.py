from functools import lru_cache

from agentic_bi.config import FAISS_INDEX_PATH, RAG_CACHE_DIR
from agentic_bi.rag.embeddings import load_embedding_model
from agentic_bi.rag.faiss_store import load_faiss_index, search_faiss
from agentic_bi.rag.storage import load_embedding_cache


@lru_cache(maxsize=1)
def _load_retrieval_assets():
    """
    Load reusable local retrieval assets once per process.
    """

    _, chunks = load_embedding_cache(RAG_CACHE_DIR)

    index = load_faiss_index(FAISS_INDEX_PATH)

    model = load_embedding_model()

    return chunks, index, model


def search_private_knowledge(query: str, top_k: int = 5) -> dict:
    """
    Retrieve semantically relevant evidence from the local Delta
    knowledge base using local embeddings and FAISS.
    """

    if not query.strip():
        raise ValueError("query cannot be empty")

    if top_k <= 0:
        raise ValueError("top_k must be greater than zero")

    chunks, index, model = _load_retrieval_assets()

    query_embedding = model.encode(query, normalize_embeddings=True)

    matches = search_faiss(index=index, query_embedding=query_embedding, top_k=top_k)

    results = []

    for chunk_index, score in matches:
        chunk = chunks[chunk_index]

        results.append(
            {
                "source": chunk["source"],
                "page_number": chunk["page_number"],
                "chunk_id": chunk["chunk_id"],
                "score": float(score),
                "text": chunk["text"],
            }
        )

    return {"query": query, "results": results}
