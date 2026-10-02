"""Regression tests for the official-web fallback inside the agent loop."""

from functools import partial

import pytest

from agentic_bi.tools.registry import get_tools_for_skill
from conftest import FakeClient, function_call, model_response, routed_to, tools_with

PRIVATE_RESULT = {
    "query": "refund rules",
    "results": [
        {
            "source": "delta_domestic_contract_plain_language_2026-08-18.pdf",
            "page_number": 15,
            "chunk_id": "contract:p15:c0",
            "retrieval_type": "reranked",
            "score": 0.61,
            "rerank_score": 4.2,
            "text": "Refunds are issued to the original form of payment.",
        }
    ],
}

WEB_RESULT = {
    "query": "DOT automatic refund rule",
    "results": [
        {
            "title": "Refunds | US Department of Transportation",
            "url": "https://www.transportation.gov/airconsumer/refunds",
            "highlights": ["Airlines must provide automatic refunds."],
        }
    ],
}


@pytest.fixture
def agent_env(monkeypatch, run_store):
    """Fake tools and model; returns (agent module, call counts, setup)."""

    import agentic_bi.core.agent as agent_module

    calls = {"web": 0, "knowledge": 0}

    def fake_knowledge(query):
        calls["knowledge"] += 1
        return PRIVATE_RESULT

    def fake_web(query):
        calls["web"] += 1
        return WEB_RESULT

    tools = tools_with(
        search_private_knowledge=fake_knowledge, search_official_web=fake_web
    )

    def setup(skill, scripted):
        """Script the model and return (fake client, ask function)."""

        client = FakeClient(scripted)

        intent = (
            "airline_knowledge" if skill == "knowledge-analysis" else "airline_data"
        )

        monkeypatch.setattr(agent_module, "classify_interaction", routed_to(intent))
        monkeypatch.setattr(agent_module, "select_skill", lambda goal: skill)

        ask = partial(
            agent_module.run_agent, client=client, store=run_store, tools=tools
        )

        return client, ask

    return agent_module, calls, setup


# -------------------------------------------------------------------
# Tool exposure
# -------------------------------------------------------------------


def tool_names(tools):
    return {tool["name"] for tool in tools}


def test_only_knowledge_analysis_is_offered_web_search():
    assert "search_official_web" in tool_names(
        get_tools_for_skill("knowledge-analysis")
    )
    assert "search_official_web" not in tool_names(get_tools_for_skill("data-analysis"))
    assert "search_official_web" not in tool_names(get_tools_for_skill(None))


# -------------------------------------------------------------------
# Agent loop
# -------------------------------------------------------------------


def test_web_search_is_blocked_before_private_search(agent_env):
    agent_module, calls, setup = agent_env

    _, ask = setup(
        "knowledge-analysis",
        [
            model_response(
                "r1",
                [function_call("search_official_web", {"query": "refund rules"}, "c1")],
            ),
            model_response("r2", output_text="Answer without web."),
        ],
    )

    result = ask("What are the refund rules?")

    assert calls["web"] == 0
    assert result.web_search_count == 0
    assert result.stop_reason == "final_answer"
    assert result.final_answer == "Answer without web."
    assert [error["error_type"] for error in result.errors] == [
        "web_before_private_search"
    ]


def test_web_fallback_runs_after_private_search(agent_env):
    agent_module, calls, setup = agent_env

    client, ask = setup(
        "knowledge-analysis",
        [
            model_response(
                "r1",
                [
                    function_call(
                        "search_private_knowledge", {"query": "refund rules"}, "c1"
                    )
                ],
            ),
            model_response(
                "r2",
                [
                    function_call(
                        "search_official_web",
                        {"query": "DOT automatic refund rule"},
                        "c2",
                    )
                ],
            ),
            model_response("r3", output_text="Combined answer."),
        ],
    )

    result = ask("Does the contract still describe refunds the same way today?")

    assert calls == {"knowledge": 1, "web": 1}
    assert result.knowledge_search_count == 1
    assert result.web_search_count == 1
    assert result.stop_reason == "final_answer"
    assert result.final_answer == "Combined answer."
    assert result.errors == []

    # The web budget is spent, so the final call is forced synthesis.
    assert "tools" not in client.responses.requests[-1]

    source_types = [source["source_type"] for source in result.sources]
    assert source_types == ["private_document", "live_official_web"]
    assert result.sources[1]["url"] == (
        "https://www.transportation.gov/airconsumer/refunds"
    )


def test_data_analysis_cannot_call_web_search(agent_env):
    agent_module, calls, setup = agent_env

    client, ask = setup(
        "data-analysis",
        [
            model_response(
                "r1",
                [
                    function_call(
                        "search_official_web", {"query": "cancellations"}, "c1"
                    )
                ],
            )
        ],
    )

    result = ask("Which airport has the highest cancellation rate?")

    assert calls["web"] == 0
    assert result.stop_reason == "blocked_unknown_tool"
    assert "search_official_web" not in tool_names(
        client.responses.requests[0]["tools"]
    )


def test_interaction_intent_selects_skill_without_keyword_router(
    agent_env, monkeypatch
):
    agent_module, calls, setup = agent_env

    client, ask = setup(
        "knowledge-analysis",
        [model_response("r1", output_text="Not found in the documents.")],
    )

    def fail_if_keyword_router_runs(goal):
        raise AssertionError("Keyword router must not override a mapped intent.")

    monkeypatch.setattr(agent_module, "select_skill", fail_if_keyword_router_runs)

    # No routing keywords: the old keyword router returned None here.
    result = ask("when delta company found")

    assert result.selected_skill == "knowledge-analysis"
    assert "search_official_web" in tool_names(client.responses.requests[0]["tools"])
