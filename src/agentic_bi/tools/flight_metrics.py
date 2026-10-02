"""Deterministic flight-performance metrics over the July 2026 dataset.

Definitions follow the DOT Air Travel Consumer Report:

- A flight is *on time* when it is completed (not cancelled or diverted)
  and arrives less than 15 minutes late. The on-time rate divides by ALL
  scheduled flights, so cancellations and diversions count as not on
  time. This reproduces the report's July 2026 figures exactly: 71.7% for
  the Delta network, 71.9% for Delta mainline (operating carrier DL).
- Average delays use completed flights with a reported delay.
- Delay minutes are the dataset's *DelayMinutes* fields: early arrivals
  count as 0, not as negative delay.
- Delay causes are reported only for flights at least 15 minutes late, so
  cause shares describe those flights, not the whole schedule.
"""

from typing import Literal

import pandas as pd

from agentic_bi.tools.flight_analysis import _load_default_flight_data

DATASET_NAME = "Delta-marketed domestic flights, July 2026"

ON_TIME_THRESHOLD_MINUTES = 15

Metric = Literal[
    "cancellation_rate",
    "on_time_arrival_rate",
    "avg_arrival_delay_minutes",
    "avg_departure_delay_minutes",
    "diversion_rate",
    "flight_count",
]

GroupBy = Literal[
    "origin", "destination", "route", "operating_carrier", "flight_date", "day_of_week"
]

METRIC_UNITS: dict[str, str] = {
    "cancellation_rate": "percent",
    "on_time_arrival_rate": "percent",
    "avg_arrival_delay_minutes": "minutes",
    "avg_departure_delay_minutes": "minutes",
    "diversion_rate": "percent",
    "flight_count": "flights",
}

DELAY_CAUSE_COLUMNS = {
    "carrier": "CarrierDelay",
    "weather": "WeatherDelay",
    "national_aviation_system": "NASDelay",
    "security": "SecurityDelay",
    "late_arriving_aircraft": "LateAircraftDelay",
}

CANCELLATION_CODES = {
    "A": "carrier",
    "B": "weather",
    "C": "national_aviation_system",
    "D": "security",
}

DAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def _with_group_keys(df: pd.DataFrame) -> pd.DataFrame:
    """Add the derived grouping columns used by the ranking tool."""

    dates = pd.to_datetime(df["FlightDate"])

    return df.assign(
        origin=df["Origin"],
        destination=df["Dest"],
        route=df["Origin"] + "-" + df["Dest"],
        operating_carrier=df["IATA_Code_Operating_Airline"],
        flight_date=df["FlightDate"],
        day_of_week=dates.dt.day_name(),
    )


def _filter(
    df: pd.DataFrame, origin: str | None, destination: str | None
) -> pd.DataFrame:
    if origin:
        df = df[df["Origin"] == origin]

    if destination:
        df = df[df["Dest"] == destination]

    return df


def _metric_by_group(grouped, metric: str) -> pd.Series:
    if metric == "flight_count":
        return grouped.size().astype(float)

    if metric == "cancellation_rate":
        return grouped["Cancelled"].mean() * 100

    if metric == "diversion_rate":
        return grouped["Diverted"].mean() * 100

    if metric == "on_time_arrival_rate":
        return grouped["on_time"].mean() * 100

    # Delay averages use completed flights with a reported delay.
    if metric == "avg_arrival_delay_minutes":
        return grouped["completed_arr_delay"].mean()

    if metric == "avg_departure_delay_minutes":
        return grouped["completed_dep_delay"].mean()

    raise ValueError(f"Unknown metric: {metric}")


