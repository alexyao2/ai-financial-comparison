from datetime import datetime
from model_decisions.investment_config import InvestmentConfig

def validate_investment_config(config: InvestmentConfig) -> None:
    # validate that all fields are present and of the correct type
    if type(config["initial_investment"]) is not int or config["initial_investment"] < 0:
        raise ValueError("Initial investment must be a non-negative integer.")

    if type(config["monthly_contribution"]) is not int or config["monthly_contribution"] < 0:
        raise ValueError("Monthly contribution must be a non-negative integer.")

    if not isinstance(config["investment_start_date"], datetime):
        raise ValueError("Investment start date must be a datetime object.")

    if not isinstance(config["investment_end_date"], datetime):
        raise ValueError("Investment end date must be a datetime object.")
    
    if not isinstance(config["allowed_assets"], list):
        raise ValueError("Allowed assets must be a list.")
    if not config["allowed_assets"]:
        raise ValueError("Allowed assets list cannot be empty.")

    # validate that the start date is before the end date
    if config["investment_start_date"] >= config["investment_end_date"]:
        raise ValueError("Investment start date must be before the investment end date.")
    
    # validate the assets are non-empty and unique
    for asset in config["allowed_assets"]:
        if not isinstance(asset, str):
            raise ValueError(f"Allowed asset '{asset}' must be a string.")
        if asset.strip() == "":
            raise ValueError("Allowed asset names cannot be empty strings.")
        if asset != asset.strip().lower():
            raise ValueError(f"Allowed asset '{asset}' must be in lowercase and without leading/trailing whitespace.")

    if len(config["allowed_assets"]) != len(set(config["allowed_assets"])):
        raise ValueError("Allowed assets list contains duplicate entries.")
    
    if config["rebalance_frequency"] not in ["monthly", "quarterly", "annually"]:
        raise ValueError("Rebalance frequency must be 'monthly', 'quarterly', or 'annually'.")


assets = ["stocks", "bonds", "real_estate", "commodities", "cryptocurrency"]
investment_config: InvestmentConfig = {
    "initial_investment": 10000,
    "investment_start_date": datetime(2025, 1, 1),
    "investment_end_date": datetime(2019, 12, 31),
    "monthly_contribution": 500,
    "allowed_assets": assets,
    "rebalance_frequency": "quarterly",
}

if __name__ == "__main__":
    try:
        validate_investment_config(investment_config)
        print("Investment configuration is valid.")
    except ValueError as e:
        print(f"Investment configuration validation error: {e}")