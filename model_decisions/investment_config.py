from typing import Literal, TypedDict
from datetime import datetime

AssetType = Literal["individual_stock", "broad_equity_etf", "treasury_bond_etf", "cash", "cryptocurrency"]

class InvestmentConfig(TypedDict):
    initial_investment: int
    investment_start_date: datetime
    investment_end_date: datetime
    monthly_contribution: int
    allowed_asset_types: list[AssetType]
    rebalance_frequency: Literal["monthly", "quarterly", "annually"]
    transaction_costs: float