def rank_flight_groups(
    df: pd.DataFrame,
    metric: str,
    group_by: str,
    order: str = "highest",
    top_n: int = 10,
    min_flights: int = 1,
    origin: str | None = None,
    destination: str | None = None,
    only: list[str] | None = None,
) -> pd.DataFrame:
    """
    Rank groups (airports, routes, carriers, days) by a flight metric.

    Groups with fewer than `min_flights` scheduled flights are excluded.
    `only` keeps just the listed group values, for direct comparisons.
    Returns columns: group, flights, value.
    """

    if metric not in METRIC_UNITS:
        raise ValueError(f"Unknown metric: {metric}")

    if group_by not in GroupBy.__args__:
        raise ValueError(f"Unknown group_by: {group_by}")

    if top_n <= 0 or min_flights <= 0:
        raise ValueError("top_n and min_flights must be greater than zero")

    data = _with_group_keys(_filter(df, origin, destination))

    completed = (data["Cancelled"] == 0) & (data["Diverted"] == 0)
    data = data.assign(
        on_time=(
            completed & (data["ArrDelayMinutes"] < ON_TIME_THRESHOLD_MINUTES)
        ).astype(float),
        completed_arr_delay=data["ArrDelayMinutes"].where(completed),
        completed_dep_delay=data["DepDelayMinutes"].where(completed),
    )

    if only:
        data = data[data[group_by].isin(only)]

    grouped = data.groupby(group_by)

    summary = pd.DataFrame(
        {"flights": grouped.size(), "value": _metric_by_group(grouped, metric)}
    ).reset_index(names="group")

    summary = summary[summary["flights"] >= min_flights].dropna(subset=["value"])

    if group_by == "day_of_week" and order == "calendar":
        summary["sort_key"] = summary["group"].map(DAY_ORDER.index)
        summary = summary.sort_values("sort_key").drop(columns="sort_key")
    elif group_by == "flight_date" and order == "calendar":
        summary = summary.sort_values("group")
    else:
        # Ties break on volume, then name, so results are reproducible.
        summary = summary.sort_values(
            ["value", "flights", "group"], ascending=[order == "lowest", False, True]
        )

    summary["value"] = summary["value"].round(2)

    return summary.head(top_n).reset_index(drop=True)


def rank_flight_performance(
    metric: str,
    group_by: str,
    order: str,
    top_n: int,
    min_flights: int,
    origin: str | None,
    destination: str | None,
    only: list[str] | None,
) -> dict:
    """Agent tool: rank groups of flights by a performance metric."""

    results = rank_flight_groups(
        _load_default_flight_data(),
        metric=metric,
        group_by=group_by,
        order=order,
        top_n=top_n,
        min_flights=min_flights,
        origin=origin,
        destination=destination,
        only=only,
    )

    return {
        "dataset": DATASET_NAME,
        "metric": metric,
        "unit": METRIC_UNITS[metric],
        "group_by": group_by,
        "order": order,
        "filters": {"origin": origin, "destination": destination, "only": only},
        "minimum_flights": min_flights,
        "results": results.to_dict(orient="records"),
    }


def summarize_delay_causes(
    df: pd.DataFrame,
    origin: str | None = None,
    destination: str | None = None,
    operating_carrier: str | None = None,
) -> dict:
    """Delay minutes by cause and cancellations by reason code."""

    data = _filter(df, origin, destination)

    if operating_carrier:
        data = data[data["IATA_Code_Operating_Airline"] == operating_carrier]

    if data.empty:
        raise ValueError("No flights match these filters.")

    with_causes = data.dropna(subset=list(DELAY_CAUSE_COLUMNS.values()), how="all")

    minutes = {
        cause: float(with_causes[column].fillna(0).sum())
        for cause, column in DELAY_CAUSE_COLUMNS.items()
    }
    total_minutes = sum(minutes.values())

    cancelled = data[data["Cancelled"] == 1]
    codes = cancelled["CancellationCode"].value_counts()

    return {
        "flights": int(len(data)),
        "delayed_flights_with_causes": int(len(with_causes)),
        "delay_causes": [
            {
                "cause": cause,
                "minutes": round(value, 1),
                "share_percent": (
                    round(value / total_minutes * 100, 2) if total_minutes else 0.0
                ),
            }
            for cause, value in sorted(
                minutes.items(), key=lambda item: item[1], reverse=True
            )
        ],
        "cancelled_flights": int(len(cancelled)),
        "cancellation_reasons": [
            {
                "reason": CANCELLATION_CODES.get(code, f"code {code}"),
                "flights": int(count),
                "share_percent": round(count / len(cancelled) * 100, 2),
            }
            for code, count in codes.items()
        ],
    }


def analyze_delay_causes(
    origin: str | None, destination: str | None, operating_carrier: str | None
) -> dict:
    """Agent tool: break down delay minutes and cancellations by cause."""

    summary = summarize_delay_causes(
        _load_default_flight_data(),
        origin=origin,
        destination=destination,
        operating_carrier=operating_carrier,
    )

    return {
        "dataset": DATASET_NAME,
        "filters": {
            "origin": origin,
            "destination": destination,
            "operating_carrier": operating_carrier,
        },
        **summary,
    }
