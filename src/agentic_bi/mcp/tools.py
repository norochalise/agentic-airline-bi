import asyncio
from pathlib import Path

import anyio
from mcp import Client, StdioServerParameters

from agentic_bi.core.reliability import PermanentToolError, TransientToolError

# src/agentic_bi/mcp/tools.py -> repository root
PROJECT_ROOT = Path(__file__).resolve().parents[3]


# Failures of the connection itself, which a fresh attempt may avoid.
_TRANSIENT_ERRORS = (
    TimeoutError,
    ConnectionError,
    anyio.BrokenResourceError,
    anyio.ClosedResourceError,
    anyio.EndOfStream,
)


SERVER_PARAMS = StdioServerParameters(
    command="uv",
    args=["run", "python", "-m", "agentic_bi.mcp.server"],
    cwd=PROJECT_ROOT,
)


def _leaf_errors(exc: BaseException) -> list[BaseException]:
    """
    Flatten the exception groups raised by the MCP client's task group.
    """

    if isinstance(exc, BaseExceptionGroup):
        return [leaf for inner in exc.exceptions for leaf in _leaf_errors(inner)]

    return [exc]


def _classify_mcp_failure(exc: Exception) -> Exception:
    """
    Map an MCP client failure to a retryable or non-retryable tool error.

    Only connection and timeout failures are retried. A missing `uv`
    executable, a protocol error from the server, or an unexpected bug
    would fail the same way again.
    """

    leaves = _leaf_errors(exc)

    if any(isinstance(leaf, FileNotFoundError) for leaf in leaves):
        return PermanentToolError(f"MCP server could not be started: {exc}")

    if any(isinstance(leaf, _TRANSIENT_ERRORS) for leaf in leaves):
        return TransientToolError(f"MCP connection failed: {exc}")

    return PermanentToolError(f"MCP execution failed: {exc}")


async def _call_origin_cancellation_tool(min_flights: int, top_n: int) -> dict:
    """
    Call the Delta cancellation-analysis capability through MCP.
    """

    try:
        async with Client(SERVER_PARAMS) as client:
            result = await client.call_tool(
                "top_origin_cancellation_rates",
                {"min_flights": min_flights, "top_n": top_n},
            )

    except Exception as exc:
        raise _classify_mcp_failure(exc) from exc

    if result.is_error:
        raise PermanentToolError("MCP tool returned an error.")

    if result.structured_content is None:
        raise PermanentToolError("MCP tool returned no structured content.")

    return result.structured_content


def analyze_top_origin_cancellation_rates_via_mcp(
    min_flights: int = 500, top_n: int = 5
) -> dict:
    """
    Synchronous adapter for the MCP cancellation-analysis tool.
    """

    return asyncio.run(
        _call_origin_cancellation_tool(min_flights=min_flights, top_n=top_n)
    )
