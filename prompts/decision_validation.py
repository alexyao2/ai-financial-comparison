import json

def validate_decision(
        response: object, 
        expected_date: str | None = None,
    ) -> None:
    if not isinstance(response, dict):
        raise ValueError("Response must be a dictionary.")
    for field in ("decision_date", "allocations", "rationale", "risks"):
        if field not in response:
            raise ValueError(f"Missing required field: {field}")

    if not isinstance(response["allocations"], list):
        raise ValueError("allocations must be a list.")
    if not response["allocations"]:
        raise ValueError("allocations must be a non-empty list.")
    for index, allocation in enumerate(response["allocations"]):
        if not isinstance(allocation, dict):
            raise ValueError(f"Allocation at index {index} must be a dictionary.")
        for field in ("category", "identifier", "weight"):
            if field not in allocation:
                raise ValueError(f"Missing required field '{field}' in allocation at index {index}.")
        if not isinstance(allocation["category"], str):
            raise ValueError(f"Allocation category at index {index} must be a string.")
        if not isinstance(allocation["identifier"], str):
            raise ValueError(f"Allocation identifier at index {index} must be a string.")
        if type(allocation["weight"]) not in (int, float):
            raise ValueError(f"Allocation weight at index {index} must be a number.")
        if allocation["weight"] < 0 or allocation["weight"] > 100:
            raise ValueError(f"Allocation weight at index {index} must be between 0 and 100.")

    
    if not isinstance(response["rationale"], list):
        raise ValueError("rationale must be a list.")
    if response["rationale"] == []:
        raise ValueError("rationale must be a non-empty list.")
    for index, rationale in enumerate(response["rationale"]):
        if not isinstance(rationale, str):
            raise ValueError(f"Rationale at index {index} must be a string.")
        if rationale == "":
            raise ValueError(f"Rationale at index {index} must be a non-empty string.")
        if rationale != rationale.strip():
            raise ValueError(f"Rationale at index {index} must not have leading or trailing whitespace.")
    
    if not isinstance(response["risks"], list):
        raise ValueError("risks must be a list.")
    if response["risks"] == []:
        raise ValueError("risks must be a non-empty list.")
    for index, risk in enumerate(response["risks"]):
        if not isinstance(risk, str):
            raise ValueError(f"Risk at index {index} must be a string.")
        if risk == "":
            raise ValueError(f"Risk at index {index} must be a non-empty string.")
        if risk != risk.strip():
            raise ValueError(f"Risk at index {index} must not have leading or trailing whitespace.")

    if not isinstance(response["decision_date"], str):
        raise ValueError("decision_date must be a string.")
    if response["decision_date"] == "":
        raise ValueError("decision_date must be a non-empty string.")
    if response["decision_date"] != response["decision_date"].strip():
        raise ValueError("decision_date must not have leading or trailing whitespace.")


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







        
