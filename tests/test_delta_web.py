"""Regression tests for M23 trusted Delta web retrieval."""

from types import SimpleNamespace

import pytest

from agentic_bi.tools.delta_current_info import answer_current_delta_question
from agentic_bi.tools.delta_official_web import (
    _is_allowed_delta_url,
    search_delta_official_web,
)
from conftest import FakeClient, routed_to

# -------------------------------------------------------------------
# Domain validation
# -------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://delta.com/us/en/baggage/overview",
        "https://www.delta.com/us/en/baggage/overview",
        "https://news.delta.com/example",
        "https://www.transportation.gov/airconsumer/refunds",
        "https://www.faa.gov/travelers",
        "https://www.bts.gov/topics/airlines-and-airports",
    ],
)
def test_allowed_delta_urls_are_accepted(url):
    assert _is_allowed_delta_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/delta",
        "https://delta.com.example.com/fake",
        "https://notdelta.com/",
        "https://google.com/",
        "https://transportation.gov.evil.com/refunds",
        "https://faketransportation.gov/",
        "https://faa.gov.example.com/",
    ],
)
def test_non_delta_urls_are_rejected(url):
    assert _is_allowed_delta_url(url) is False


# -------------------------------------------------------------------
# Fake Exa objects
# -------------------------------------------------------------------


class FakeExaResult:
    """Minimal Exa search-result object."""

    def __init__(self, title, url, highlights=None):
        self.title = title
        self.url = url
        self.highlights = highlights or []


class FakeExaResponse:
    """Minimal Exa response object."""

    def __init__(self, results):
        self.results = results


class FakeExa:
    """Fake Exa client that records search parameters."""

    last_instance = None

    def __init__(self, api_key):
        self.api_key = api_key
        self.last_query = None
        self.last_kwargs = None

        FakeExa.last_instance = self

    def search_and_contents(self, query, **kwargs):
        self.last_query = query
        self.last_kwargs = kwargs

        return FakeExaResponse(
            [
                FakeExaResult(
                    title="Baggage Policy and Fees | Delta Air Lines",
                    url="https://www.delta.com/us/en/baggage/overview",
                    highlights=[
                        "First checked bag fee is $45.",
                        "Second checked bag fee is $55.",
                    ],
                ),
                FakeExaResult(
                    title="Fake Result",
                    url="https://example.com/not-allowed",
                    highlights=["This result must never be exposed."],
                ),
            ]
        )


def test_search_delta_official_web_filters_non_delta_results(monkeypatch):
    import agentic_bi.tools.delta_official_web as web_module

    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")

    monkeypatch.setattr(web_module, "Exa", FakeExa)

    result = search_delta_official_web(
        "What is Delta's current baggage policy?", num_results=3
    )

    assert result["provider"] == "exa"
    assert result["source_type"] == "live_official_web"

    assert result["result_count"] == 1

    assert len(result["results"]) == 1

    returned = result["results"][0]

    assert returned["url"] == "https://www.delta.com/us/en/baggage/overview"

    assert returned["title"] == ("Baggage Policy and Fees | Delta Air Lines")

    assert returned["highlights"] == [
        "First checked bag fee is $45.",
        "Second checked bag fee is $55.",
    ]

    exa = FakeExa.last_instance

    assert exa is not None
    assert exa.api_key == "test-exa-key"

    assert exa.last_query == "What is Delta's current baggage policy?"

    assert exa.last_kwargs["num_results"] == 3

    assert exa.last_kwargs["include_domains"] == [
        "delta.com",
        "transportation.gov",
        "faa.gov",
        "bts.gov",
    ]

    assert exa.last_kwargs["highlights"] is True


def test_search_delta_official_web_rejects_empty_query(monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")

    with pytest.raises(ValueError, match="must not be empty"):
        search_delta_official_web("   ")


def test_search_delta_official_web_requires_exa_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="EXA_API_KEY"):
        search_delta_official_web("Current Delta baggage policy")


# -------------------------------------------------------------------
# Current-info synthesis
# -------------------------------------------------------------------


