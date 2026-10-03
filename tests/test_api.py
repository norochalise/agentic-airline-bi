import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from agentic_bi.api.app import app
from agentic_bi.core.agent import AgentResult
from agentic_bi.core.observability import AgentTrace

client = TestClient(app)


def test_frontend_endpoint():
    response = client.get("/")

    assert response.status_code == 200
    assert "Airline Intelligence Assistant" in response.text
    assert 'id="ask-form"' in response.text


def test_frontend_stylesheet():
    response = client.get("/static/styles.css")

    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]


def test_frontend_javascript():
    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert 'fetch("/ask/stream"' in response.text


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ask_rejects_empty_question():
    response = client.post("/ask", json={"question": ""})

    assert response.status_code == 422


def test_ask_endpoint_with_mocked_agent():
    question = "Which airport has the highest cancellation rate?"

    fake_trace = AgentTrace(
        run_id="test-run-123", question=question, started_at="2026-01-01T00:00:00+00:00"
    )

    fake_result = AgentResult(
        goal=question,
        final_answer=("LGA has the highest cancellation rate."),
        selected_skill="data-analysis",
        stop_reason="final_answer",
        step_count=1,
        tool_call_count=1,
        knowledge_search_count=0,
        data_analysis_count=1,
        errors=[],
        trace=fake_trace,
    )

    with patch(
        "agentic_bi.api.app.run_agent", return_value=fake_result
    ) as mock_run_agent:
        response = client.post("/ask", json={"question": question})

    assert response.status_code == 200

    body = response.json()

    assert body["answer"] == ("LGA has the highest cancellation rate.")
    assert body["selected_skill"] == "data-analysis"
    assert body["stop_reason"] == "final_answer"
    assert body["run_id"] == "test-run-123"
    assert body["step_count"] == 1
    assert body["tool_call_count"] == 1
    assert body["knowledge_search_count"] == 0
    assert body["data_analysis_count"] == 1
    assert body["error_count"] == 0

    mock_run_agent.assert_called_once_with(
        question=question, verbose=False, history=None, on_event=None
    )


def test_frontend_assets_require_revalidation():
    for path in ("/", "/static/styles.css", "/static/app.js"):
        response = client.get(path)

        assert response.headers["cache-control"] == "no-cache"


def test_ask_rejects_whitespace_only_question():
    response = client.post("/ask", json={"question": "   "})

    assert response.status_code == 422


def test_ask_rejects_overlong_question():
    response = client.post("/ask", json={"question": "x" * 2001})

    assert response.status_code == 422
    assert "2000" in response.json()["detail"][0]["msg"]


def test_agent_failure_returns_a_clean_error_without_internals():
    with patch(
        "agentic_bi.api.app.run_agent",
        side_effect=RuntimeError("secret stack detail: sk-test-key"),
    ):
        response = client.post("/ask", json={"question": "Top airport?"})

    assert response.status_code == 500

    body = response.json()
    assert body["error_id"]
    assert body["error_id"] in body["detail"]
    assert "secret" not in body["detail"]
    assert "sk-test-key" not in response.text


def test_missing_configuration_returns_503():
    from agentic_bi.config import ConfigError

    with patch(
        "agentic_bi.api.app.run_agent",
        side_effect=ConfigError("OPENAI_MODEL is not configured."),
    ):
        response = client.post("/ask", json={"question": "Top airport?"})

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_startup_warms_up_models_unless_disabled(monkeypatch):
    import agentic_bi.api.app as app_module

    calls = []
    monkeypatch.setattr(app_module, "validate_settings", lambda: None)
    monkeypatch.setattr(app_module, "warm_up_tools", lambda: calls.append(1) or {})

    monkeypatch.setenv("WARM_UP_ON_STARTUP", "true")
    with TestClient(app):
        pass

    monkeypatch.setenv("WARM_UP_ON_STARTUP", "false")
    with TestClient(app):
        pass

    assert calls == [1]


