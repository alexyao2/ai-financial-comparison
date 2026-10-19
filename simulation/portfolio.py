import pandas as pd

from prompts.decision_validation import validate_decision


# assumes config and price data are valid and consistent
def simulate_quarter(
    prices: pd.DataFrame,
    decision: dict,
    initial_investment: float,
    monthly_contribution: float,
    transaction_cost_rate: float,
) -> pd.DataFrame:
    validate_decision(decision)

    weights = {
        allocation["identifier"]: allocation["weight"] / 100
        for allocation in decision["allocations"]
    }

    invested_assets = [
        identifier for identifier in weights if identifier != "USD"
    ]

    missing = set(invested_assets) - set(prices.columns)
    if missing:
        raise ValueError(f"Missing price data for: {sorted(missing)}")

    if prices.empty:
        raise ValueError("Price data cannot be empty.")

    # Dollar values of positions, not numbers of actual shares.
    holdings = {identifier: 0.0 for identifier in invested_assets}
    cash = 0.0
    total_contributed = 0.0
    total_fees = 0.0
    previous_prices = None
    previous_month = None
    records = []

    cash_weight = weights.get("USD", 0.0)
    invested_weight = sum(weights[ticker] for ticker in invested_assets)

    for date, current_prices in prices.iterrows():
        # Existing holdings earn today's close-to-close return.
        if previous_prices is not None:
            for ticker in invested_assets:
                holdings[ticker] *= (
                    current_prices[ticker] / previous_prices[ticker]
                )

        month = (date.year, date.month) # type: ignore
        deposit = 0.0

        if previous_prices is None:
            deposit += initial_investment

        if month != previous_month:
            deposit += monthly_contribution

        if deposit > 0:
            total_contributed += deposit

            # Make purchases plus their fees fit within the deposit.
            allocation_budget = deposit / (
                1 + transaction_cost_rate * invested_weight
            )
            fee = (
                allocation_budget
                * invested_weight
                * transaction_cost_rate
            )

            for ticker in invested_assets:
                holdings[ticker] += allocation_budget * weights[ticker]

            cash += allocation_budget * cash_weight
            total_fees += fee

        portfolio_value = cash + sum(holdings.values())

        records.append({
            "Date": date,
            "portfolio_value": portfolio_value,
            "total_contributed": total_contributed,
            "total_fees": total_fees,
            "net_gain": portfolio_value - total_contributed,
            "cash": cash,
        })

        previous_prices = current_prices
        previous_month = month

    return pd.DataFrame(records).set_index("Date")



if __name__ == "__main__":
    from pathlib import Path

    from model_decisions.investment import (
        investment_config,
        validate_investment_config,
    )

    validate_investment_config(investment_config)

    project_root = Path(__file__).resolve().parent.parent
    prices = pd.read_csv(
        project_root / "data" / "prices" / "sample_prices.csv",
        index_col="Date",
        parse_dates=True,
    )

    decision = {
        "decision_date": "2019-01-01",
        "allocations": [
            {"category": "individual_stock", "identifier": "AAPL", "weight": 50},
            {"category": "broad_equity_etf", "identifier": "SPY", "weight": 30},
            {"category": "treasury_bond_etf", "identifier": "TLT", "weight": 20},
        ],
        "rationale": ["Manually specified portfolio for testing."],
        "risks": ["Stock and bond prices may decline."],
    }

    results = simulate_quarter(
        prices=prices,
        decision=decision,
        initial_investment=investment_config["initial_investment"],
        monthly_contribution=investment_config["monthly_contribution"],
        transaction_cost_rate=investment_config["transaction_costs"],
    )

    print(results.head())
    print("\nFinal results:")
    print(results.tail(1))