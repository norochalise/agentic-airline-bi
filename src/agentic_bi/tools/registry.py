from agentic_bi.core.schemas import (
    KnowledgeSearchArgs,
    KnowledgeSearchOutput,
    OriginCancellationAnalysisArgs,
    OriginCancellationAnalysisOutput,
)
from agentic_bi.mcp.tools import (
    analyze_top_origin_cancellation_rates_via_mcp,
)
from agentic_bi.tools.improved_knowledge_search import (
    search_private_knowledge_improved,
)


# -------------------------------------------------------------------
# Tool implementations / adapters
# -------------------------------------------------------------------


def run_knowledge_search(
    query: str,
) -> dict:
    """
    Retrieve evidence from the local Delta knowledge base.

    Internally uses the improved M14 retrieval pipeline:

        FAISS candidate retrieval
            -> CrossEncoder reranking
            -> neighboring-chunk expansion

    The returned structure intentionally preserves the original
    knowledge-search tool contract expected by the agent.
    """

    improved_result = search_private_knowledge_improved(
        query=query,
        candidate_k=15,
        top_k=5,
    )

    # ---------------------------------------------------------------
    # ADAPTER
    #
    # improved retriever:
    #     query
    #     reranked_results
    #     context_results
    #
    # agent tool contract:
    #     query
    #     results
    #
    # We give the agent the expanded context while keeping the
    # existing external schema unchanged.
    # ---------------------------------------------------------------

    results = []

    for item in improved_result["context_results"]:
        results.append(
            {
                "source": item["source"],
                "page_number": item["page_number"],
                "chunk_id": item["chunk_id"],
                "score": (
                    item["faiss_score"]
                    if item["faiss_score"] is not None
                    else 0.0
                ),
                "text": item["text"],
            }
        )

    return {
        "query": query,
        "results": results,
    }


# -------------------------------------------------------------------
# Tool definitions exposed to the model
# -------------------------------------------------------------------


TOOLS = [
    {
        "type": "function",
        "name": "search_private_knowledge",
        "description": (
            "Search indexed Delta documents, policies, contracts, "
            "reports, and other internal business knowledge."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Focused semantic retrieval query describing "
                        "the evidence required."
                    ),
                },
            },
            "required": [
                "query",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "analyze_top_origin_cancellation_rates",
        "description": (
            "Analyze July 2026 Delta-marketed domestic flight data "
            "and rank origin airports by cancellation rate."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "min_flights": {
                    "type": "integer",
                    "description": (
                        "Minimum number of flights required for an "
                        "airport to be included in the analysis."
                    ),
                },
                "top_n": {
                    "type": "integer",
                    "description": (
                        "Number of highest cancellation-rate airports "
                        "to return."
                    ),
                },
            },
            "required": [
                "min_flights",
                "top_n",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


# -------------------------------------------------------------------
# Runtime function registry
# -------------------------------------------------------------------


FUNCTIONS = {
    "search_private_knowledge":
        run_knowledge_search,

    "analyze_top_origin_cancellation_rates":
        analyze_top_origin_cancellation_rates_via_mcp,
}


# -------------------------------------------------------------------
# Input validation
# -------------------------------------------------------------------


INPUT_SCHEMAS = {
    "search_private_knowledge":
        KnowledgeSearchArgs,

    "analyze_top_origin_cancellation_rates":
        OriginCancellationAnalysisArgs,
}


# -------------------------------------------------------------------
# Output validation
# -------------------------------------------------------------------


OUTPUT_SCHEMAS = {
    "search_private_knowledge":
        KnowledgeSearchOutput,

    "analyze_top_origin_cancellation_rates":
        OriginCancellationAnalysisOutput,
}


# -------------------------------------------------------------------
# Reliability policies
# -------------------------------------------------------------------


TOOL_POLICIES = {
    "search_private_knowledge": {
        "max_attempts": 1,
    },
    "analyze_top_origin_cancellation_rates": {
        "max_attempts": 2,
    },
}