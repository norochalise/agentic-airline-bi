from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Matches the composer's maxlength; bounds the cost of a single request.
MAX_QUESTION_LENGTH = 2000

# Earlier turns sent with a follow-up question (user + assistant messages).
MAX_HISTORY_MESSAGES = 6
MAX_HISTORY_CHARS = 4000


class HistoryMessage(BaseModel):
    """One earlier turn of the conversation."""

    role: Literal["user", "assistant"]

    content: str = Field(max_length=MAX_HISTORY_CHARS)


class AskRequest(BaseModel):
    """
    Request body for the agent API.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(
        ...,
        min_length=1,
        max_length=MAX_QUESTION_LENGTH,
        description=("Business question to send to the Delta BI agent."),
        examples=[
            (
                "Which 3 origin airports have the "
                "highest cancellation rates among "
                "airports with at least 1000 flights?"
            )
        ],
    )

    history: list[HistoryMessage] = Field(
        default_factory=list,
        max_length=MAX_HISTORY_MESSAGES,
        description="Earlier turns, oldest first, so follow-ups can be resolved.",
    )


class SourceReference(BaseModel):
    """
    Provenance associated with an agent answer.
    """

    source_type: str | None = None

    title: str

    page_number: int | None = None

    url: str | None = None


class ChartRow(BaseModel):
    """One bar: a label, its value and a short supporting detail."""

    label: str

    value: float

    detail: str | None = None


class ChartSpec(BaseModel):
    """A ranked bar chart built from a deterministic data-tool result."""

    title: str

    subtitle: str | None = None

    unit: Literal["percent", "minutes", "flights"]

    label_header: str

    value_header: str

    rows: list[ChartRow]


class AskResponse(BaseModel):
    """
    Structured response returned by the agent API.
    """

    answer: str

    # The question the agent answered: a follow-up arrives rewritten.
    question: str | None = None

    selected_skill: str | None

    stop_reason: str | None

    run_id: str

    step_count: int

    tool_call_count: int

    knowledge_search_count: int

    data_analysis_count: int

    web_search_count: int

    error_count: int

    sources: list[SourceReference] = Field(default_factory=list)

    charts: list[ChartSpec] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    """A reader's rating of one answer."""

    model_config = ConfigDict(str_strip_whitespace=True)

    run_id: str = Field(pattern=r"^[0-9a-f-]{8,64}$")

    rating: Literal["up", "down"]

    comment: str | None = Field(default=None, max_length=500)
