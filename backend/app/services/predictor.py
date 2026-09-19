"""Turns a remaining amount and a daily rate into 'runs out in N days' and a status.

The daily rate comes from services/consumption (learned from history) with the household-size prior below as
the cold-start guess.
"""

# Typical daily use per person, in the product's pack unit (kg or l).
BASE_USAGE = {
    "rice": {"adult": 0.30, "child": 0.15},
    "wheat": {"adult": 0.25, "child": 0.12},
    "milk": {"adult": 0.40, "child": 0.35},
    "water": {"adult": 2.5, "child": 1.5},
    "dal": {"adult": 0.08, "child": 0.04},
}
DEFAULT_DAILY_USAGE = 0.2

# Reorder when the item will not outlast a delivery plus one day of margin.
LEAD_TIME_DAYS = 1.0
SAFETY_DAYS = 1.0
WARNING_DAYS = 5.0


def estimate_daily_usage(product_name: str, household) -> float:
    """Daily consumption guess from household size and diet, in pack units per day."""
    item = product_name.lower()
    if item not in BASE_USAGE:
        return DEFAULT_DAILY_USAGE

    total = BASE_USAGE[item]["adult"] * household.adults + BASE_USAGE[item]["child"] * household.children

    if household.food_habit == "veg" and item in {"rice", "dal"}:
        total *= 1.1
    elif household.food_habit == "non-veg" and item in {"rice", "dal"}:
        total *= 0.9

    return round(total, 2)


def needs_reorder(days_left: float) -> bool:
    return days_left <= LEAD_TIME_DAYS + SAFETY_DAYS


def status_for(days_left: float) -> str:
    if needs_reorder(days_left):
        return "critical"
    if days_left <= WARNING_DAYS:
        return "warning"
    return "safe"


def predict_state(state, product, household) -> dict:
    """days_left / status / needs_reorder for one inventory row."""
    daily = state.daily_rate if state.daily_rate is not None else estimate_daily_usage(product.name, household)
    remaining = state.remaining_fraction * product.pack_size
    days_left = remaining / daily if daily > 0 else 999
    return {
        "days_left": round(days_left, 2),
        "status": status_for(days_left),
        "needs_reorder": needs_reorder(days_left),
        "estimated_daily_usage": round(daily, 3),
    }
