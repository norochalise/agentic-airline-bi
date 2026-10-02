import logging
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class TransientToolError(RuntimeError):
    """
    Temporary tool failure that may succeed when retried.
    """


class ToolTimeoutError(TimeoutError):
    """
    Tool operation exceeded its permitted execution time.
    """


class BusinessRuleError(ValueError):
    """
    Valid request that violates a business rule.
    """


class PermanentToolError(RuntimeError):
    """
    Tool failure that should not be retried automatically.
    """


def classify_tool_error(error: Exception) -> str:
    """
    Classify a tool failure for controller decision-making.
    """

    if isinstance(error, (TransientToolError, ToolTimeoutError, ConnectionError)):
        return "transient_error"

    if isinstance(error, BusinessRuleError):
        return "business_rule_error"

    if isinstance(error, ValueError):
        return "validation_or_input_error"

    if isinstance(error, PermanentToolError):
        return "permanent_tool_error"

    return "unexpected_tool_error"


def execute_with_retry(
    function: Callable[..., Any],
    *args,
    max_attempts: int = 2,
    base_delay_seconds: float = 0.5,
    retryable_exceptions: tuple[type[Exception], ...] = (
        TransientToolError,
        ToolTimeoutError,
        ConnectionError,
    ),
    **kwargs,
) -> Any:
    """
    Execute a tool with bounded retries and exponential backoff.

    Only explicitly retryable failures are retried.
    Validation, business-rule, and permanent failures propagate
    immediately.
    """

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    for attempt in range(1, max_attempts + 1):
        try:
            return function(*args, **kwargs)

        except retryable_exceptions:
            if attempt >= max_attempts:
                raise

            delay = base_delay_seconds * (2 ** (attempt - 1))

            logger.warning(
                "Transient failure; retrying in %.2fs (attempt %d/%d)",
                delay,
                attempt + 1,
                max_attempts,
            )

            time.sleep(delay)
