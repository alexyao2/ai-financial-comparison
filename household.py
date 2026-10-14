from finance_schema import Finances

def validate_finances(finances: Finances) -> None:
    def check_amount(name: str, value: int) -> None:
        if type (value) is not int or value < 0:
            raise ValueError(f"{name} must be a non-negative integer, got {value}")

    for name in ("total_income", "rent", "mortgage", "utilities"):
        check_amount(name, finances[name])


household: Finances = {
    "total_income": 8000,
    "rent": 500,
    "mortgage": 0,
    "utilities": 300,
    "living_expenses": {
        "groceries": 400,
        "transportation": 200,
        "dining_out": 150,
    },
    "subscriptions": {
        "internet": 60,
        "streaming_services": 30,
        "fitness": 50,
    },
    "insurance": {
        "health": 200,
        "auto": 100,
        "home": 150,
    },
}

