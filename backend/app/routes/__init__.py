from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import SessionLocal
from .. import models

router = APIRouter()


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 🔹 Create Order (Manual)
@router.post("/create")
def create_order(item_id: int, vendor_id: int, db: Session = Depends(get_db)):

    # Check item exists
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Check vendor exists
    vendor = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    # Create order
    order = models.Order(
        item_id=item_id,
        vendor_id=vendor_id,
        status="confirmed"
    )

    db.add(order)
    db.commit()
    db.refresh(order)

    return {
        "message": "Order placed successfully",
        "order_id": order.id,
        "item": item.name,
        "vendor": vendor.name,
        "price": vendor.price
    }


# 🔹 Get All Orders
@router.get("/")
def get_orders(db: Session = Depends(get_db)):
    orders = db.query(models.Order).all()

    results = []
    for order in orders:
        item = db.query(models.Item).filter(models.Item.id == order.item_id).first()
        vendor = db.query(models.Vendor).filter(models.Vendor.id == order.vendor_id).first()

        results.append({
            "order_id": order.id,
            "item": item.name if item else None,
            "vendor": vendor.name if vendor else None,
            "price": vendor.price if vendor else None,
            "status": order.status
        })

    return results


# 🔹 Delete Order (for testing/demo reset)
@router.delete("/{order_id}")
def delete_order(order_id: int, db: Session = Depends(get_db)):

    order = db.query(models.Order).filter(models.Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    db.delete(order)
    db.commit()

    return {"message": "Order deleted successfully"}