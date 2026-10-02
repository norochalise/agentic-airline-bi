import pytest

import agentic_bi.tools.registry as registry
from agentic_bi.config import ConfigError
from agentic_bi.core.prompts import build_agent_instructions
from agentic_bi.tools.registry import (
    TOOL_REGISTRY,
    get_tool_specs_for_skill,
    get_tools_for_skill,
)


def names(specs):
    return [spec.name for spec in specs]


def test_tools_offered_per_skill():
    assert names(get_tool_specs_for_skill("knowledge-analysis")) == [
        "search_private_knowledge",
        "analyze_top_origin_cancellation_rates",
        "search_official_web",
    ]
    assert names(get_tool_specs_for_skill("data-analysis")) == [
        "search_private_knowledge",
        "analyze_top_origin_cancellation_rates",
    ]


def test_write_action_is_registered_but_never_offered():
    spec = TOOL_REGISTRY["issue_customer_credit"]

    assert spec.access == "write"
    assert spec.requires_approval

    for skill in ("knowledge-analysis", "data-analysis", None):
        assert "issue_customer_credit" not in names(get_tool_specs_for_skill(skill))


def test_generated_tool_json_is_openai_strict():
    for tool in get_tools_for_skill("knowledge-analysis"):
        parameters = tool["parameters"]

        assert tool["strict"] is True
        assert parameters["additionalProperties"] is False
        assert parameters["required"] == list(parameters["properties"])

        for field_schema in parameters["properties"].values():
            assert "title" not in field_schema
            assert field_schema["description"]


def test_generated_tool_json_matches_the_previous_hand_written_schema():
    tools = {tool["name"]: tool for tool in get_tools_for_skill("knowledge-analysis")}

    assert tools["analyze_top_origin_cancellation_rates"]["parameters"] == {
        "type": "object",
        "properties": {
            "min_flights": {
                "type": "integer",
                "description": (
                    "Minimum number of flights required for an airport to be "
                    "included in the analysis."
                ),
            },
            "top_n": {
                "type": "integer",
                "description": (
                    "Number of highest cancellation-rate airports to return."
                ),
            },
        },
        "required": ["min_flights", "top_n"],
        "additionalProperties": False,
    }


def test_prompt_capability_list_comes_from_the_registry():
    prompt = build_agent_instructions("knowledge-analysis", "")

    assert "1. search_private_knowledge\n   Search indexed" in prompt
    assert "2. analyze_top_origin_cancellation_rates\n" in prompt
    assert "3. search_official_web (document questions only, when offered)" in prompt
    assert "issue_customer_credit" not in prompt


@pytest.fixture
def transport_spies(monkeypatch):
    calls = []

    def in_process(**kwargs):
        calls.append(("inprocess", kwargs))
        return {}

    def via_mcp(**kwargs):
        calls.append(("mcp", kwargs))
        return {}

    monkeypatch.setattr(registry, "analyze_top_origin_cancellation_rates", in_process)
    monkeypatch.setattr(
        registry, "analyze_top_origin_cancellation_rates_via_mcp", via_mcp
    )

    return calls


def test_flight_analysis_runs_in_process_by_default(monkeypatch, transport_spies):
    monkeypatch.delenv("TOOL_TRANSPORT", raising=False)

    registry.run_origin_cancellation_analysis(min_flights=1000, top_n=3)

    assert transport_spies == [("inprocess", {"min_flights": 1000, "top_n": 3})]


def test_flight_analysis_can_use_mcp(monkeypatch, transport_spies):
    monkeypatch.setenv("TOOL_TRANSPORT", "MCP")

    registry.run_origin_cancellation_analysis(min_flights=1000, top_n=3)

    assert transport_spies == [("mcp", {"min_flights": 1000, "top_n": 3})]


def test_unknown_transport_is_a_config_error(monkeypatch, transport_spies):
    monkeypatch.setenv("TOOL_TRANSPORT", "grpc")

    with pytest.raises(ConfigError, match="TOOL_TRANSPORT"):
        registry.run_origin_cancellation_analysis(min_flights=1000, top_n=3)


def test_in_process_analysis_returns_valid_output():
    spec = TOOL_REGISTRY["analyze_top_origin_cancellation_rates"]

    result = spec.func(min_flights=1000, top_n=3)

    output = spec.output_model.model_validate(result)

    assert len(output.results) == 3
    rates = [row.cancellation_rate for row in output.results]
    assert rates == sorted(rates, reverse=True)
