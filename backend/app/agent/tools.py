"""Tools the chat agent can call. Every tool is scoped to the caller's household."""

from sqlalchemy.orm import Session

from .. import models
from ..services.inventory import find_product, list_states, set_remaining
from ..services.ranking import offers_for_product, rank_offers

# Orders above this amount need an explicit "yes" from the user (the guardrail).
AUTO_APPROVE_LIMIT = 50.0


# 1. Get pantry status
def get_pantry_status(db: Session, household: models.Household):
    return {"inventory": list_states(db, household)}


# 2. Get registered vendors
def get_vendors(db: Session):
    vendors = db.query(models.Vendor).filter(models.Vendor.is_active.is_(True)).all()
    return {
        "vendors": [
            {"id": v.id, "name": v.name, "rating": v.rating, "vendor_type": v.kind, "review_count": v.review_count}
            for v in vendors
        ]
    }


# 3. Compare prices for an item across vendors
def compare_prices(item_name: str, db: Session, household: models.Household):
    product = find_product(db, item_name)
    if product is None:
        return {"item": item_name, "message": "No such product in the catalog.", "comparison": []}
    comparison = rank_offers(offers_for_product(db, product))
    if not comparison:
        return {"item": item_name, "message": "No vendor prices found for this item.", "comparison": []}
    return {"item": item_name, "comparison": comparison}


def _find_vendor(db: Session, vendor_name: str) -> models.Vendor | None:
    return db.query(models.Vendor).filter(models.Vendor.name.ilike(vendor_name.strip())).first()


# 4. Place order (replenishes stock as well, subject to confirmation gate)
def place_pantry_order(item_name: str, vendor_name: str, db: Session, household: models.Household):
    product = find_product(db, item_name)
    if product is None:
        return {"success": False, "error": f"Item '{item_name}' was not found in the catalog."}

    vendor = _find_vendor(db, vendor_name)
    if vendor is None:
        return {"success": False, "error": f"Vendor '{vendor_name}' was not found."}

    offer = db.query(models.VendorOffer).filter_by(vendor_id=vendor.id, product_id=product.id).first()
    price = offer.price if offer else 0.0

    needs_confirmation = price > AUTO_APPROVE_LIMIT
    order = models.Order(
        household_id=household.id,
        vendor_id=vendor.id,
        status=models.OrderStatus.PENDING_CONFIRMATION if needs_confirmation else models.OrderStatus.CONFIRMED,
        channel=models.OrderChannel.KIRANA if vendor.kind == models.VendorKind.KIRANA else models.OrderChannel.HANDOFF,
        total_amount=price,
    )
    order.items.append(models.OrderItem(product_id=product.id, qty=1, unit_price=price))
    db.add(order)
    db.commit()
    db.refresh(order)

    if needs_confirmation:
        return {
            "success": True,
            "needs_confirmation": True,
            "message": (
                f"Order for '{product.name}' from '{vendor.name}' (price ₹{price}) exceeds the "
                f"₹{AUTO_APPROVE_LIMIT} auto-approve threshold and is pending confirmation."
            ),
            "order_id": order.id,
        }

    state = set_remaining(db, household, product.id, 1.0, source=models.EventSource.ORDER)
    return {
        "success": True,
        "needs_confirmation": False,
        "message": f"Successfully placed order for '{product.name}' from '{vendor.name}' (price ₹{price}).",
        "order_id": order.id,
        "new_remaining_qty": round(state.remaining_fraction * product.pack_size, 2),
    }


def confirm_pending_order(order_id: int, db: Session, household: models.Household):
    order = db.get(models.Order, order_id)
    if order is None or order.household_id != household.id:
        return {"success": False, "needs_confirmation": False, "error": "Pending order not found."}

    if order.status != models.OrderStatus.PENDING_CONFIRMATION:
        return {
            "success": True,
            "needs_confirmation": False,
            "message": "Order already confirmed or completed.",
            "order_id": order.id,
        }

    order.status = models.OrderStatus.CONFIRMED
    db.commit()
    new_qty = None
    for line in order.items:
        state = set_remaining(db, household, line.product_id, 1.0, source=models.EventSource.ORDER)
        new_qty = round(state.remaining_fraction * line.product.pack_size, 2)

    return {
        "success": True,
        "needs_confirmation": False,
        "message": f"Order #{order.id} confirmed and stock replenished.",
        "order_id": order.id,
        "new_remaining_qty": new_qty,
    }


