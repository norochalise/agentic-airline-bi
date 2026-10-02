from agentic_bi.rag.reranker import rerank_results
from agentic_bi.tools.knowledge_search import (
    _load_retrieval_assets,
    search_private_knowledge,
)


def search_private_knowledge_improved(
    query: str,
    candidate_k: int = 15,
    top_k: int = 5,
) -> dict:
    """
    Improved local retrieval pipeline.

    Pipeline:
        1. FAISS retrieves a broad candidate set.
        2. CrossEncoder reranks those candidates.
        3. Keep the best reranked chunks.
        4. Add previous/next neighboring chunks.

    The original search_private_knowledge() remains unchanged
    so it can continue serving as our baseline.
    """

    if not query.strip():
        raise ValueError("query cannot be empty")

    if candidate_k <= 0:
        raise ValueError("candidate_k must be greater than zero")

    if top_k <= 0:
        raise ValueError("top_k must be greater than zero")

    if candidate_k < top_k:
        raise ValueError(
            "candidate_k must be greater than or equal to top_k"
        )

    # ---------------------------------------------------------
    # STEP 1: FAISS candidate retrieval
    # ---------------------------------------------------------

    baseline = search_private_knowledge(
        query=query,
        top_k=candidate_k,
    )

    # ---------------------------------------------------------
    # STEP 2: CrossEncoder reranking
    # ---------------------------------------------------------

    reranked = rerank_results(
        query=query,
        results=baseline["results"],
        top_k=top_k,
    )

    # ---------------------------------------------------------
    # STEP 3: Load stored chunks for neighbor lookup
    # ---------------------------------------------------------

    chunks, _, _ = _load_retrieval_assets()

    chunk_positions = {
        chunk["chunk_id"]: index
        for index, chunk in enumerate(chunks)
    }

    # ---------------------------------------------------------
    # STEP 4: Build final context
    # ---------------------------------------------------------

    context_results = []
    seen_chunk_ids = set()

    def add_chunk(
        chunk: dict,
        retrieval_type: str,
        rerank_score: float | None = None,
        faiss_score: float | None = None,
        rerank_rank: int | None = None,
    ) -> None:

        chunk_id = chunk["chunk_id"]

        if chunk_id in seen_chunk_ids:
            return

        seen_chunk_ids.add(chunk_id)

        context_results.append(
            {
                "source": chunk["source"],
                "page_number": chunk["page_number"],
                "chunk_id": chunk_id,
                "text": chunk["text"],
                "retrieval_type": retrieval_type,
                "faiss_score": faiss_score,
                "rerank_score": rerank_score,
                "rerank_rank": rerank_rank,
            }
        )

    for rank, result in enumerate(reranked, start=1):

        chunk_id = result["chunk_id"]
        position = chunk_positions[chunk_id]
        current_chunk = chunks[position]

        # Main reranked semantic result.
        add_chunk(
            chunk=current_chunk,
            retrieval_type="reranked",
            rerank_score=result["rerank_score"],
            faiss_score=result["faiss_score"],
            rerank_rank=rank,
        )

        # Previous neighboring chunk.
        if position > 0:
            previous_chunk = chunks[position - 1]

            if previous_chunk["source"] == current_chunk["source"]:
                add_chunk(
                    chunk=previous_chunk,
                    retrieval_type="neighbor_previous",
                )

        # Next neighboring chunk.
        if position + 1 < len(chunks):
            next_chunk = chunks[position + 1]

            if next_chunk["source"] == current_chunk["source"]:
                add_chunk(
                    chunk=next_chunk,
                    retrieval_type="neighbor_next",
                )

    return {
        "query": query,
        "candidate_k": candidate_k,
        "top_k": top_k,

        # Ranked results used for retrieval metrics.
        "reranked_results": reranked,

        # Expanded chunks intended for final RAG context.
        "context_results": context_results,
    }