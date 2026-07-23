from datetime import datetime


def estimate_daily_usage(item_name, household):

    base_usage = {
        "rice": {"adult": 0.30, "child": 0.15},
        "wheat": {"adult": 0.25, "child": 0.12},
        "milk": {"adult": 0.40, "child": 0.35},
        "water": {"adult": 2.5, "child": 1.5},
        "dal": {"adult": 0.08, "child": 0.04}
    }

    item = item_name.lower()

    if item not in base_usage:
        return 0.2

    adult_usage = base_usage[item]["adult"] * household.adults
    child_usage = base_usage[item]["child"] * household.children

    total = adult_usage + child_usage

    # Light food habit adjustment
    if household.food_habit == "veg" and item in ["rice", "dal"]:
        total *= 1.1
    elif household.food_habit == "non-veg" and item in ["rice", "dal"]:
        total *= 0.9

    return round(total, 2)


def predict_status(item, household):

    base_estimate = estimate_daily_usage(item.name, household)

    # Adaptive learning
    days_passed = (datetime.utcnow() - item.last_updated).days

    if days_passed > 0:
        consumed = item.total_qty - item.remaining_qty

        if consumed > 0:
            historical_rate = consumed / days_passed
            daily_usage = (0.6 * historical_rate) + (0.4 * base_estimate)
        else:
            daily_usage = base_estimate
    else:
        daily_usage = base_estimate

    days_left = item.remaining_qty / daily_usage if daily_usage > 0 else 999

    if days_left > 5:
        status = "safe"
    elif 2 < days_left <= 5:
        status = "warning"
    else:
        status = "critical"

    return {
        "days_left": round(days_left, 2),
        "status": status,
        "estimated_daily_usage": round(daily_usage, 2)
    }