class FakeResponses:
    """Fake Responses API used only for evidence synthesis."""

    def __init__(self):
        self.last_request = None

    def create(self, **kwargs):
        self.last_request = kwargs

        return SimpleNamespace(
            output_text=(
                "Delta's current official baggage information "
                "shows a $45 first checked-bag fee."
            )
        )


class FakeModelClient:
    """Minimal client exposing responses.create()."""

    def __init__(self):
        self.responses = FakeResponses()


def test_current_info_uses_retrieved_evidence_and_preserves_sources(monkeypatch):
    import agentic_bi.tools.delta_current_info as current_module

    fake_search_result = {
        "query": "Current baggage policy",
        "source_type": "live_official_web",
        "provider": "exa",
        "result_count": 1,
        "results": [
            {
                "title": ("Baggage Policy and Fees | Delta Air Lines"),
                "url": ("https://www.delta.com/us/en/baggage/overview"),
                "highlights": [
                    "The first checked bag costs $45.",
                    "The second checked bag costs $55.",
                ],
            }
        ],
    }

    monkeypatch.setattr(
        current_module,
        "search_delta_official_web",
        lambda query, num_results=3: fake_search_result,
    )

    monkeypatch.setenv("OPENAI_MODEL", "test-model")

    client = FakeModelClient()

    result = answer_current_delta_question(
        "What is Delta's current baggage policy?", client=client
    )

    assert "$45" in result["answer"]

    assert result["source_type"] == "live_official_web"
    assert result["provider"] == "exa"

    assert result["sources"] == [
        {
            "source_type": "live_official_web",
            "title": ("Baggage Policy and Fees | Delta Air Lines"),
            "url": ("https://www.delta.com/us/en/baggage/overview"),
        }
    ]

    request = client.responses.last_request

    assert request is not None
    assert request["model"] == "test-model"

    assert "The first checked bag costs $45." in request["input"]

    assert "The second checked bag costs $55." in request["input"]

    assert "https://www.delta.com/us/en/baggage/overview" in request["input"]


def test_current_info_returns_safe_fallback_when_no_results(monkeypatch):
    import agentic_bi.tools.delta_current_info as current_module

    monkeypatch.setattr(
        current_module,
        "search_delta_official_web",
        lambda query, num_results=3: {
            "query": query,
            "source_type": "live_official_web",
            "provider": "exa",
            "result_count": 0,
            "results": [],
        },
    )

    result = answer_current_delta_question("What is Delta's latest unknown policy?")

    assert result["answer"] == (
        "I could not verify this from current official "
        "Delta or U.S. government websites."
    )

    assert result["sources"] == []
    assert result["source_type"] == "live_official_web"
    assert result["provider"] == "exa"


# -------------------------------------------------------------------
# Agent integration
# -------------------------------------------------------------------


def test_current_info_exits_before_normal_skill_router(monkeypatch, run_store):
    import agentic_bi.core.agent as agent_module

    monkeypatch.setattr(
        agent_module, "classify_interaction", routed_to("current_airline_info")
    )

    monkeypatch.setattr(
        agent_module,
        "answer_current_delta_question",
        lambda question, client=None: {
            "answer": ("Current official Delta baggage information."),
            "sources": [
                {
                    "title": "Delta baggage policy",
                    "url": ("https://www.delta.com/us/en/baggage/overview"),
                }
            ],
            "source_type": "live_official_web",
            "provider": "exa",
        },
    )

    def fail_if_skill_router_runs(*args, **kwargs):
        raise AssertionError("Skill router must not run for current_airline_info.")

    monkeypatch.setattr(agent_module, "select_skill", fail_if_skill_router_runs)

    result = agent_module.run_agent(
        "What is Delta's current baggage policy?", client=FakeClient(), store=run_store
    )

    assert result.final_answer == "Current official Delta baggage information."

    assert result.selected_skill is None
    assert result.stop_reason == "current_airline_info"
    assert result.web_search_count == 1
    assert result.sources[0]["url"] == "https://www.delta.com/us/en/baggage/overview"

    assert result.step_count == 0
    assert result.tool_call_count == 0
    assert result.knowledge_search_count == 0
    assert result.data_analysis_count == 0

    assert result.tool_history == []
    assert result.observations == []
    assert result.errors == []
