from pydantic import BaseModel, ConfigDict, Field

# Matches the composer's maxlength; bounds the cost of a single request.
MAX_QUESTION_LENGTH = 2000


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


class SourceReference(BaseModel):
    """
    Provenance associated with an agent answer.
    """

    source_type: str | None = None

    title: str

    page_number: int | None = None

    url: str | None = None


class AskResponse(BaseModel):
    """
    Structured response returned by the agent API.
    """

    answer: str

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