# 5. Manually update quantity of pantry item (remaining_qty in the product's pack unit)
def update_item_qty(item_name: str, remaining_qty: float, db: Session, household: models.Household):
    product = find_product(db, item_name)
    if product is None:
        return {"success": False, "error": f"Item '{item_name}' is not in the catalog."}
    fraction = remaining_qty / product.pack_size if product.pack_size else 0.0
    state = set_remaining(db, household, product.id, fraction)
    return {
        "success": True,
        "message": f"Updated '{product.name}' stock level to {round(state.remaining_fraction * product.pack_size, 2)} {product.unit}.",
    }


# 6. Retrieve household information
def get_household_settings(db: Session, household: models.Household):
    return {"adults": household.adults, "children": household.children, "food_habit": household.food_habit}


# 7. Modify household parameters
def set_household_settings(adults: int, children: int, food_habit: str, db: Session, household: models.Household):
    household.adults = adults
    household.children = children
    household.food_habit = food_habit
    db.commit()
    return {
        "success": True,
        "message": "Household parameters updated successfully.",
        "settings": get_household_settings(db, household),
    }


# 8. Get recent orders
def get_recent_orders(db: Session, household: models.Household):
    orders = (
        db.query(models.Order)
        .filter(models.Order.household_id == household.id)
        .order_by(models.Order.id.desc())
        .limit(20)
        .all()
    )
    return {
        "orders": [
            {
                "order_id": o.id,
                "item_name": ", ".join(i.product.name for i in o.items) or "Unknown",
                "vendor_name": o.vendor.name if o.vendor else "Unknown",
                "price": o.total_amount,
                "status": o.status,
            }
            for o in orders
        ]
    }


# 9. Build a shopping list from inventory that needs restocking
def build_shopping_list(db: Session, household: models.Household, max_items: int = 5):
    inventory = get_pantry_status(db, household)["inventory"]
    needs_attention = [row for row in inventory if row["status"] in {"warning", "critical"}]
    needs_attention.sort(key=lambda row: (row["days_left"], row["remaining_qty"]))

    items = [
        {
            "name": row["name"],
            "days_left": row["days_left"],
            "remaining_qty": row["remaining_qty"],
            "priority": "urgent" if row["status"] == "critical" else "soon",
        }
        for row in needs_attention[:max_items]
    ]
    return {
        "shopping_list": items,
        "message": "Suggested restock priorities from pantry health analysis."
        if items
        else "No urgent restocks needed right now.",
    }


# 10. Explain why an item is healthy or at risk
def explain_inventory(item_name: str | None, db: Session, household: models.Household):
    inventory = get_pantry_status(db, household)["inventory"]
    if item_name:
        matches = [row for row in inventory if row["name"].lower() == item_name.strip().lower()]
    else:
        matches = inventory

    if not matches:
        return {"explanations": [], "message": f"No inventory found for '{item_name or 'the pantry'}'."}

    explanations = []
    for row in matches:
        if row["days_left"] <= 2:
            reason = "high risk"
        elif row["days_left"] <= 5:
            reason = "watch closely"
        else:
            reason = "healthy"
        explanations.append(
            {
                "name": row["name"],
                "days_left": row["days_left"],
                "remaining_qty": row["remaining_qty"],
                "status": row["status"],
                "reason": reason,
                "summary": (
                    f"{row['name'].capitalize()} has {row['remaining_qty']}/{row['pack_size']} {row['unit']} left "
                    f"and is projected to last about {row['days_left']} days."
                ),
            }
        )
    return {"explanations": explanations, "message": "Inventory explanation generated."}
