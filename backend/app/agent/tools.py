from sqlalchemy.orm import Session
from datetime import datetime
from .. import models
from ..services.predictor import predict_status


# 1. Get pantry status
def get_pantry_status(db: Session):
    household = db.query(models.Household).first()
    if not household:
        household = models.Household(adults=2, children=1, food_habit="mixed")
        db.add(household)
        db.commit()
        db.refresh(household)

    items = db.query(models.Item).all()
    results = []
    for item in items:
        pred = predict_status(item, household)

        results.append({
            "id": item.id,
            "name": item.name,
            "total_qty": item.total_qty,
            "remaining_qty": item.remaining_qty,
            "min_threshold": item.min_threshold,
            "predicted_daily_usage": item.predicted_daily_usage,
            "days_left": pred["days_left"],
            "status": pred["status"],
            "last_updated": item.last_updated.isoformat() if item.last_updated else None
        })
    return {"inventory": results}


# 2. Get registered vendors
def get_vendors(db: Session):
    vendors = db.query(models.Vendor).all()
    return {"vendors": [{
        "id": v.id,
        "name": v.name,
        "rating": v.rating,
        "vendor_type": v.vendor_type,
        "review_count": v.review_count
    } for v in vendors]}


# 3. Compare prices for an item across vendors
def compare_prices(item_name: str, db: Session):
    cleaned_name = item_name.strip().lower()
    vendor_items = db.query(models.VendorItem).filter(
        models.VendorItem.item_name == cleaned_name
    ).all()

    if not vendor_items:
        return {"item": item_name, "message": "No vendor prices found for this item.", "comparison": []}

    prices = [vi.price for vi in vendor_items]
    min_price = min(prices)
    max_price = max(prices)

    results = []
    for vi in vendor_items:
        vendor = db.query(models.Vendor).filter(models.Vendor.id == vi.vendor_id).first()
        if not vendor:
            continue

        rating_score = vendor.rating / 5
        if max_price != min_price:
            price_score = 1 - ((vi.price - min_price) / (max_price - min_price))
        else:
            price_score = 1

        final_score = (0.4 * price_score) + (0.6 * rating_score)

        results.append({
            "vendor_id": vendor.id,
            "vendor_name": vendor.name,
            "rating": vendor.rating,
            "price": vi.price,
            "final_score": round(final_score, 2),
            "recommendation": "Best Match" if final_score >= 0.8 else ("Good Value" if vi.price == min_price else "Standard")
        })

    results.sort(key=lambda x: x["final_score"], reverse=True)
    return {"item": item_name, "comparison": results}


# 4. Place order (replenishes stock as well, subject to confirmation gate)
def place_pantry_order(item_name: str, vendor_name: str, db: Session):
    cleaned_item = item_name.strip().lower()
    item = db.query(models.Item).filter(models.Item.name == cleaned_item).first()
    if not item:
        return {"success": False, "error": f"Item '{item_name}' was not found in pantry inventory database."}

    cleaned_vendor = vendor_name.strip().lower()
    vendor = db.query(models.Vendor).filter(models.Vendor.name.ilike(cleaned_vendor)).first()
    if not vendor:
        return {"success": False, "error": f"Vendor '{vendor_name}' was not found in database."}

    price = 0.0
    price_rec = db.query(models.VendorItem).filter(
        models.VendorItem.vendor_id == vendor.id,
        models.VendorItem.item_name == item.name
    ).first()
    if price_rec:
        price = price_rec.price

    needs_confirmation = price > 50.0
    status = "pending_confirmation" if needs_confirmation else "confirmed"

    order = models.Order(
        item_id=item.id,
        vendor_id=vendor.id,
        status=status
    )
    db.add(order)

    if not needs_confirmation:
        item.remaining_qty = item.total_qty
        item.last_order_date = datetime.utcnow()
        item.last_updated = datetime.utcnow()

    db.commit()
    db.refresh(order)
    db.refresh(item)

    if needs_confirmation:
        return {
            "success": True,
            "needs_confirmation": True,
            "message": f"Order for '{item.name}' from '{vendor.name}' (price ₹{price}) exceeds the ₹50.0 auto-approve threshold and is pending confirmation.",
            "order_id": order.id,
            "new_remaining_qty": item.remaining_qty
        }
    return {
        "success": True,
        "needs_confirmation": False,
        "message": f"Successfully placed order for '{item.name}' from '{vendor.name}' (price ₹{price}).",
        "order_id": order.id,
        "new_remaining_qty": item.remaining_qty
    }


