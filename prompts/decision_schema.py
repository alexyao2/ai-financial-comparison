from typing import Literal, TypedDict
from model_decisions.investment_config import AssetType

class OneAllocation(TypedDict):
    category: AssetType
    identifier: str
    weight: float

class DecisionSchema(TypedDict):
    allocations: list[OneAllocation]
    decision_date: str
    rationale: list[str]
    risks: list[str]