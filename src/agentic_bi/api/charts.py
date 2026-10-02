"""Turn data-tool observations into chart specs for the chat UI.

Every value comes straight from validated tool output; nothing is
recomputed or estimated here.
"""

from typing import Any

from agentic_bi.api.schemas import ChartRow, ChartSpec

METRIC_TITLES = {
    "cancellation_rate": "Cancellation rate",
    "on_time_arrival_rate": "On-time arrival rate",
    "avg_arrival_delay_minutes": "Average arrival delay",
    "avg_departure_delay_minutes": "Average departure delay",
    "diversion_rate": "Diversion rate",
    "flight_count": "Flights",
}

GROUP_TITLES = {
    "origin": "origin airport",
    "destination": "destination airport",
    "route": "route",
    "operating_carrier": "operating carrier",
    "flight_date": "date",
    "day_of_week": "day of week",
}

CAUSE_TITLES = {
    "carrier": "Carrier",
    "weather": "Weather",
    "national_aviation_system": "National aviation system",
    "security": "Security",
    "late_arriving_aircraft": "Late-arriving aircraft",
}

# A chart needs at least two bars to compare.
MIN_ROWS = 2


def _sentence(text: str) -> str | None:
    """Upper-case the first letter only, keeping codes like ATL intact."""

    return text[:1].upper() + text[1:] if text else None


def _flights(count: float) -> str:
    return f"{int(count):,} flights"


def _origin_cancellation_chart(result: dict[str, Any]) -> list[ChartSpec]:
    rows = [
        ChartRow(
            label=row["Origin"],
            value=round(row["cancellation_rate"], 2),
            detail=(
                f"{int(row['cancelled_flights']):,} of "
                f"{_flights(row['total_flights'])} cancelled"
            ),
        )
        for row in result["results"]
    ]

    return [
        ChartSpec(
            title="Cancellation rate by origin airport",
            subtitle=f"Airports with at least {result['minimum_flights']:,} flights",
            unit="percent",
            label_header="Origin",
            value_header="Cancellation rate",
            rows=rows,
        )
    ]


def _performance_chart(result: dict[str, Any]) -> list[ChartSpec]:
    filters = result["filters"]
    scope = []

    if filters.get("origin"):
        scope.append(f"from {filters['origin']}")
    if filters.get("destination"):
        scope.append(f"to {filters['destination']}")
    if result["minimum_flights"] > 1:
        scope.append(f"at least {result['minimum_flights']:,} flights")

    metric_title = METRIC_TITLES[result["metric"]]
    group_title = GROUP_TITLES[result["group_by"]]

    return [
        ChartSpec(
            title=f"{metric_title} by {group_title}",
            subtitle=_sentence(", ".join(scope)),
            unit=result["unit"],
            label_header=_sentence(group_title),
            value_header=metric_title,
            rows=[
                ChartRow(
                    label=row["group"],
                    value=row["value"],
                    detail=_flights(row["flights"]),
                )
                for row in result["results"]
            ],
        )
    ]


def _delay_cause_charts(result: dict[str, Any]) -> list[ChartSpec]:
    return [
        ChartSpec(
            title="Share of delay minutes by cause",
            subtitle=(
                f"{result['delayed_flights_with_causes']:,} flights "
                "15+ minutes late with a reported cause"
            ),
            unit="percent",
            label_header="Cause",
            value_header="Share of delay minutes",
            rows=[
                ChartRow(
                    label=CAUSE_TITLES.get(item["cause"], item["cause"]),
                    value=item["share_percent"],
                    detail=f"{item['minutes']:,.0f} minutes",
                )
                for item in result["delay_causes"]
            ],
        ),
        ChartSpec(
            title="Cancellations by reason",
            subtitle=f"{result['cancelled_flights']:,} cancelled flights",
            unit="percent",
            label_header="Reason",
            value_header="Share of cancellations",
            rows=[
                ChartRow(
                    label=CAUSE_TITLES.get(item["reason"], item["reason"]),
                    value=item["share_percent"],
                    detail=_flights(item["flights"]),
                )
                for item in result["cancellation_reasons"]
            ],
        ),
    ]


_BUILDERS = {
    "analyze_top_origin_cancellation_rates": _origin_cancellation_chart,
    "rank_flight_performance": _performance_chart,
    "analyze_delay_causes": _delay_cause_charts,
}


def build_charts(observations: list[dict[str, Any]]) -> list[ChartSpec]:
    """Charts for every successful data-tool result with at least two rows."""

    charts = []

    for observation in observations:
        builder = _BUILDERS.get(observation.get("tool"))

        if builder is None:
            continue

        charts.extend(
            chart
            for chart in builder(observation["result"])
            if len(chart.rows) >= MIN_ROWS
        )

    return charts
