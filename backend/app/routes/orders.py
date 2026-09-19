from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..database import SessionLocal

router = APIRouter()   # 🔥 THIS LINE IS CRITICAL


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/create")
def create_order(item_id: int, vendor_id: int, db: Session = Depends(get_db)):

    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    vendor = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

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
        "order_id": order.id
    }


@router.get("/")
def get_orders(db: Session = Depends(get_db)):
    return db.query(models.Order).all()
