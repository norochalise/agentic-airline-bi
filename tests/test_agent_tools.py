"""Tool execution and controller guards inside run_agent."""

from dataclasses import replace

import pytest

import agentic_bi.core.agent as agent_module
from agentic_bi.core.action_guard import ApprovalRequiredError
from agentic_bi.core.agent import ToolCallError, execute_tool, parse_arguments
from agentic_bi.core.reliability import TransientToolError
from agentic_bi.tools.registry import TOOL_REGISTRY
from conftest import FakeClient, function_call, model_response, routed_to, tools_with

DATA_TOOL = TOOL_REGISTRY["analyze_top_origin_cancellation_rates"]

DATA_RESULT = {
    "dataset": "Delta-marketed domestic flights, July 2026",
    "minimum_flights": 1000,
    "top_n": 1,
    "results": [
        {
            "Origin": "LGA",
            "total_flights": 7378,
            "cancelled_flights": 843.0,
            "cancellation_rate": 11.43,
        }
    ],
}


# -------------------------------------------------------------------
# parse_arguments / execute_tool
# -------------------------------------------------------------------


def test_invalid_json_arguments_are_reported_to_the_model():
    with pytest.raises(ToolCallError) as error:
        parse_arguments(DATA_TOOL, "{not json")

    assert error.value.error_type == "argument_parse_error"


def test_arguments_are_validated_against_the_spec():
    with pytest.raises(ToolCallError) as error:
        parse_arguments(DATA_TOOL, '{"min_flights": 0, "top_n": 3}')

    assert error.value.error_type == "input_validation_error"
    assert error.value.details


def test_output_breaking_the_contract_is_rejected():
    spec = replace(DATA_TOOL, func=lambda **kwargs: {"unexpected": True})

    with pytest.raises(ToolCallError) as error:
        execute_tool(spec, {"min_flights": 1000, "top_n": 1})

    assert error.value.error_type == "output_validation_error"


def test_transient_failures_are_retried_up_to_the_spec_limit():
    attempts = []

    def flaky(**kwargs):
        attempts.append(kwargs)
        if len(attempts) == 1:
            raise TransientToolError("connection reset")
        return DATA_RESULT

    spec = replace(DATA_TOOL, func=flaky, max_attempts=2)

    result = execute_tool(spec, {"min_flights": 1000, "top_n": 1})

    assert len(attempts) == 2
    assert result["results"][0]["Origin"] == "LGA"


def test_write_tool_needs_approval_before_it_runs():
    calls = []
    spec = replace(
        TOOL_REGISTRY["issue_customer_credit"], func=lambda **kw: calls.append(kw)
    )

    with pytest.raises(ApprovalRequiredError):
        execute_tool(spec, {"customer_id": "C-1", "amount": 10.0})

    assert calls == []


# -------------------------------------------------------------------
# Agent loop
# -------------------------------------------------------------------


@pytest.fixture
def data_run(monkeypatch, run_store):
    """Run the data-analysis skill with a fake data tool."""

    calls = []

    def fake_analysis(**kwargs):
        calls.append(kwargs)
        return DATA_RESULT

    monkeypatch.setattr(agent_module, "classify_interaction", routed_to("airline_data"))

    def ask(question, scripted):
        client = FakeClient(scripted)
        result = agent_module.run_agent(
            question,
            client=client,
            store=run_store,
            tools=tools_with(analyze_top_origin_cancellation_rates=fake_analysis),
        )
        return result, client

    return ask, calls


def test_data_question_runs_the_tool_then_forces_the_answer(data_run, run_store):
    ask, calls = data_run

    result, client = ask(
        "Top cancellation airport?",
        [
            model_response(
                "r1",
                [
                    function_call(
                        "analyze_top_origin_cancellation_rates",
                        {"min_flights": 1000, "top_n": 1},
                        "c1",
                    )
                ],
            ),
            model_response("r2", output_text="LGA has the highest rate."),
        ],
    )

    assert calls == [{"min_flights": 1000, "top_n": 1}]
    assert result.stop_reason == "final_answer"
    assert result.final_answer == "LGA has the highest rate."
    assert result.data_analysis_count == 1
    assert result.sources[0]["source_type"] == "dataset"

    # One call used the whole data budget, so the answer call offers no tools.
    assert "tools" not in client.responses.requests[-1]

    assert [c.checkpoint_id for c in run_store.checkpoints] == [
        "step_1_tool_1",
        "final",
    ]
    assert run_store.traces[0].stop_reason == "final_answer"


def test_repeated_identical_call_stops_the_run(data_run):
    ask, calls = data_run

    same_call = {"min_flights": 1000, "top_n": 1}

    result, _ = ask(
        "Top cancellation airport?",
        [
            model_response(
                "r1",
                [
                    function_call(
                        "analyze_top_origin_cancellation_rates", same_call, "c1"
                    ),
                    function_call(
                        "analyze_top_origin_cancellation_rates", same_call, "c2"
                    ),
                ],
            )
        ],
    )

    assert len(calls) == 1
    assert result.stop_reason == "repeated_tool_call"
    assert result.final_answer == ""


def test_invalid_arguments_go_back_to_the_model(data_run):
    ask, calls = data_run

    result, client = ask(
        "Top cancellation airport?",
        [
            model_response(
                "r1",
                [
                    function_call(
                        "analyze_top_origin_cancellation_rates",
                        {"min_flights": 0, "top_n": 1},
                        "c1",
                    )
                ],
            ),
            model_response("r2", output_text="Could not run the analysis."),
        ],
    )

    assert calls == []
    assert result.stop_reason == "final_answer"
    assert [e["error_type"] for e in result.errors] == ["input_validation_error"]

    tool_output = client.responses.requests[1]["input"][0]
    assert tool_output["call_id"] == "c1"
    assert "input_validation_error" in tool_output["output"]


def test_analytics_tool_budget_then_forced_answer(monkeypatch, run_store):
    calls = []

    def fake_rank(**kwargs):
        calls.append(kwargs)
        return {
            "dataset": "Delta-marketed domestic flights, July 2026",
            "metric": kwargs["metric"],
            "unit": "percent",
            "group_by": kwargs["group_by"],
            "order": kwargs["order"],
            "filters": {"origin": None, "destination": None, "only": None},
            "minimum_flights": 1,
            "results": [{"group": "ATL", "flights": 100, "value": 80.0}],
        }

    monkeypatch.setattr(agent_module, "classify_interaction", routed_to("airline_data"))

    def rank_call(metric, call_id):
        return function_call(
            "rank_flight_performance",
            {
                "metric": metric,
                "group_by": "origin",
                "order": "highest",
                "top_n": 3,
                "min_flights": 1,
                "origin": None,
                "destination": None,
                "only": None,
            },
            call_id,
        )

    client = FakeClient(
        [
            model_response("r1", [rank_call("on_time_arrival_rate", "c1")]),
            model_response("r2", [rank_call("cancellation_rate", "c2")]),
            model_response("r3", output_text="ATL leads both."),
        ]
    )

    result = agent_module.run_agent(
        "Compare on-time and cancellation rates by airport",
        client=client,
        store=run_store,
        tools=tools_with(rank_flight_performance=fake_rank),
    )

    assert len(calls) == 2
    assert result.data_analysis_count == 2
    assert result.final_answer == "ATL leads both."
    # The second call used the tool's budget of 2, so the answer had no tools.
    assert "tools" in client.responses.requests[1]
    assert "tools" not in client.responses.requests[2]
