"""Token usage, cost estimates and timing per run."""

import time

import pytest

import agentic_bi.core.agent as agent_module
from agentic_bi import config
from agentic_bi.core.agent import run_agent
from agentic_bi.core.interaction import InteractionDecision
from agentic_bi.core.usage import MeteredClient, UsageMeter, estimate_cost, read_usage
from conftest import FakeClient, function_call, model_response, token_usage, tools_with

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


def set_prices(monkeypatch, input_price="2", output_price="8", cached=None):
    monkeypatch.setenv("OPENAI_INPUT_PRICE_PER_M", input_price)
    monkeypatch.setenv("OPENAI_OUTPUT_PRICE_PER_M", output_price)

    if cached is not None:
        monkeypatch.setenv("OPENAI_CACHED_INPUT_PRICE_PER_M", cached)


def test_read_usage_tolerates_missing_fields():
    assert read_usage(model_response("r")) == (0, 0, 0)
    assert read_usage(model_response("r", usage=token_usage(10, 4, 3))) == (10, 3, 4)


def test_cost_is_none_without_prices():
    assert estimate_cost(1000, 0, 1000) is None


def test_cost_charges_cached_input_at_its_own_price(monkeypatch):
    set_prices(monkeypatch, input_price="2", output_price="8", cached="0.5")

    # 600 uncached * $2 + 400 cached * $0.5 + 500 output * $8, per million.
    assert estimate_cost(1000, 400, 500) == pytest.approx(0.0054)


def test_cached_price_defaults_to_the_input_price(monkeypatch):
    set_prices(monkeypatch, input_price="2", output_price="8")

    assert estimate_cost(1000, 400, 0) == pytest.approx(0.002)


@pytest.mark.parametrize("value", ["cheap", "-1"])
def test_bad_prices_raise_config_errors(monkeypatch, value):
    set_prices(monkeypatch, input_price=value)

    with pytest.raises(config.ConfigError, match="OPENAI_INPUT_PRICE_PER_M"):
        config.openai_prices()


def test_meter_groups_calls_by_stage(monkeypatch):
    set_prices(monkeypatch)

    meter = UsageMeter()
    client = MeteredClient(
        FakeClient(
            [
                model_response("a", usage=token_usage(100, 10)),
                model_response("b", usage=token_usage(300, 20)),
                model_response("c", usage=token_usage(200, 30)),
            ]
        ),
        meter,
    )

    meter.stage = "routing"
    client.responses.create(model="m", input="q")
    meter.stage = "agent"
    client.responses.create(model="m", input="q")
    client.responses.create(model="m", input="q")

    summary = meter.summary(tool_seconds=0.25, total_seconds=1.5)

    assert summary["model_calls"] == 3
    assert summary["input_tokens"] == 600
    assert summary["output_tokens"] == 60
    assert summary["total_tokens"] == 660
    assert summary["estimated_cost_usd"] == pytest.approx((600 * 2 + 60 * 8) / 1e6)
    assert summary["tool_seconds"] == 0.25
    assert summary["duration_seconds"] == 1.5
    assert [(s["stage"], s["calls"]) for s in summary["stages"]] == [
        ("routing", 1),
        ("agent", 2),
    ]


def test_metered_client_passes_requests_through():
    fake = FakeClient([model_response("a")])
    client = MeteredClient(fake, UsageMeter())

    response = client.responses.create(model="m", input="hello")

    assert response.id == "a"
    assert fake.responses.requests[0]["input"] == "hello"


def test_run_reports_usage_for_every_stage(monkeypatch, run_store):
    set_prices(monkeypatch)

    def classify(question, client=None):
        # Stands in for the real router: one model call through the client.
        client.responses.create(model="m", input=question)
        return InteractionDecision(intent="airline_data", reason="Test routing.")

    monkeypatch.setattr(agent_module, "classify_interaction", classify)

    client = FakeClient(
        [
            model_response("route", usage=token_usage(50, 5)),
            model_response(
                "r1",
                output=[
                    function_call(
                        "analyze_top_origin_cancellation_rates",
                        {"min_flights": 1000, "top_n": 1},
                        "call-1",
                    )
                ],
                usage=token_usage(400, 20, cached_tokens=100),
            ),
            model_response(
                "r2", output_text="LGA is highest.", usage=token_usage(600, 80)
            ),
        ]
    )

    result = run_agent(
        "Which airport cancels most?",
        client=client,
        store=run_store,
        tools=tools_with(analyze_top_origin_cancellation_rates=lambda **_: DATA_RESULT),
    )

    usage = result.usage

    assert result.final_answer == "LGA is highest."
    assert usage["model_calls"] == 3
    assert usage["input_tokens"] == 1050
    assert usage["cached_input_tokens"] == 100
    assert usage["output_tokens"] == 105
    assert usage["estimated_cost_usd"] == pytest.approx((1050 * 2 + 105 * 8) / 1e6)
    assert usage["tool_seconds"] >= 0
    assert [stage["stage"] for stage in usage["stages"]] == ["routing", "agent"]
    assert result.trace.usage == usage

    finished = [e for e in result.trace.events if e.event_type == "agent_finished"]
    assert finished[0].data["total_tokens"] == 1155


def test_official_web_search_counts_as_tool_time(monkeypatch, run_store):
    monkeypatch.setattr(
        agent_module,
        "classify_interaction",
        lambda question, client=None: InteractionDecision(
            intent="current_airline_info", reason="Test routing."
        ),
    )

    def answer(question, client=None):
        time.sleep(0.05)  # stands in for the Exa search
        client.responses.create(model="m", input=question)
        return {"answer": "Yes, small dogs.", "sources": []}

    monkeypatch.setattr(agent_module, "answer_current_delta_question", answer)

    client = FakeClient([model_response("a", usage=token_usage(300, 40))])

    result = run_agent("Can I bring my dog?", client=client, store=run_store)

    assert result.usage["tool_seconds"] >= 0.04
    assert [stage["stage"] for stage in result.usage["stages"]] == ["web answer"]