def confirm_pending_order(order_id: int, db: Session):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        return {"success": False, "needs_confirmation": False, "error": "Pending order not found."}

    if order.status != "pending_confirmation":
        return {"success": True, "needs_confirmation": False, "message": "Order already confirmed or completed.", "order_id": order.id}

    item = db.query(models.Item).filter(models.Item.id == order.item_id).first()
    if not item:
        return {"success": False, "needs_confirmation": False, "error": "Linked pantry item not found."}

    order.status = "confirmed"
    item.remaining_qty = item.total_qty
    item.last_order_date = datetime.utcnow()
    item.last_updated = datetime.utcnow()
    db.commit()
    db.refresh(order)
    db.refresh(item)

    return {
        "success": True,
        "needs_confirmation": False,
        "message": f"Order #{order.id} confirmed and stock replenished.",
        "order_id": order.id,
        "new_remaining_qty": item.remaining_qty
    }


# 5. Manually update quantity of pantry item
def update_item_qty(item_name: str, remaining_qty: float, db: Session):
    cleaned_item = item_name.strip().lower()
    item = db.query(models.Item).filter(models.Item.name == cleaned_item).first()
    if not item:
        item = models.Item(
            name=cleaned_item,
            total_qty=remaining_qty if remaining_qty > 0 else 10.0,
            remaining_qty=remaining_qty,
            min_threshold=2.0,
            last_updated=datetime.utcnow()
        )
        db.add(item)
    else:
        item.remaining_qty = remaining_qty
        if remaining_qty > item.total_qty:
            item.total_qty = remaining_qty
        item.last_updated = datetime.utcnow()

    db.commit()
    db.refresh(item)
    return {"success": True, "message": f"Updated '{item.name}' stock level to {item.remaining_qty}."}


# 6. Retrieve household information
def get_household_settings(db: Session):
    household = db.query(models.Household).first()
    if not household:
        household = models.Household(adults=2, children=1, food_habit="mixed")
        db.add(household)
        db.commit()
        db.refresh(household)

    return {
        "adults": household.adults,
        "children": household.children,
        "food_habit": household.food_habit
    }


# 7. Modify household parameters
def set_household_settings(adults: int, children: int, food_habit: str, db: Session):
    household = db.query(models.Household).first()
    if not household:
        household = models.Household(adults=adults, children=children, food_habit=food_habit)
        db.add(household)
    else:
        household.adults = adults
        household.children = children
        household.food_habit = food_habit

    db.commit()
    db.refresh(household)
    return {"success": True, "message": "Household parameters updated successfully.", "settings": {
        "adults": household.adults,
        "children": household.children,
        "food_habit": household.food_habit
    }}


# 8. Get recent orders with full join info
def get_recent_orders(db: Session):
    orders = db.query(models.Order).order_by(models.Order.id.desc()).all()
    results = []
    for order in orders:
        item = db.query(models.Item).filter(models.Item.id == order.item_id).first()
        vendor = db.query(models.Vendor).filter(models.Vendor.id == order.vendor_id).first()

        price_rec = None
        if item and vendor:
            price_rec = db.query(models.VendorItem).filter(
                models.VendorItem.vendor_id == vendor.id,
                models.VendorItem.item_name == item.name
            ).first()

        results.append({
            "order_id": order.id,
            "item_name": item.name if item else "Unknown",
            "vendor_name": vendor.name if vendor else "Unknown",
            "price": price_rec.price if price_rec else None,
            "status": order.status
        })
    return {"orders": results}


# 9. Build a shopping list from inventory that needs restocking
def build_shopping_list(db: Session, max_items: int = 5):
    pantry_status = get_pantry_status(db)
    needs_attention = [item for item in pantry_status["inventory"] if item["status"] in {"warning", "critical"}]
    needs_attention.sort(key=lambda item: (item["days_left"], item["remaining_qty"]))

    items = []
    for item in needs_attention[:max_items]:
        items.append({
            "name": item["name"],
            "days_left": item["days_left"],
            "remaining_qty": item["remaining_qty"],
            "priority": "urgent" if item["status"] == "critical" else "soon"
        })

    return {
        "shopping_list": items,
        "message": "Suggested restock priorities from pantry health analysis." if items else "No urgent restocks needed right now."
    }


# 10. Explain why an item is healthy or at risk
def explain_inventory(item_name: str | None, db: Session):
    pantry_status = get_pantry_status(db)
    if item_name:
        matches = [item for item in pantry_status["inventory"] if item["name"].lower() == item_name.strip().lower()]
    else:
        matches = pantry_status["inventory"]

    if not matches:
        return {"explanations": [], "message": f"No inventory found for '{item_name or 'the pantry'}'."}

    explanations = []
    for item in matches:
        if item["days_left"] <= 2:
            reason = "high risk"
        elif item["days_left"] <= 5:
            reason = "watch closely"
        else:
            reason = "healthy"
        explanations.append({
            "name": item["name"],
            "days_left": item["days_left"],
            "remaining_qty": item["remaining_qty"],
            "status": item["status"],
            "reason": reason,
            "summary": f"{item['name'].capitalize()} has {item['remaining_qty']}/{item['total_qty']} units left and is projected to last about {item['days_left']} days."
        })

    return {"explanations": explanations, "message": "Inventory explanation generated."}
