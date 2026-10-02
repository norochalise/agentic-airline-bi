from pydantic import BaseModel, ConfigDict, Field


# -------------------------------------------------------------------
# Tool input schemas
# -------------------------------------------------------------------

class KnowledgeSearchArgs(BaseModel):
    """
    Validated arguments for local knowledge retrieval.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    query: str = Field(
        min_length=3,
        description="Focused semantic query for the local knowledge base.",
    )


class OriginCancellationAnalysisArgs(BaseModel):
    """
    Validated arguments for origin-airport cancellation analysis.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    min_flights: int = Field(
        ge=1,
        description="Minimum flight volume required for inclusion.",
    )

    top_n: int = Field(
        ge=1,
        le=50,
        description="Maximum number of ranked airports to return.",
    )


# -------------------------------------------------------------------
# Knowledge-search output schemas
# -------------------------------------------------------------------

class KnowledgeSearchResult(BaseModel):
    """
    One retrieved knowledge chunk with source metadata.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    source: str = Field(
        min_length=1,
    )

    page_number: int | None = Field(
        default=None,
        ge=1,
    )

    chunk_id: str = Field(
        min_length=1,
    )

    score: float = Field(
        ge=-1.0,
        le=1.0,
    )

    text: str = Field(
        min_length=1,
    )


class KnowledgeSearchOutput(BaseModel):
    """
    Validated output returned by the knowledge-search tool.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    query: str = Field(
        min_length=3,
    )

    results: list[KnowledgeSearchResult]


# -------------------------------------------------------------------
# Flight-analysis output schemas
# -------------------------------------------------------------------

class OriginCancellationResult(BaseModel):
    """
    One airport-level cancellation-rate result.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    Origin: str = Field(
        min_length=3,
        max_length=3,
    )

    total_flights: int = Field(
        ge=0,
    )

    cancelled_flights: float = Field(
        ge=0,
    )

    cancellation_rate: float = Field(
        ge=0,
        le=100,
    )


class OriginCancellationAnalysisOutput(BaseModel):
    """
    Validated output returned by the cancellation-analysis tool.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    dataset: str = Field(
        min_length=1,
    )

    minimum_flights: int = Field(
        ge=1,
    )

    top_n: int = Field(
        ge=1,
        le=50,
    )

    results: list[OriginCancellationResult]

# -------------------------------------------------------------------
# Official-web search schemas
# -------------------------------------------------------------------

class OfficialWebSearchArgs(BaseModel):
    """
    Validated arguments for official live-web search.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    query: str = Field(
        min_length=3,
        description="Focused query for official Delta and U.S. government sites.",
    )


class OfficialWebSearchResult(BaseModel):
    """
    One page returned from an allowed official domain.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    title: str = Field(
        min_length=1,
    )

    url: str = Field(
        min_length=1,
    )

    highlights: list[str]


class OfficialWebSearchOutput(BaseModel):
    """
    Validated output returned by the official-web search tool.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    query: str = Field(
        min_length=3,
    )

    results: list[OfficialWebSearchResult]
