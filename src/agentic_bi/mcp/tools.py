import asyncio
from pathlib import Path

from mcp import Client, StdioServerParameters

from agentic_bi.core.reliability import (
    PermanentToolError,
    TransientToolError,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


SERVER_PARAMS = StdioServerParameters(
    command="uv",
    args=[
        "run",
        "python",
        "-m",
        "agentic_bi.mcp.server",
    ],
    cwd=PROJECT_ROOT,
)


async def _call_origin_cancellation_tool(
    min_flights: int,
    top_n: int,
) -> dict:
    """
    Call the Delta cancellation-analysis capability through MCP.
    """

    try:
        async with Client(SERVER_PARAMS) as client:

            result = await client.call_tool(
                "top_origin_cancellation_rates",
                {
                    "min_flights": min_flights,
                    "top_n": top_n,
                },
            )

    except Exception as exc:
        raise TransientToolError(
            f"MCP connection or execution failed: {exc}"
        ) from exc


    if result.is_error:
        raise PermanentToolError(
            "MCP tool returned an error."
        )


    if result.structured_content is None:
        raise PermanentToolError(
            "MCP tool returned no structured content."
        )


    return result.structured_content


def analyze_top_origin_cancellation_rates_via_mcp(
    min_flights: int = 500,
    top_n: int = 5,
) -> dict:
    """
    Synchronous adapter for the MCP cancellation-analysis tool.
    """

    return asyncio.run(
        _call_origin_cancellation_tool(
            min_flights=min_flights,
            top_n=top_n,
        )
    )