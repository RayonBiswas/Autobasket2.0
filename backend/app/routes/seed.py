from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import SessionLocal
from .. import models

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/vendors")
def seed_vendors(db: Session = Depends(get_db)):

    db.query(models.VendorItem).delete()
    db.query(models.Vendor).delete()

    # Vendors
    kirana = models.Vendor(name="Local Kirana", vendor_type="kirana", rating=4.2)
    blinkit = models.Vendor(name="Blinkit", vendor_type="ecommerce", rating=4.8)
    bigbasket = models.Vendor(name="BigBasket", vendor_type="regional", rating=4.5)

    db.add_all([kirana, blinkit, bigbasket])
    db.commit()

    # Items
    items = [
        # Kirana prices
        models.VendorItem(vendor_id=kirana.id, item_name="rice", price=48),
        models.VendorItem(vendor_id=kirana.id, item_name="milk", price=28),
        models.VendorItem(vendor_id=kirana.id, item_name="water", price=18),

        # Blinkit prices
        models.VendorItem(vendor_id=blinkit.id, item_name="rice", price=55),
        models.VendorItem(vendor_id=blinkit.id, item_name="milk", price=30),
        models.VendorItem(vendor_id=blinkit.id, item_name="water", price=20),

        # BigBasket prices
        models.VendorItem(vendor_id=bigbasket.id, item_name="rice", price=52),
        models.VendorItem(vendor_id=bigbasket.id, item_name="milk", price=29),
        models.VendorItem(vendor_id=bigbasket.id, item_name="water", price=19),
    ]

    db.add_all(items)
    db.commit()

    return {"message": "Sample vendors added"}