from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import agentic_bi.api.app as app_module
from agentic_bi import config
from agentic_bi.api.rate_limit import SlidingWindowLimiter

client = TestClient(app_module.app)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_limiter_blocks_after_the_limit_and_reports_the_wait():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(window=60, clock=clock)

    assert limiter.hit("a", 2) is None
    clock.now += 10
    assert limiter.hit("a", 2) is None
    clock.now += 5

    assert limiter.hit("a", 2) == pytest.approx(45)
    # Other clients have their own budget.
    assert limiter.hit("b", 2) is None


def test_limiter_frees_hits_once_they_leave_the_window():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(window=60, clock=clock)

    limiter.hit("a", 1)
    clock.now += 60

    assert limiter.hit("a", 1) is None


def test_limit_of_zero_disables_the_limiter():
    limiter = SlidingWindowLimiter(window=60)

    assert all(limiter.hit("a", 0) is None for _ in range(100))


def test_rate_limit_settings_validate(monkeypatch):
    monkeypatch.delenv("ASK_RATE_LIMIT")
    monkeypatch.delenv("ASK_DAILY_LIMIT", raising=False)
    assert config.ask_rate_limit() == 10
    assert config.ask_daily_limit() == 0

    monkeypatch.setenv("ASK_RATE_LIMIT", "-1")
    with pytest.raises(config.ConfigError, match="ASK_RATE_LIMIT"):
        config.ask_rate_limit()

    monkeypatch.setenv("ASK_DAILY_LIMIT", "lots")
    with pytest.raises(config.ConfigError, match="ASK_DAILY_LIMIT"):
        config.ask_daily_limit()


@pytest.fixture
def fresh_limiters():
    app_module.client_limiter.reset()
    app_module.daily_limiter.reset()
    yield
    app_module.client_limiter.reset()
    app_module.daily_limiter.reset()


def test_ask_returns_429_with_retry_after_once_over_the_limit(
    monkeypatch, fresh_limiters
):
    monkeypatch.setenv("ASK_RATE_LIMIT", "1")

    with patch.object(app_module, "_answer") as answer:
        answer.side_effect = app_module.AgentFailure(500, "stub", "x")
        first = client.post("/ask", json={"question": "Top airport?"})
        second = client.post("/ask", json={"question": "Top airport?"})

    assert first.status_code == 500  # reached the agent
    assert second.status_code == 429
    assert "Too many questions" in second.json()["detail"]
    assert 1 <= int(second.headers["retry-after"]) <= 60
    assert answer.call_count == 1


def test_stream_is_limited_before_the_stream_starts(monkeypatch, fresh_limiters):
    monkeypatch.setenv("ASK_RATE_LIMIT", "1")
    app_module.client_limiter.hit("testclient", 1)

    with patch.object(app_module, "_answer") as answer:
        response = client.post("/ask/stream", json={"question": "Top airport?"})

    assert response.status_code == 429
    assert response.headers["content-type"].startswith("application/json")
    answer.assert_not_called()


def test_daily_cap_applies_across_clients(monkeypatch, fresh_limiters):
    monkeypatch.setenv("ASK_DAILY_LIMIT", "1")
    app_module.daily_limiter.hit("all", 1)

    response = client.post("/ask", json={"question": "Top airport?"})

    assert response.status_code == 429
    assert "daily" in response.json()["detail"]


def test_invalid_questions_do_not_use_up_the_limit(monkeypatch, fresh_limiters):
    monkeypatch.setenv("ASK_RATE_LIMIT", "1")

    client.post("/ask", json={"question": ""})

    assert app_module.client_limiter.hit("testclient", 1) is None
