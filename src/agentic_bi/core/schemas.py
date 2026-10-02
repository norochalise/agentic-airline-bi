from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


# -------------------------------------------------------------------
# Flight-performance ranking
# -------------------------------------------------------------------

FlightMetric = Literal[
    "cancellation_rate",
    "on_time_arrival_rate",
    "avg_arrival_delay_minutes",
    "avg_departure_delay_minutes",
    "diversion_rate",
    "flight_count",
]

FlightGroupBy = Literal[
    "origin", "destination", "route", "operating_carrier", "flight_date", "day_of_week"
]

# Group keys whose values are airport or carrier codes.
_CODE_GROUPS = {"origin", "destination", "route", "operating_carrier"}


def _upper_code(value: str | None) -> str | None:
    return value.strip().upper() if value else None


class FlightPerformanceArgs(BaseModel):
    """
    Validated arguments for ranking groups of flights by a metric.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    metric: FlightMetric = Field(
        description=(
            "Metric to rank by. on_time_arrival_rate follows the DOT definition "
            "(arrived under 15 minutes late; cancelled and diverted flights "
            "count as not on time)."
        )
    )

    group_by: FlightGroupBy = Field(
        description=(
            "What to compare: origin or destination airport, route "
            "(ORIGIN-DEST), operating_carrier, flight_date or day_of_week."
        )
    )

    order: Literal["highest", "lowest", "calendar"] = Field(
        description=(
            "highest or lowest metric first; calendar orders flight_date or "
            "day_of_week chronologically."
        )
    )

    top_n: int = Field(ge=1, le=50, description="Number of groups to return.")

    min_flights: int = Field(
        ge=1,
        description=(
            "Minimum scheduled flights for a group to be included. Use 1 unless "
            "the user gives a threshold or small groups would distort a rate."
        ),
    )

    origin: str | None = Field(
        description="Only flights departing this IATA airport code; null for all."
    )

    destination: str | None = Field(
        description="Only flights arriving at this IATA airport code; null for all."
    )

    only: list[str] | None = Field(
        description=(
            "Keep only these group values, to compare them directly (for "
            "example ['JFK', 'LGA'], ['ATL-LGA'] or ['Monday']); null for all."
        )
    )

    @field_validator("origin", "destination")
    @classmethod
    def _codes_upper(cls, value: str | None) -> str | None:
        return _upper_code(value)

    @model_validator(mode="after")
    def _check_combination(self) -> "FlightPerformanceArgs":
        if self.order == "calendar" and self.group_by not in (
            "flight_date",
            "day_of_week",
        ):
            raise ValueError(
                "order='calendar' needs group_by flight_date or day_of_week"
            )

        if self.only and self.group_by in _CODE_GROUPS:
            self.only = [value.strip().upper() for value in self.only]

        return self


class FlightPerformanceRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group: str = Field(min_length=1)

    flights: int = Field(ge=0)

    value: float


class FlightPerformanceOutput(BaseModel):
    """
    Validated output of the flight-performance ranking tool.
    """

    model_config = ConfigDict(extra="forbid")

    dataset: str = Field(min_length=1)

    metric: FlightMetric

    unit: Literal["percent", "minutes", "flights"]

    group_by: FlightGroupBy

    order: Literal["highest", "lowest", "calendar"]

    filters: dict[str, str | list[str] | None]

    minimum_flights: int = Field(ge=1)

    results: list[FlightPerformanceRow]


# -------------------------------------------------------------------
# Delay-cause breakdown
# -------------------------------------------------------------------


class DelayCausesArgs(BaseModel):
    """
    Validated arguments for the delay-cause breakdown.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    origin: str | None = Field(
        description="Only flights departing this IATA airport code; null for all."
    )

    destination: str | None = Field(
        description="Only flights arriving at this IATA airport code; null for all."
    )

    operating_carrier: str | None = Field(
        description=(
            "Only flights operated by this carrier code (DL, OO, 9E, YX); null for all."
        )
    )

    @field_validator("origin", "destination", "operating_carrier")
    @classmethod
    def _codes_upper(cls, value: str | None) -> str | None:
        return _upper_code(value)


class DelayCauseShare(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cause: str

    minutes: float = Field(ge=0)

    share_percent: float = Field(ge=0, le=100)


class CancellationReasonShare(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str

    flights: int = Field(ge=0)

    share_percent: float = Field(ge=0, le=100)


class DelayCausesOutput(BaseModel):
    """
    Validated output of the delay-cause breakdown tool.
    """

    model_config = ConfigDict(extra="forbid")

    dataset: str = Field(min_length=1)

    filters: dict[str, str | None]

    flights: int = Field(ge=0)

    delayed_flights_with_causes: int = Field(ge=0)

    delay_causes: list[DelayCauseShare]

    cancelled_flights: int = Field(ge=0)

    cancellation_reasons: list[CancellationReasonShare]
