from savings_calculations.finance_schema import Finances

# Use type ignore comments to suppress type checking for dictionary values, since we know
# they will be integers based on the Finances TypedDict definition.
def validate_finances(finances: Finances) -> None:
    def check_amount(name: str, value: int) -> None:
        if type (value) is not int or value < 0:
            raise ValueError(f"{name} must be a non-negative integer, got {value}")

    for name in ("total_income", "rent", "mortgage", "utilities"):
        check_amount(name, finances[name])
    
    for name, value in finances["living_expenses"].items():
        check_amount(f"living_expenses.{name}", value) # type: ignore
    for name, value in finances["subscriptions"].items():
        check_amount(f"subscriptions.{name}", value) # type: ignore
    for name, value in finances["insurance"].items():
        check_amount(f"insurance.{name}", value) # type: ignore


    minimums = finances["minimums"]["living_expenses"] # type: ignore
    for name in ("groceries", "transportation", "dining_out"):
        if name not in minimums:
            raise ValueError(f"Missing minimum living expense for {name}")
        
        value = minimums[name] # type: ignore
        check_amount(f"minimums.living_expenses.{name}", value) # type: ignore

        if value > finances["living_expenses"][name]: # type: ignore
            raise ValueError(f"Minimum living expense {name} is greater than the actual living expense.")

    if finances["rent"] > 0 and finances["mortgage"] > 0:
        raise ValueError("Cannot have both rent and mortgage greater than zero.")



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
    "minimums": {
        "living_expenses": {
            "groceries": 300,
            "transportation": 115,
            "dining_out": 50,
        }
    }
}