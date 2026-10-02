"""Tests for the M22 interaction-routing layer."""

import json
from types import SimpleNamespace

import pytest

from agentic_bi.core.interaction import (
    InteractionDecision,
    classify_interaction,
)
from agentic_bi.core.interaction_response import (
    build_interaction_response,
)


class FakeResponses:
    """Minimal fake for the Responses API used by the classifier."""

    def __init__(self, intent: str, reason: str):
        self.intent = intent
        self.reason = reason
        self.last_request = None

    def create(self, **kwargs):
        self.last_request = kwargs

        return SimpleNamespace(
            output_text=json.dumps(
                {
                    "intent": self.intent,
                    "reason": self.reason,
                }
            )
        )


class FakeClient:
    """Minimal client exposing responses.create()."""

    def __init__(self, intent: str, reason: str):
        self.responses = FakeResponses(
            intent=intent,
            reason=reason,
        )


@pytest.mark.parametrize(
    ("intent", "question"),
    [
        (
            "conversation",
            "Hello, how are you?",
        ),
        (
            "app_info",
            "Who built you?",
        ),
        (
            "airline_data",
            "Which origin airport has the highest cancellation rate?",
        ),
        (
            "airline_knowledge",
            "What does the contract say about refunds?",
        ),
        (
            "current_airline_info",
            "What is Delta's current baggage policy?",
        ),
        (
            "out_of_scope",
            "Write me a poem about Delta flights.",
        ),
    ],
)
def test_classify_interaction_returns_structured_intent(
    monkeypatch,
    intent,
    question,
):
    monkeypatch.setenv(
        "OPENAI_MODEL",
        "test-model",
    )

    client = FakeClient(
        intent=intent,
        reason="Test classification.",
    )

    result = classify_interaction(
        question,
        client=client,
    )

    assert isinstance(
        result,
        InteractionDecision,
    )

    assert result.intent == intent
    assert result.reason == "Test classification."

    request = client.responses.last_request

    assert request["model"] == "test-model"
    assert request["input"] == question

    assert (
        request["text"]["format"]["type"]
        == "json_schema"
    )

    assert (
        request["text"]["format"]["strict"]
        is True
    )


def test_conversation_gets_bounded_response():
    response = build_interaction_response(
        intent="conversation",
        question="Hello",
    )

    assert response is not None

    assert (
        "Airline Intelligence Assistant"
        in response
    )


def test_app_info_identifies_project_builder():
    response = build_interaction_response(
        intent="app_info",
        question="Who built you?",
    )

    assert response is not None
    assert "Noro Insight" in response
    assert "Agentic Business Intelligence" in response


def test_app_info_can_describe_capabilities():
    response = build_interaction_response(
        intent="app_info",
        question="What can you do?",
    )

    assert response is not None

    assert "flight dataset" in response
    assert "document knowledge base" in response


def test_app_info_can_describe_architecture():
    response = build_interaction_response(
        intent="app_info",
        question="How were you built?",
    )

    assert response is not None

    assert "skill routing" in response
    assert "RAG" in response
    assert "FAISS" in response


def test_app_info_architecture_needs_whole_word_match():
    # "average" contains "rag"; it must not trigger the architecture reply.
    response = build_interaction_response(
        intent="app_info",
        question="What is your average response quality?",
    )

    assert response is not None

    assert "FAISS" not in response


def test_out_of_scope_gets_bounded_response():
    response = build_interaction_response(
        intent="out_of_scope",
        question="Write me a poem.",
    )

    assert response is not None

    assert "business-intelligence" in response


def test_current_info_continues_to_live_web_path():
    response = build_interaction_response(
        intent="current_airline_info",
        question="What is Delta's current baggage policy?",
    )

    assert response is None


@pytest.mark.parametrize(
    "intent",
    [
        "airline_data",
        "airline_knowledge",
    ],
)
def test_domain_intents_continue_to_main_agent(
    intent,
):
    response = build_interaction_response(
        intent=intent,
        question="Example domain question",
    )

    assert response is None