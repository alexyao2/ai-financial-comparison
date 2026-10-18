import json
import math
from datetime import datetime
from typing import get_args
from model_decisions.investment_config import AssetType

def validate_decision(
        response: object, 
        expected_date: str | None = None,
    ) -> None:
    if not isinstance(response, dict):
        raise ValueError("Response must be a dictionary.")
    for field in ("decision_date", "allocations", "rationale", "risks"):
        if field not in response:
            raise ValueError(f"Missing required field: {field}")

    #validate allocations
    allocations = response["allocations"]
    if not isinstance(allocations, list) or not allocations:
        raise ValueError("allocations must be a non-empty list.")

    seen_identifiers: set[str] = set()
    weights: list[float] = []

    for index, allocation in enumerate(allocations):
        if not isinstance(allocation, dict):
            raise ValueError(f"Allocation {index} must be a dictionary.")

        for field in ("category", "identifier", "weight"):
            if field not in allocation:
                raise ValueError(f"Allocation {index} is missing {field}.")

        category = allocation["category"]
        if not isinstance(category, str) or category not in get_args(AssetType):
            raise ValueError(f"Allocation {index} has an invalid category.")

        identifier = allocation["identifier"]
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError(f"Allocation {index} needs an identifier.")

        if identifier != identifier.strip().upper():
            raise ValueError(
                f"Allocation {index} identifier must be uppercase "
                "without surrounding whitespace."
            )

        if category == "cash" and identifier != "USD":
            raise ValueError("Cash must use identifier USD.")

        if category != "cash" and identifier == "USD":
            raise ValueError("Identifier USD is reserved for cash.")

        if identifier in seen_identifiers:
            raise ValueError(f"Duplicate holding: {identifier}")
        seen_identifiers.add(identifier)

        weight = allocation["weight"]
        if type(weight) not in (int, float):
            raise ValueError(f"Allocation {index} weight must be numeric.")

        if not 0 <= weight <= 100:
            raise ValueError(
                f"Allocation {index} weight must be between 0 and 100."
            )

        if not math.isfinite(weight):
            raise ValueError(f"Allocation {index} weight must be finite.")

        weights.append(float(weight))

    if not math.isclose(
        math.fsum(weights),
        100.0,
        rel_tol=0,
        abs_tol=0.000001,
    ):
        raise ValueError("Allocation weights must total 100.")

    # Validate explanations.
    for field in ("rationale", "risks"):
        entries = response[field]
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"{field} must be a non-empty list.")

        for index, entry in enumerate(entries):
            if not isinstance(entry, str) or not entry.strip():
                raise ValueError(
                    f"{field}[{index}] must be a non-empty string."
                )
    
    #validate rationale & risks
    for field in ("rationale", "risks"):
        entries = response[field]
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"{field} must be a non-empty list.")

        for index, entry in enumerate(entries):
            if not isinstance(entry, str) or not entry.strip():
                raise ValueError(
                    f"{field}[{index}] must be a non-empty string.")

    # validate decision date
    decision_date = response["decision_date"]
    if not isinstance(response["decision_date"], str):
        raise ValueError("decision_date must be a string.")
    try:
        parsed_date = datetime.strptime(decision_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("decision_date must be a valid YYYY-MM-DD date.")
    if parsed_date.strftime("%Y-%m-%d") != decision_date:
        raise ValueError("decision_date must use exactly YYYY-MM-DD.")
    if expected_date is not None and decision_date != expected_date:
        raise ValueError("decision_date does not match the review date.")


if __name__ == "__main__":
    # Example usage
    response_text = '''
    {
        "allocations": [
            {"category": "individual_stock", "identifier": "AAPL", "weight": 50},
            {"category": "broad_equity_etf", "identifier": "SPY", "weight": 30},
            {"category": "treasury_bond_etf", "identifier": "TLT", "weight": 20}
        ],
        "decision_date": "2024-06-01",
        "rationale": ["Diversification across asset classes", "Long-term growth potential"],
        "risks": ["Market volatility", "Interest rate changes"]
    }
    '''
    parsed_response = json.loads(response_text)
    validate_decision(parsed_response)







        
