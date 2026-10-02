from functools import lru_cache

import pandas as pd

from agentic_bi.config import FLIGHT_DATA_PATH
from agentic_bi.data.loader import load_flight_data


@lru_cache(maxsize=1)
def _load_default_flight_data() -> pd.DataFrame:
    """
    Load the project flight dataset once per process.
    """

    return load_flight_data(FLIGHT_DATA_PATH)


def get_top_origin_cancellation_rates(
    df: pd.DataFrame, min_flights: int = 500, top_n: int = 10
) -> pd.DataFrame:
    """
    Rank origin airports by cancellation rate.

    Airports below the minimum flight-volume threshold are excluded
    to reduce unstable rankings from small samples.
    """

    required_columns = {"Origin", "Cancelled"}

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(f"Missing required columns: {sorted(missing_columns)}")

    if min_flights <= 0:
        raise ValueError("min_flights must be greater than zero")

    if top_n <= 0:
        raise ValueError("top_n must be greater than zero")

    summary = (
        df.groupby("Origin")
        .agg(
            total_flights=("Cancelled", "size"), cancelled_flights=("Cancelled", "sum")
        )
        .reset_index()
    )

    summary = summary[summary["total_flights"] >= min_flights].copy()

    summary["cancellation_rate"] = (
        summary["cancelled_flights"] / summary["total_flights"] * 100
    )

    return (
        summary.sort_values("cancellation_rate", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )


def analyze_top_origin_cancellation_rates(
    min_flights: int = 500, top_n: int = 10
) -> dict:
    """
    Analyze cancellation rates by origin airport using the
    project flight dataset.

    Returns structured records suitable for agent tool output.
    """

    df = _load_default_flight_data()

    results = get_top_origin_cancellation_rates(
        df=df, min_flights=min_flights, top_n=top_n
    )

    return {
        "dataset": "Delta-marketed domestic flights, July 2026",
        "minimum_flights": min_flights,
        "top_n": top_n,
        "results": results.to_dict(orient="records"),
    }
