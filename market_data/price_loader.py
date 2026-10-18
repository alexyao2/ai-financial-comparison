from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf


def load_prices() -> pd.DataFrame:
    """Download daily adjusted closing prices for the sample portfolio."""
    tickers = ["AAPL", "SPY", "TLT"]

    data = yf.download(
        tickers=tickers,
        start="2019-01-01",
        end="2019-04-01",
        interval="1d",
        auto_adjust=True,
        progress=False,
    )

    if data is None or data.empty:
        raise ValueError("The download returned no price data.")

    if isinstance(data.columns, pd.MultiIndex):
        close_level = next(
            (
                level
                for level in range(data.columns.nlevels)
                if "Close" in data.columns.get_level_values(level)
            ),
            None,
        )

        if close_level is None:
            raise ValueError("Downloaded data has no Close field.")

        prices = data.xs("Close", axis=1, level=close_level)
    else:
        # This loader expects multiple tickers.
        raise ValueError("Expected multi-ticker data with MultiIndex columns.")

    if not isinstance(prices, pd.DataFrame):
        raise ValueError("Expected a price table with one column per ticker.")

    missing_tickers = [
        ticker for ticker in tickers if ticker not in prices.columns
    ]
    if missing_tickers:
        raise ValueError(f"Missing tickers: {missing_tickers}")

    prices = prices.reindex(columns=tickers).sort_index()
    prices.index.name = "Date"

    if prices.index.has_duplicates:
        raise ValueError("Price data contains duplicate dates.")

    if prices.isna().any().any():
        raise ValueError(
            f"Missing prices by ticker:\n{prices.isna().sum()}"
        )

    if not np.isfinite(prices.to_numpy(dtype=float)).all():
        raise ValueError("Price data contains nonfinite values.")

    if (prices <= 0).any().any():
        raise ValueError("All prices must be positive.")

    return prices


if __name__ == "__main__":
    prices = load_prices()

    print("First five rows:")
    print(prices.head())

    print("\nLast five rows:")
    print(prices.tail())

    print("\nColumns:", prices.columns.tolist())
    print("\nMissing values:")
    print(prices.isna().sum())

    # Resolve the output relative to the project, not the terminal folder.
    project_root = Path(__file__).resolve().parent.parent
    output_path = project_root / "data" / "prices" / "sample_prices.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    prices.to_csv(output_path)
    print(f"\nSaved prices to: {output_path}")