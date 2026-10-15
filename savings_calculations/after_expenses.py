from savings_calculations.household import Finances, household, validate_finances

def calculate_after_expenses(finances: Finances) -> int:
    validate_finances(finances)

    total_expenses = (
        finances["rent"] + finances["mortgage"]
        + finances["utilities"] + sum(finances["living_expenses"].values()) # type: ignore
        + sum(finances["subscriptions"].values()) # type: ignore
        + sum(finances["insurance"].values()) # type: ignore
    )
    return finances["total_income"] - total_expenses

def max_savings(finances: Finances) -> int:
    validate_finances(finances)
    max_savings_amount = finances["total_income"] - (
        finances["rent"] + finances["mortgage"]
        + finances["utilities"] + sum(finances["minimums"]["living_expenses"].values()) # type: ignore
        + sum(finances["subscriptions"].values()) # type: ignore
        + sum(finances["insurance"].values()) # type: ignore 
    )
    return max_savings_amount


if __name__ == "__main__":
    after_expenses = calculate_after_expenses(household)
    print(f"After expenses, you have: ${after_expenses}")

    max_savings_amount = max_savings(household)
    print(f"Maximum savings possible: ${max_savings_amount}")
    print(f"Additional savings possible: ${max_savings_amount - after_expenses}")