"""Phase-1 predictor: household-size prior only. Phase 3 replaces this with rates learned from inventory_events."""

# Typical daily use per person, in the product's pack unit (kg or l).
BASE_USAGE = {
    "rice": {"adult": 0.30, "child": 0.15},
    "wheat": {"adult": 0.25, "child": 0.12},
    "milk": {"adult": 0.40, "child": 0.35},
    "water": {"adult": 2.5, "child": 1.5},
    "dal": {"adult": 0.08, "child": 0.04},
}
DEFAULT_DAILY_USAGE = 0.2


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


def status_for(days_left: float) -> str:
    if days_left > 5:
        return "safe"
    if days_left > 2:
        return "warning"
    return "critical"


def predict_state(state, product, household) -> dict:
    """days_left / status for one inventory row. Uses a learned daily_rate when present, else the prior."""
    daily = state.daily_rate or estimate_daily_usage(product.name, household)
    remaining = state.remaining_fraction * product.pack_size
    days_left = remaining / daily if daily > 0 else 999
    return {
        "days_left": round(days_left, 2),
        "status": status_for(days_left),
        "estimated_daily_usage": round(daily, 2),
    }
