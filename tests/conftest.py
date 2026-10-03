"""Shared fakes for agent tests. No test here calls a paid API."""

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from agentic_bi.core.interaction import InteractionDecision
from agentic_bi.core.run_store import MemoryRunStore
from agentic_bi.tools.registry import TOOL_REGISTRY


def function_call(name, arguments, call_id):
    """A function_call item as returned by the Responses API."""

    return SimpleNamespace(
        type="function_call",
        name=name,
        arguments=arguments if isinstance(arguments, str) else json.dumps(arguments),
        call_id=call_id,
    )


def model_response(response_id, output=None, output_text="", usage=None):
    """A Responses API response with optional function calls and usage."""

    return SimpleNamespace(
        id=response_id, output=output or [], output_text=output_text, usage=usage
    )


def token_usage(input_tokens, output_tokens, cached_tokens=0):
    """A Responses API `usage` object."""

    return SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_tokens_details=SimpleNamespace(cached_tokens=cached_tokens),
    )


class FakeResponses:
    """Return scripted responses and record every request."""

    def __init__(self, scripted):
        self.scripted = list(scripted)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.scripted.pop(0)


class FakeClient:
    """Stands in for the OpenAI client inside run_agent."""

    def __init__(self, scripted=()):
        self.responses = FakeResponses(scripted)


def tools_with(**funcs):
    """The real tool registry with some tool functions replaced."""

    return {
        name: replace(spec, func=funcs[name]) if name in funcs else spec
        for name, spec in TOOL_REGISTRY.items()
    }


def routed_to(intent):
    """A classify_interaction replacement that always returns `intent`."""

    def classify(question, client=None):
        return InteractionDecision(intent=intent, reason="Test routing.")

    return classify


@pytest.fixture
def run_store():
    return MemoryRunStore()


@pytest.fixture(autouse=True)
def _test_model(monkeypatch):
    # openai_model() must resolve, but no test reaches the real API.
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    # API tests post many questions from one client; rate-limit tests opt in.
    monkeypatch.setenv("ASK_RATE_LIMIT", "0")
    # Cost estimates only when a test sets prices, whatever .env says.
    for name in (
        "OPENAI_INPUT_PRICE_PER_M",
        "OPENAI_CACHED_INPUT_PRICE_PER_M",
        "OPENAI_OUTPUT_PRICE_PER_M",
    ):
        monkeypatch.delenv(name, raising=False)
