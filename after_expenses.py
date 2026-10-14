from household import Finances, household, validate_finances

def calculate_after_expenses(finances: Finances) -> int:
    validate_finances(finances)



    total_expenses = (
        finances["rent"] + finances["mortgage"]
        + finances["utilities"] + sum(finances["living_expenses"].values()) # type: ignore
        + sum(finances["subscriptions"].values()) # type: ignore
        + sum(finances["insurance"].values()) # type: ignore
    )
    return finances["total_income"] - total_expenses

if __name__ == "__main__":
    after_expenses = calculate_after_expenses(household)
    print(f"After expenses, you have: ${after_expenses}")