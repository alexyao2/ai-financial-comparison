from typing import TypedDict, get_args
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

DECISION_JSON_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["decision_date", "allocations", "rationale", "risks"],
    "properties": {
        "decision_date": {"type": "string"},
        "allocations": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["category", "identifier", "weight"],
            "properties": {
                "category": {"type": "string", "enum": list(get_args(AssetType))},
                "identifier": {"type": "string"},
                "weight": {"type": "number"},
            },
        }},
        "rationale": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
    },
}
