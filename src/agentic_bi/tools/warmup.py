"""Load the local models and data once, before the first question."""

from time import perf_counter

from agentic_bi.rag.reranker import load_reranker
from agentic_bi.tools.flight_analysis import _load_default_flight_data
from agentic_bi.tools.knowledge_search import _load_retrieval_assets


def warm_up_tools() -> dict[str, float]:
    """
    Load the FAISS index, embedding model, reranker and flight data.

    Each loader is cached, so later tool calls reuse what is loaded here.
    Returns the seconds each load took.
    """

    timings = {}

    for name, load in (
        ("retrieval index and embedding model", _load_retrieval_assets),
        ("reranker", load_reranker),
        ("flight data", _load_default_flight_data),
    ):
        started = perf_counter()
        load()
        timings[name] = perf_counter() - started

    return timings
