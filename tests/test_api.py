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

    mock_run_agent.assert_called_once_with(question=question, verbose=False)


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
