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
    assert 'fetch("/ask"' in response.text


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ask_rejects_empty_question():
    response = client.post(
        "/ask",
        json={"question": ""},
    )

    assert response.status_code == 422


def test_ask_endpoint_with_mocked_agent():
    question = (
        "Which airport has the highest "
        "cancellation rate?"
    )

    fake_trace = AgentTrace(
        run_id="test-run-123",
        question=question,
        started_at="2026-01-01T00:00:00+00:00",
    )

    fake_result = AgentResult(
        goal=question,
        final_answer=(
            "LGA has the highest cancellation rate."
        ),
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
        "agentic_bi.api.app.run_agent",
        return_value=fake_result,
    ) as mock_run_agent:
        response = client.post(
            "/ask",
            json={"question": question},
        )

    assert response.status_code == 200

    body = response.json()

    assert body["answer"] == (
        "LGA has the highest cancellation rate."
    )
    assert body["selected_skill"] == "data-analysis"
    assert body["stop_reason"] == "final_answer"
    assert body["run_id"] == "test-run-123"
    assert body["step_count"] == 1
    assert body["tool_call_count"] == 1
    assert body["knowledge_search_count"] == 0
    assert body["data_analysis_count"] == 1
    assert body["error_count"] == 0

    mock_run_agent.assert_called_once_with(
        question=question,
        verbose=False,
    )