def fake_result(question="Top airport?", answer="LGA."):
    return AgentResult(
        goal=question,
        final_answer=answer,
        selected_skill="data-analysis",
        stop_reason="final_answer",
        step_count=1,
        tool_call_count=1,
        knowledge_search_count=0,
        data_analysis_count=1,
        trace=AgentTrace(
            run_id="run-1", question=question, started_at="2026-01-01T00:00:00+00:00"
        ),
    )


def parse_sse(text):
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def test_history_is_passed_to_the_agent():
    history = [
        {"role": "user", "content": "Top cancellation airport?"},
        {"role": "assistant", "content": "LGA."},
    ]

    with patch("agentic_bi.api.app.run_agent", return_value=fake_result()) as mocked:
        response = client.post(
            "/ask", json={"question": "and for JFK?", "history": history}
        )

    assert response.status_code == 200
    assert mocked.call_args.kwargs["history"] == history


def test_history_is_bounded():
    history = [{"role": "user", "content": "q"}] * 7

    response = client.post("/ask", json={"question": "and?", "history": history})

    assert response.status_code == 422


def test_stream_sends_progress_then_the_result():
    def fake_run_agent(question, verbose, history, on_event):
        on_event("agent_started", {})
        on_event("tool_started", {"tool": "rank_flight_performance"})
        on_event("checkpoint_saved", {})  # not user-facing: skipped
        return fake_result(question)

    with patch("agentic_bi.api.app.run_agent", side_effect=fake_run_agent):
        response = client.post("/ask/stream", json={"question": "Top airport?"})

    assert response.headers["content-type"].startswith("text/event-stream")

    events = parse_sse(response.text)
    assert [kind for kind, _ in events] == ["progress", "progress", "result"]
    assert events[1][1]["message"] == "Analyzing flight data…"
    assert events[2][1]["answer"] == "LGA."
    assert events[2][1]["run_id"] == "run-1"


def test_stream_reports_failures_as_an_error_event():
    with patch("agentic_bi.api.app.run_agent", side_effect=RuntimeError("boom")):
        response = client.post("/ask/stream", json={"question": "Top airport?"})

    ((kind, payload),) = parse_sse(response.text)

    assert kind == "error"
    assert payload["status"] == 500
    assert "boom" not in payload["detail"]


def test_feedback_is_appended(monkeypatch, tmp_path):
    import agentic_bi.api.app as app_module

    path = tmp_path / "feedback.jsonl"
    monkeypatch.setattr(app_module, "FEEDBACK_PATH", path)

    response = client.post(
        "/feedback",
        json={"run_id": "3f2a9c1e-0000-4000-8000-000000000001", "rating": "down"},
    )

    assert response.status_code == 204

    (record,) = [json.loads(line) for line in path.read_text().splitlines()]
    assert record["rating"] == "down"
    assert record["recorded_at"]


def test_feedback_rejects_bad_input():
    assert (
        client.post("/feedback", json={"run_id": "x", "rating": "up"}).status_code
        == 422
    )
    assert (
        client.post(
            "/feedback", json={"run_id": "abcdef12", "rating": "meh"}
        ).status_code
        == 422
    )


def test_ask_returns_usage_when_the_run_reports_it():
    result = fake_result()
    result.usage = {
        "model_calls": 2,
        "input_tokens": 900,
        "cached_input_tokens": 0,
        "output_tokens": 100,
        "total_tokens": 1000,
        "estimated_cost_usd": 0.0026,
        "duration_seconds": 2.5,
        "model_seconds": 2.1,
        "tool_seconds": 0.2,
        "stages": [
            {
                "stage": "agent",
                "calls": 2,
                "seconds": 2.1,
                "input_tokens": 900,
                "output_tokens": 100,
            }
        ],
    }

    with patch("agentic_bi.api.app.run_agent", return_value=result):
        body = client.post("/ask", json={"question": "Top airport?"}).json()

    assert body["usage"]["total_tokens"] == 1000
    assert body["usage"]["estimated_cost_usd"] == 0.0026
    assert body["usage"]["stages"][0]["stage"] == "agent"


def test_ask_usage_is_null_when_missing():
    with patch("agentic_bi.api.app.run_agent", return_value=fake_result()):
        body = client.post("/ask", json={"question": "Top airport?"}).json()

    assert body["usage"] is None
