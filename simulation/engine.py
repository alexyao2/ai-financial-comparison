"""Daily dollar-position simulator, with fees on buys AND sells."""
from dataclasses import dataclass, field
import math
import pandas as pd


@dataclass
class Portfolio:
    cash: float = 0.0
    holdings: dict[str, float] = field(default_factory=dict)
    contributed: float = 0.0
    fees: float = 0.0
    previous_prices: dict[str, float] = field(default_factory=dict)
    wealth_index: float = 1.0
    peak: float = 1.0

    @property
    def value(self):
        return self.cash + math.fsum(self.holdings.values())

    def snapshot(self):
        return {"holdings_usd": dict(self.holdings), "cash": self.cash,
                "portfolio_value": self.value, "total_contributed": self.contributed}

    def mark(self, prices):
        for ticker in self.holdings:
            if ticker not in self.previous_prices:
                raise ValueError(f"Missing previous valuation for {ticker}")
            self.holdings[ticker] *= prices[ticker] / self.previous_prices[ticker]

    def rebalance(self, weights, cost):
        # Solve W + cost * turnover(W) = pre-trade wealth. Cash has no fee.
        before = self.value
        names = set(self.holdings) | (set(weights) - {"USD"})
        def turnover(wealth):
            return math.fsum(abs(weights.get(t, 0) * wealth - self.holdings.get(t, 0))
                             for t in names)
        low, high = 0.0, before
        for _ in range(100):
            mid = (low + high) / 2
            if mid + cost * turnover(mid) > before:
                high = mid
            else:
                low = mid
        wealth = (low + high) / 2
        self.fees += cost * turnover(wealth)
        self.holdings = {t: weights[t] * wealth for t in weights
                         if t != "USD" and weights[t] > 0}
        self.cash = weights.get("USD", 0) * wealth

    def invest_deposit(self, amount, weights, cost):
        # Existing positions are not rebalanced between decision dates.
        invested_weight = 1 - weights.get("USD", 0)
        budget = amount / (1 + cost * invested_weight)
        self.cash -= amount
        self.cash += budget * weights.get("USD", 0)
        self.fees += budget * cost * invested_weight
        for ticker, weight in weights.items():
            if ticker != "USD" and weight > 0:
                self.holdings[ticker] = self.holdings.get(ticker, 0) + budget * weight

    def step(self, date, prices, deposit, weights, cost, rebalance=False):
        previous_value = self.value
        if self.holdings:
            self.mark(prices)
        marked_value = self.value
        self.cash += deposit
        self.contributed += deposit
        if rebalance:
            self.rebalance(weights, cost)
        elif deposit:
            self.invest_deposit(deposit, weights, cost)
        # Contributions arrive after today's market return, before closing trades.
        market_factor = marked_value / previous_value if previous_value else 1.0
        trade_factor = self.value / (marked_value + deposit) if marked_value + deposit else 1.0
        self.wealth_index *= market_factor * trade_factor
        self.peak = max(self.peak, self.wealth_index)
        self.previous_prices = {t: float(prices[t]) for t in self.holdings}
        if self.cash < -1e-7 or not math.isfinite(self.value):
            raise ValueError("Invalid portfolio state")
        return {"Date": date, "portfolio_value": self.value,
                "total_contributed": self.contributed, "total_fees": self.fees,
                "net_gain": self.value - self.contributed, "cash": self.cash,
                "time_weighted_return": self.wealth_index - 1,
                "drawdown": self.wealth_index / self.peak - 1}


def weights_from(decision):
    weights = {a["identifier"]: a["weight"] / 100 for a in decision["allocations"]}
    total = math.fsum(weights.values())
    # Validator permits only rounding error; normalize that tiny residual.
    return {ticker: weight / total for ticker, weight in weights.items()}


def review_period(date, frequency):
    divisor = {"monthly": 1, "quarterly": 3, "annually": 12}[frequency]
    return date.year, (date.month - 1) // divisor
