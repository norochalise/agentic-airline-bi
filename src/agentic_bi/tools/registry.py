"""The single definition of every tool the agent can use.

Each tool is one `ToolSpec`. The OpenAI tool JSON, input and output
validation, retry policy, access policy, per-run budget and the prompt's
capability list are all derived from it.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

from agentic_bi.config import (
    MAX_DATA_ANALYSIS_CALLS,
    MAX_KNOWLEDGE_SEARCHES,
    MAX_WEB_SEARCHES,
    RETRIEVAL_CANDIDATE_K,
    RETRIEVAL_TOP_K,
    tool_transport,
)
from agentic_bi.core.schemas import (
    DelayCausesArgs,
    DelayCausesOutput,
    FlightPerformanceArgs,
    FlightPerformanceOutput,
    IssueCustomerCreditArgs,
    IssueCustomerCreditOutput,
    KnowledgeSearchArgs,
    KnowledgeSearchOutput,
    OfficialWebSearchArgs,
    OfficialWebSearchOutput,
    OriginCancellationAnalysisArgs,
    OriginCancellationAnalysisOutput,
)
from agentic_bi.mcp.tools import analyze_top_origin_cancellation_rates_via_mcp
from agentic_bi.tools.delta_official_web import search_delta_official_web
from agentic_bi.tools.flight_analysis import analyze_top_origin_cancellation_rates
from agentic_bi.tools.flight_metrics import (
    analyze_delay_causes,
    rank_flight_performance,
)
from agentic_bi.tools.improved_knowledge_search import search_private_knowledge_improved
from agentic_bi.tools.mock_actions import issue_customer_credit

# -------------------------------------------------------------------
# Tool implementations / adapters
# -------------------------------------------------------------------


def run_knowledge_search(query: str) -> dict:
    """
    Retrieve evidence from the local Delta knowledge base.

    Pipeline: FAISS candidates -> CrossEncoder reranking -> neighbouring
    chunks. Each result says how it was retrieved, so the model can tell
    primary evidence ("reranked") from surrounding context ("neighbor_*").
    """

    improved_result = search_private_knowledge_improved(
        query=query, candidate_k=RETRIEVAL_CANDIDATE_K, top_k=RETRIEVAL_TOP_K
    )

    results = [
        {
            "source": item["source"],
            "page_number": item["page_number"],
            "chunk_id": item["chunk_id"],
            "retrieval_type": item["retrieval_type"],
            "score": item["faiss_score"],
            "rerank_score": item["rerank_score"],
            "text": item["text"],
        }
        for item in improved_result["context_results"]
    ]

    return {"query": query, "results": results}


def run_origin_cancellation_analysis(min_flights: int, top_n: int) -> dict:
    """
    Rank origin airports by cancellation rate.

    Runs in this process by default. TOOL_TRANSPORT=mcp routes the call
    through the MCP server instead (one subprocess per call).
    """

    if tool_transport() == "mcp":
        return analyze_top_origin_cancellation_rates_via_mcp(
            min_flights=min_flights, top_n=top_n
        )

    return analyze_top_origin_cancellation_rates(min_flights=min_flights, top_n=top_n)


def run_official_web_search(query: str) -> dict:
    """
    Search official Delta and U.S. government websites.

    Returns only the fields covered by the tool output contract.
    """

    search_result = search_delta_official_web(query=query, num_results=3)

    return {
        "query": query,
        "results": [
            {
                "title": result["title"],
                "url": result["url"],
                "highlights": [
                    str(highlight) for highlight in result.get("highlights", [])
                ],
            }
            for result in search_result.get("results", [])
        ],
    }


# -------------------------------------------------------------------
# Tool specification
# -------------------------------------------------------------------

# Validation keywords left out of the model-facing schema. Pydantic
# still enforces them when the arguments come back.
_MODEL_SCHEMA_EXCLUDED_KEYS = {
    "title",
    "default",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
}


def _strict_parameters(model: type[BaseModel]) -> dict[str, Any]:
    """OpenAI strict-mode parameter schema for a pydantic input model."""

    schema = model.model_json_schema()

    properties = {
        name: {
            key: value
            for key, value in field_schema.items()
            if key not in _MODEL_SCHEMA_EXCLUDED_KEYS
        }
        for name, field_schema in schema["properties"].items()
    }

    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


@dataclass(frozen=True)
class ToolSpec:
    """Everything the agent needs to know about one tool."""

    name: str
    description: str
    func: Callable[..., dict]
    input_model: type[BaseModel]
    output_model: type[BaseModel]

    # Capability entry for the agent prompt: the text after the tool name
    # (starting with "\n   " when the description goes on the next lines).
    prompt_summary: str = ""

    # What the tool does, for per-run counters: document search, dataset
    # analysis, official web search, or a write action.
    category: Literal["knowledge", "data", "web", "action"] = "data"

    access: Literal["read", "write"] = "read"
    requires_approval: bool = False
    max_attempts: int = 1

    # Executions allowed per run; None means no per-tool limit.
    max_calls_per_run: int | None = None

    # Skills that may be offered this tool; None means every skill. A set
    # may include None for runs where no skill was selected.
    skills: frozenset[str | None] | None = None

    # False for actions that exist for the guard but are never offered.
    offered_to_model: bool = True

    def openai_tool(self) -> dict[str, Any]:
        """The function definition sent to the Responses API."""

        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": _strict_parameters(self.input_model),
            "strict": True,
        }

    def is_offered_to(self, skill: str | None) -> bool:
        return self.offered_to_model and (self.skills is None or skill in self.skills)


KNOWLEDGE_SEARCH_TOOL = "search_private_knowledge"
DATA_ANALYSIS_TOOL = "analyze_top_origin_cancellation_rates"
WEB_SEARCH_TOOL = "search_official_web"
PERFORMANCE_TOOL = "rank_flight_performance"
DELAY_CAUSES_TOOL = "analyze_delay_causes"


_SPECS = [
    ToolSpec(
        name=KNOWLEDGE_SEARCH_TOOL,
        description=(
            "Search indexed Delta documents, policies, contracts, "
            "reports, and other internal business knowledge."
        ),
        func=run_knowledge_search,
        category="knowledge",
        input_model=KnowledgeSearchArgs,
        output_model=KnowledgeSearchOutput,
        prompt_summary=(
            "\n   Search indexed Delta documents, policies, contracts, reports, and\n"
            "   internal business knowledge using local semantic retrieval."
        ),
        max_attempts=1,
        max_calls_per_run=MAX_KNOWLEDGE_SEARCHES,
    ),
    ToolSpec(
        name=DATA_ANALYSIS_TOOL,
        description=(
            "Analyze July 2026 Delta-marketed domestic flight data "
            "and rank origin airports by cancellation rate."
        ),
        func=run_origin_cancellation_analysis,
        input_model=OriginCancellationAnalysisArgs,
        output_model=OriginCancellationAnalysisOutput,
        prompt_summary=(
            "\n   Analyze cancellation rates from the July 2026 Delta-marketed\n"
            "   domestic flight dataset using deterministic pandas computation."
        ),
        max_attempts=2,
        max_calls_per_run=MAX_DATA_ANALYSIS_CALLS,
    ),
    ToolSpec(
        name=PERFORMANCE_TOOL,
        description=(
            "Rank Delta-marketed July 2026 domestic flights grouped by origin, "
            "destination, route, operating carrier, date or day of week, by "
            "cancellation rate, on-time arrival rate, average arrival or "
            "departure delay, diversion rate or flight count. Can filter by "
            "origin/destination airport or compare specific groups. For origin "
            "airports ranked by cancellation rate, use "
            "analyze_top_origin_cancellation_rates instead."
        ),
        func=rank_flight_performance,
        input_model=FlightPerformanceArgs,
        output_model=FlightPerformanceOutput,
        prompt_summary=(
            "\n   Rank airports, routes, operating carriers, dates or weekdays by\n"
            "   cancellation, on-time, delay or diversion metrics (deterministic\n"
            "   pandas computation)."
        ),
        max_attempts=1,
        max_calls_per_run=2,
        skills=frozenset({"data-analysis", None}),
    ),
    ToolSpec(
        name=DELAY_CAUSES_TOOL,
        description=(
            "Break down July 2026 Delta-marketed domestic flight delays by cause "
            "(carrier, weather, national aviation system, security, late-arriving "
            "aircraft) and cancellations by reason, optionally for one origin, "
            "destination or operating carrier."
        ),
        func=analyze_delay_causes,
        input_model=DelayCausesArgs,
        output_model=DelayCausesOutput,
        prompt_summary=(
            "\n   Break down delay minutes and cancellations by cause, overall or for\n"
            "   one airport or operating carrier (deterministic pandas computation)."
        ),
        max_attempts=1,
        max_calls_per_run=2,
        skills=frozenset({"data-analysis", None}),
    ),
    ToolSpec(
        name=WEB_SEARCH_TOOL,
        description=(
            "Search current official Delta and U.S. government websites "
            "(delta.com, transportation.gov, faa.gov, bts.gov). Use only "
            "after search_private_knowledge when the private documents "
            "do not cover a material part of the question, or when the "
            "user asks whether a document is still current."
        ),
        func=run_official_web_search,
        category="web",
        input_model=OfficialWebSearchArgs,
        output_model=OfficialWebSearchOutput,
        prompt_summary=(
            " (document questions only, when offered)\n"
            "   Search current official Delta and U.S. government websites\n"
            "   (delta.com, transportation.gov, faa.gov, bts.gov)."
        ),
        max_attempts=2,
        max_calls_per_run=MAX_WEB_SEARCHES,
        # Dataset metrics must come from deterministic tools only.
        skills=frozenset({"knowledge-analysis"}),
    ),
    ToolSpec(
        name="issue_customer_credit",
        description="Issue a goodwill credit to a customer account (mock).",
        func=issue_customer_credit,
        category="action",
        input_model=IssueCustomerCreditArgs,
        output_model=IssueCustomerCreditOutput,
        access="write",
        requires_approval=True,
        offered_to_model=False,
    ),
]

TOOL_REGISTRY: Mapping[str, ToolSpec] = {spec.name: spec for spec in _SPECS}


def get_tool_specs_for_skill(
    selected_skill: str | None, registry: Mapping[str, ToolSpec] = TOOL_REGISTRY
) -> list[ToolSpec]:
    """Tools offered to the model for a skill, in registry order."""

    return [spec for spec in registry.values() if spec.is_offered_to(selected_skill)]


def get_tools_for_skill(selected_skill: str | None) -> list[dict]:
    """OpenAI tool definitions offered to the model for a skill."""

    return [spec.openai_tool() for spec in get_tool_specs_for_skill(selected_skill)]
