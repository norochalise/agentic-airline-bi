import pandas as pd
import pytest
from pydantic import ValidationError

from agentic_bi.core.schemas import FlightPerformanceArgs
from agentic_bi.tools.flight_analysis import _load_default_flight_data
from agentic_bi.tools.flight_metrics import rank_flight_groups, summarize_delay_causes

COLUMNS = [
    "FlightDate",
    "IATA_Code_Operating_Airline",
    "Origin",
    "Dest",
    "DepDelayMinutes",
    "ArrDelayMinutes",
    "Cancelled",
    "CancellationCode",
    "Diverted",
    "CarrierDelay",
    "WeatherDelay",
    "NASDelay",
    "SecurityDelay",
    "LateAircraftDelay",
]

NO_CAUSE = (None, None, None, None, None)


@pytest.fixture
def flights():
    rows = [
        # ATL -> LGA: on time, 20 min late (carrier + weather), cancelled (weather)
        ("2026-07-06", "DL", "ATL", "LGA", 0, 0, 0, None, 0, *NO_CAUSE),
        ("2026-07-06", "DL", "ATL", "LGA", 25, 20, 0, None, 0, 15, 5, 0, 0, 0),
        ("2026-07-07", "OO", "ATL", "LGA", None, None, 1, "B", 0, *NO_CAUSE),
        # JFK -> ATL: 40 min late (late aircraft), diverted
        ("2026-07-07", "OO", "JFK", "ATL", 45, 40, 0, None, 0, 0, 0, 0, 0, 40),
        ("2026-07-07", "OO", "JFK", "ATL", 0, None, 0, None, 1, *NO_CAUSE),
    ]
    return pd.DataFrame(rows, columns=COLUMNS)


def rank(df, metric, group_by, **kwargs):
    result = rank_flight_groups(df, metric=metric, group_by=group_by, **kwargs)
    return list(zip(result["group"], result["value"], strict=True))


def test_on_time_rate_counts_cancelled_and_diverted_as_not_on_time(flights):
    # ATL: 1 of 3 on time; JFK: 0 of 2 (one late, one diverted).
    assert rank(flights, "on_time_arrival_rate", "origin") == [
        ("ATL", 33.33),
        ("JFK", 0.0),
    ]


def test_average_delay_uses_completed_flights_only(flights):
    # ATL completed arrivals: 0 and 20 minutes; the cancellation is ignored.
    assert rank(flights, "avg_arrival_delay_minutes", "origin", order="lowest") == [
        ("ATL", 10.0),
        ("JFK", 40.0),
    ]


def test_groups_routes_carriers_and_weekdays(flights):
    assert rank(flights, "flight_count", "route") == [("ATL-LGA", 3), ("JFK-ATL", 2)]
    assert rank(flights, "diversion_rate", "operating_carrier") == [
        ("OO", 33.33),
        ("DL", 0.0),
    ]
    # 2026-07-06 is a Monday.
    assert rank(flights, "flight_count", "day_of_week", order="calendar") == [
        ("Monday", 2),
        ("Tuesday", 3),
    ]


def test_filters_threshold_and_comparison(flights):
    assert rank(flights, "flight_count", "destination", origin="JFK") == [("ATL", 2)]
    assert rank(flights, "cancellation_rate", "origin", min_flights=3) == [
        ("ATL", 33.33)
    ]
    assert rank(flights, "flight_count", "origin", only=["JFK"]) == [("JFK", 2)]


def test_delay_causes_share_minutes_and_cancellation_reasons(flights):
    summary = summarize_delay_causes(flights)

    shares = {item["cause"]: item["share_percent"] for item in summary["delay_causes"]}
    assert shares["late_arriving_aircraft"] == 66.67
    assert shares["carrier"] == 25.0
    assert shares["weather"] == 8.33
    assert summary["delayed_flights_with_causes"] == 2
    assert summary["cancellation_reasons"] == [
        {"reason": "weather", "flights": 1, "share_percent": 100.0}
    ]

    with pytest.raises(ValueError, match="No flights"):
        summarize_delay_causes(flights, origin="SEA")


def test_calendar_order_needs_a_time_grouping():
    base = {
        "metric": "flight_count",
        "top_n": 5,
        "min_flights": 1,
        "origin": None,
        "destination": None,
        "only": None,
    }

    with pytest.raises(ValidationError, match="calendar"):
        FlightPerformanceArgs(**base, group_by="origin", order="calendar")

    FlightPerformanceArgs(**base, group_by="day_of_week", order="calendar")


def test_on_time_rate_matches_the_dot_report_for_july_2026():
    # DOT Air Travel Consumer Report (Sep 2026), July 2026: Delta network
    # 71.7% on time, Delta mainline (operating carrier DL) 71.9%.
    data = _load_default_flight_data()

    network = rank_flight_groups(
        data.assign(Origin="ALL"), "on_time_arrival_rate", "origin"
    )
    mainline = rank_flight_groups(
        data, "on_time_arrival_rate", "operating_carrier", only=["DL"]
    )

    assert round(network["value"][0], 1) == 71.7
    assert round(mainline["value"][0], 1) == 71.9
