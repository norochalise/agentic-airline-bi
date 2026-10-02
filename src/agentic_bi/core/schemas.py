from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# -------------------------------------------------------------------
# Tool input schemas
# -------------------------------------------------------------------


class KnowledgeSearchArgs(BaseModel):
    """
    Validated arguments for local knowledge retrieval.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(
        min_length=3,
        description=(
            "Focused semantic retrieval query describing the evidence required."
        ),
    )


class OriginCancellationAnalysisArgs(BaseModel):
    """
    Validated arguments for origin-airport cancellation analysis.
    """

    model_config = ConfigDict(extra="forbid")

    min_flights: int = Field(
        ge=1,
        description=(
            "Minimum number of flights required for an airport to be included "
            "in the analysis."
        ),
    )

    top_n: int = Field(
        ge=1,
        le=50,
        description="Number of highest cancellation-rate airports to return.",
    )


# -------------------------------------------------------------------
# Knowledge-search output schemas
# -------------------------------------------------------------------


class KnowledgeSearchResult(BaseModel):
    """
    One retrieved knowledge chunk with source metadata.
    """

    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1)

    page_number: int | None = Field(default=None, ge=1)

    chunk_id: str = Field(min_length=1)

    # "reranked" chunks are primary evidence; "neighbor_previous" and
    # "neighbor_next" are surrounding context added after reranking.
    retrieval_type: Literal["reranked", "neighbor_previous", "neighbor_next"]

    # FAISS cosine similarity; None for neighbor chunks, which were not
    # retrieved by similarity.
    score: float | None = Field(default=None, ge=-1.0, le=1.0)

    # Cross-encoder relevance (higher is better); None for neighbor chunks.
    rerank_score: float | None = None

    text: str = Field(min_length=1)


class KnowledgeSearchOutput(BaseModel):
    """
    Validated output returned by the knowledge-search tool.
    """

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=3)

    results: list[KnowledgeSearchResult]


# -------------------------------------------------------------------
# Flight-analysis output schemas
# -------------------------------------------------------------------


class OriginCancellationResult(BaseModel):
    """
    One airport-level cancellation-rate result.
    """

    model_config = ConfigDict(extra="forbid")

    Origin: str = Field(min_length=3, max_length=3)

    total_flights: int = Field(ge=0)

    cancelled_flights: float = Field(ge=0)

    cancellation_rate: float = Field(ge=0, le=100)


class OriginCancellationAnalysisOutput(BaseModel):
    """
    Validated output returned by the cancellation-analysis tool.
    """

    model_config = ConfigDict(extra="forbid")

    dataset: str = Field(min_length=1)

    minimum_flights: int = Field(ge=1)

    top_n: int = Field(ge=1, le=50)

    results: list[OriginCancellationResult]


# -------------------------------------------------------------------
# Official-web search schemas
# -------------------------------------------------------------------


class OfficialWebSearchArgs(BaseModel):
    """
    Validated arguments for official live-web search.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(
        min_length=3,
        description=(
            "Focused plain-language query describing the official information required."
        ),
    )


class OfficialWebSearchResult(BaseModel):
    """
    One page returned from an allowed official domain.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)

    url: str = Field(min_length=1)

    highlights: list[str]


class OfficialWebSearchOutput(BaseModel):
    """
    Validated output returned by the official-web search tool.
    """

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=3)

    results: list[OfficialWebSearchResult]


# -------------------------------------------------------------------
# Customer-credit write action (mock, approval required)
# -------------------------------------------------------------------


class IssueCustomerCreditArgs(BaseModel):
    """
    Validated arguments for the mock customer-credit write action.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    customer_id: str = Field(min_length=1, description="Customer identifier.")

    amount: float = Field(gt=0, description="Credit amount in US dollars.")

    reason: str = Field(min_length=1, description="Reason for the credit.")

    idempotency_key: str = Field(
        min_length=1, description="Key that makes repeated requests safe."
    )


class IssueCustomerCreditOutput(BaseModel):
    """
    Result of the mock customer-credit write action.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "duplicate_blocked"]

    customer_id: str

    amount: float

    reason: str | None = None

    idempotency_key: str
