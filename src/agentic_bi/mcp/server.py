from mcp.server import MCPServer

from agentic_bi.core.schemas import (
    OriginCancellationAnalysisOutput,
)
from agentic_bi.tools.flight_analysis import (
    analyze_top_origin_cancellation_rates,
)


mcp = MCPServer(
    "Delta Business Intelligence"
)


@mcp.tool()
def top_origin_cancellation_rates(
    min_flights: int = 500,
    top_n: int = 5,
) -> OriginCancellationAnalysisOutput:
    """
    Rank Delta-marketed origin airports by cancellation rate
    for the July 2026 domestic flight dataset.

    Airports below min_flights are excluded.
    """

    result = analyze_top_origin_cancellation_rates(
        min_flights=min_flights,
        top_n=top_n,
    )

    return OriginCancellationAnalysisOutput.model_validate(
        result
    )


if __name__ == "__main__":
    mcp.run()