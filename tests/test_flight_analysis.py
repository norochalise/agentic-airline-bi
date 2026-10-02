import pandas as pd
import pytest

from agentic_bi.tools.flight_analysis import get_top_origin_cancellation_rates


@pytest.fixture
def flights():
    # ATL: 4 flights, 1 cancelled (25%). JFK: 3 flights, 2 cancelled (66.7%).
    # BOS: 1 flight, cancelled (100%) but below any sensible volume floor.
    rows = [("ATL", 0), ("ATL", 0), ("ATL", 1), ("ATL", 0)]
    rows += [("JFK", 1), ("JFK", 1), ("JFK", 0)]
    rows += [("BOS", 1)]
    return pd.DataFrame(rows, columns=["Origin", "Cancelled"])


def test_ranks_airports_by_cancellation_rate(flights):
    result = get_top_origin_cancellation_rates(flights, min_flights=2, top_n=5)

    assert list(result["Origin"]) == ["JFK", "ATL"]
    assert result.loc[0, "total_flights"] == 3
    assert result.loc[0, "cancelled_flights"] == 2
    assert result.loc[0, "cancellation_rate"] == pytest.approx(200 / 3)
    assert result.loc[1, "cancellation_rate"] == pytest.approx(25.0)


def test_low_volume_airports_are_excluded(flights):
    result = get_top_origin_cancellation_rates(flights, min_flights=1, top_n=5)
    assert result.loc[0, "Origin"] == "BOS"

    result = get_top_origin_cancellation_rates(flights, min_flights=4, top_n=5)
    assert list(result["Origin"]) == ["ATL"]


def test_top_n_limits_the_rows(flights):
    result = get_top_origin_cancellation_rates(flights, min_flights=1, top_n=2)

    assert len(result) == 2


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"min_flights": 0, "top_n": 5}, "min_flights"),
        ({"min_flights": 1, "top_n": 0}, "top_n"),
    ],
)
def test_invalid_parameters_are_rejected(flights, kwargs, message):
    with pytest.raises(ValueError, match=message):
        get_top_origin_cancellation_rates(flights, **kwargs)


def test_missing_columns_are_reported():
    with pytest.raises(ValueError, match="Cancelled"):
        get_top_origin_cancellation_rates(pd.DataFrame({"Origin": ["ATL"]}))
