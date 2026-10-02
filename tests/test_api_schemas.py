import pytest
from pydantic import ValidationError

from agentic_bi.api.schemas import AskRequest


def test_ask_request_accepts_valid_question():
    request = AskRequest(
        question="Which airports have the highest cancellation rates?"
    )

    assert request.question == (
        "Which airports have the highest cancellation rates?"
    )


def test_ask_request_rejects_empty_question():
    with pytest.raises(ValidationError):
        AskRequest(question="")


def test_ask_request_requires_question():
    with pytest.raises(ValidationError):
        AskRequest()