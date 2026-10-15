from typing import Literal, TypedDict
from datetime import datetime

class InvestmentConfig(TypedDict):
    initial_investment: int
    investment_start_date: datetime
    investment_end_date: datetime
    monthly_contribution: int
    allowed_assets: list[str]
    rebalance_frequency: Literal["monthly", "quarterly", "annually"]


