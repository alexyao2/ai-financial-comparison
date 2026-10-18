import math
from datetime import datetime
from typing import get_args
from model_decisions.investment_config import AssetType, InvestmentConfig

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
    
    if not isinstance(config["allowed_asset_types"], list):
        raise ValueError("Allowed asset types must be a list.")
    if not config["allowed_asset_types"]:
        raise ValueError("Allowed asset types list cannot be empty.")

    if type(config["transaction_costs"]) is not float or not math.isfinite(config["transaction_costs"]) < 0:
        raise ValueError("Transaction costs must be a finite float.")
    if not 0 <= config["transaction_costs"] <= 1:
        raise ValueError("Transaction costs must be between 0 and 1.")

    # validate that the start date is before the end date
    if config["investment_start_date"] >= config["investment_end_date"]:
        raise ValueError("Investment start date must be before the investment end date.")
    
    # validate the asset types are non-empty and unique
    for asset_type in config["allowed_asset_types"]:
        if not isinstance(asset_type, str):
            raise ValueError(f"Allowed asset type '{asset_type}' must be a string.")
        if asset_type.strip() == "":
            raise ValueError("Allowed asset types cannot be empty strings.")
        if asset_type != asset_type.strip().lower():
            raise ValueError(f"Allowed asset type '{asset_type}' must be in lowercase and without leading/trailing whitespace.")
        if asset_type not in get_args(AssetType):
            raise ValueError(f"Allowed asset type '{asset_type}' is not a valid asset type. Valid types are: {get_args(AssetType)}")


    if len(config["allowed_asset_types"]) != len(set(config["allowed_asset_types"])):
        raise ValueError("Allowed asset types list contains duplicate entries.")
    
    if config["rebalance_frequency"] not in ["monthly", "quarterly", "annually"]:
        raise ValueError("Rebalance frequency must be 'monthly', 'quarterly', or 'annually'.")


investment_config: InvestmentConfig = {
    "initial_investment": 10000,
    "investment_start_date": datetime(2019, 1, 1),
    "investment_end_date": datetime(2025, 12, 31),
    "monthly_contribution": 500,
    "allowed_asset_types": ["individual_stock", "broad_equity_etf", "treasury_bond_etf", "cash", "cryptocurrency"],
    "rebalance_frequency": "quarterly",
    "transaction_costs": 0.01,  # 1% transaction costs
}

if __name__ == "__main__":
    try:
        validate_investment_config(investment_config)
        print("Investment configuration is valid.")
    except ValueError as e:
        print(f"Investment configuration validation error: {e}")