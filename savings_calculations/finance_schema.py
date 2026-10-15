from typing import TypedDict

class LivingExpenses(TypedDict):
    groceries: int
    transportation: int
    dining_out: int

class Subscriptions(TypedDict):
    internet: int
    streaming_services: int
    fitness: int

class Insurance(TypedDict):
    health: int
    auto: int
    home: int

class Minimums(TypedDict):
    living_expenses: LivingExpenses

class Finances(TypedDict):
    total_income: int
    rent: int
    mortgage: int
    utilities: int
    living_expenses: LivingExpenses
    subscriptions: Subscriptions
    insurance: Insurance
    minimums: Minimums

