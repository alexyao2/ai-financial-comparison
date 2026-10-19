"""Cached adjusted closes; no missing-price filling or silent ticker removal."""
from pathlib import Path
import hashlib
import re
import numpy as np
import pandas as pd


def validate_prices(prices):
    if prices.empty or prices.index.has_duplicates or not prices.index.is_monotonic_increasing:
        raise ValueError("Prices must have unique, sorted, nonempty dates")
    if not np.isfinite(prices.to_numpy(dtype=float)).all() or (prices <= 0).any().any():
        raise ValueError("Prices must be complete, positive, finite numbers")
    return prices


class PriceStore:
    def __init__(self, start, end, root, offline=None):
        self.start = pd.Timestamp(start) - pd.Timedelta(days=400)
        self.end = pd.Timestamp(end)
        self.cache = Path(root) / ".cache" / "prices"
        self.offline = offline
        self.series = {}

    def get(self, ticker):
        if ticker == "USD":
            raise ValueError("Cash does not need a price series")
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.=-]{0,29}", ticker):
            raise ValueError(f"Unsupported Yahoo ticker syntax: {ticker}")
        if ticker in self.series:
            return self.series[ticker]
        if self.offline is not None:
            if ticker not in self.offline:
                raise ValueError(f"Offline fixture has no prices for {ticker}")
            series = self.offline[ticker].copy()
        else:
            key = hashlib.sha256(f"{ticker}|{self.start}|{self.end}".encode()).hexdigest()
            path = self.cache / f"{key}.csv"
            if path.exists():
                frame = pd.read_csv(path, index_col=0, parse_dates=True)
            else:
                import yfinance as yf
                data = yf.download(ticker, start=self.start.strftime("%Y-%m-%d"),
                                   end=(self.end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                                   auto_adjust=True, progress=False)
                if data is None or data.empty:
                    raise ValueError(f"No market data returned for {ticker}")
                close = data["Close"]
                series = close.iloc[:, 0] if isinstance(close, pd.DataFrame) else close
                frame = series.rename(ticker).to_frame()
                frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
                validate_prices(frame)
                self.cache.mkdir(parents=True, exist_ok=True)
                frame.to_csv(path)
            series = frame.iloc[:, 0]
        validate_prices(series.to_frame())
        self.series[ticker] = series
        return series

    def prices_on(self, date, tickers):
        result = {}
        for ticker in tickers:
            if ticker == "USD":
                continue
            series = self.get(ticker)
            if date not in series.index:
                raise ValueError(f"Missing price for {ticker} on {date.date()}; refusing to fill")
            result[ticker] = float(series.loc[date])
        return result

    def packet(self, cutoff):
        packet = {}
        for ticker in ("SPY", "TLT", "AAPL"):
            history = self.get(ticker).loc[:cutoff]
            if history.empty:
                packet[ticker] = {"available": False}
                continue
            row = {"as_of": history.index[-1].strftime("%Y-%m-%d")}
            for length in (21, 63, 126, 252):
                row[f"return_{length}_sessions"] = (float(history.iloc[-1] / history.iloc[-length-1] - 1)
                                                     if len(history) > length else None)
            packet[ticker] = row
        return packet


def synthetic_prices():
    """Deterministic test fixture, deliberately NOT historical performance."""
    dates = pd.bdate_range("2018-01-01", "2020-01-03")
    t = np.arange(len(dates))
    return pd.DataFrame({
        "SPY": 100 * np.exp(.00025*t + .025*np.sin(t/18)),
        "TLT": 100 * np.exp(.00010*t - .015*np.sin(t/18)),
        "AAPL": 100 * np.exp(.00040*t + .06*np.sin(t/23)),
    }, index=dates)
