from pathlib import Path

import pandas as pd


def load_flight_data(file_path: Path) -> pd.DataFrame:
    """
    Load the Delta flight dataset for structured business analysis.
    """

    if not file_path.exists():
        raise FileNotFoundError(
            f"Flight dataset not found: {file_path}"
        )

    if file_path.suffix.lower() != ".csv":
        raise ValueError(
            f"Unsupported dataset type: {file_path.suffix}"
        )

    return pd.read_csv(file_path)