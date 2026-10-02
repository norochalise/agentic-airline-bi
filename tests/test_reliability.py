import pytest

from agentic_bi.core.reliability import (
    TransientToolError,
    execute_with_retry,
)


def test_successful_function_runs_once():
    call_count = 0

    def successful_tool():
        nonlocal call_count
        call_count += 1
        return "success"

    result = execute_with_retry(
        successful_tool,
        max_attempts=2,
        base_delay_seconds=0,
    )

    assert result == "success"
    assert call_count == 1


def test_transient_error_is_retried():
    call_count = 0

    def flaky_tool():
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            raise TransientToolError(
                "Temporary failure"
            )

        return "recovered"

    result = execute_with_retry(
        flaky_tool,
        max_attempts=2,
        base_delay_seconds=0,
    )

    assert result == "recovered"
    assert call_count == 2


def test_non_retryable_error_is_not_retried():
    call_count = 0

    def invalid_tool():
        nonlocal call_count
        call_count += 1
        raise ValueError("Invalid input")

    with pytest.raises(ValueError):
        execute_with_retry(
            invalid_tool,
            max_attempts=3,
            base_delay_seconds=0,
        )

    assert call_count == 1