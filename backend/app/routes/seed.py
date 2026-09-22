"""Development-only seed data. Refused unless AUTH_DEV_MODE is on."""

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_household, get_db
from ..core.config import get_settings
from ..core.security import hash_device_token
from ..services.inventory import set_remaining

router = APIRouter()

# name, category, unit, pack_size, typical_full_grams, base_price ₹
PRODUCTS = [
    ("milk", "dairy", "l", 1, 1030, 60),
    ("curd", "dairy", "g", 400, 420, 35),
    ("paneer", "dairy", "g", 200, 210, 90),
    ("butter", "dairy", "g", 100, 110, 58),
    ("cheese", "dairy", "g", 200, 215, 130),
    ("eggs", "dairy", "pcs", 12, 720, 84),
    ("rice", "staples", "kg", 5, 5000, 320),
    ("wheat", "staples", "kg", 5, 5000, 240),
    ("dal", "staples", "kg", 1, 1000, 140),
    ("water", "beverages", "l", 20, 20000, 90),
    ("tomato", "vegetables", "kg", 1, 1000, 40),
    ("onion", "vegetables", "kg", 1, 1000, 35),
    ("potato", "vegetables", "kg", 1, 1000, 30),
    ("coriander", "vegetables", "g", 100, 100, 15),
    ("apple", "fruits", "kg", 1, 1000, 180),
    ("banana", "fruits", "pcs", 12, 1500, 60),
    ("bread", "bakery", "g", 400, 410, 45),
    ("juice", "beverages", "l", 1, 1050, 110),
    ("ketchup", "condiments", "g", 500, 540, 120),
    ("cola", "beverages", "l", 1.25, 1300, 80),
]

# name, kind, rating, eta_minutes, price multiplier vs base
VENDORS = [
    ("Local Kirana", models.VendorKind.KIRANA, 4.2, 25, 0.95),
    ("Blinkit", models.VendorKind.PLATFORM, 4.8, 12, 1.10),
    ("Zepto", models.VendorKind.PLATFORM, 4.6, 10, 1.08),
    ("Instamart", models.VendorKind.PLATFORM, 4.4, 15, 1.05),
    ("BigBasket", models.VendorKind.PLATFORM, 4.5, 120, 1.03),
]

INITIAL_STOCK = {"milk": 0.5, "rice": 0.25, "water": 0.9}
# Tray 1 slot positions that start out assigned and calibrated (tare = 50 g platform).
SLOT_ASSIGNMENTS = {1: "milk", 2: "rice", 3: "water"}
PLATFORM_TARE_GRAMS = 50.0


@router.post("/dev")
def seed_dev(household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    if not get_settings().auth_dev_mode:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seeding is only available in dev mode")

    products: dict[str, models.Product] = {}
    for name, category, unit, pack_size, full_grams, _ in PRODUCTS:
        product = db.query(models.Product).filter_by(name=name, brand=None, pack_size=pack_size).first()
        if product is None:
            product = models.Product(
                name=name, category=category, unit=unit, pack_size=pack_size, typical_full_grams=full_grams
            )
            db.add(product)
        products[name] = product
    db.flush()

    vendors: list[models.Vendor] = []
    for name, kind, rating, eta, multiplier in VENDORS:
        vendor = db.query(models.Vendor).filter_by(name=name).first()
        if vendor is None:
            vendor = models.Vendor(
                name=name, kind=kind, rating=rating, review_count=1, eta_minutes=eta, pincode=household.pincode
            )
            db.add(vendor)
            db.flush()
        vendors.append(vendor)
        for pname, *_rest, base_price in PRODUCTS:
            product = products[pname]
            offer = db.query(models.VendorOffer).filter_by(vendor_id=vendor.id, product_id=product.id).first()
            if offer is None:
                db.add(
                    models.VendorOffer(
                        vendor_id=vendor.id,
                        product_id=product.id,
                        price=round(base_price * multiplier, 2),
                        eta_minutes=eta,
                        source=models.OfferSource.SEED,
                    )
                )
    db.flush()

    device_token: str | None = None
    device = db.query(models.Device).filter_by(household_id=household.id, name="Dev Fridge").first()
    if device is None:
        device_token = secrets.token_urlsafe(32)
        device = models.Device(household_id=household.id, name="Dev Fridge", token_hash=hash_device_token(device_token))
        db.add(device)
        db.flush()
        for tray_pos in (1, 2):
            tray = models.Tray(device_id=device.id, position=tray_pos, label=f"Shelf {tray_pos}")
            db.add(tray)
            db.flush()
            for slot_pos in (1, 2, 3, 4):
                slot = models.Slot(tray_id=tray.id, position=slot_pos)
                pname = SLOT_ASSIGNMENTS.get(slot_pos) if tray_pos == 1 else None
                if pname:
                    product = products[pname]
                    slot.product_id = product.id
                    slot.tare_grams = PLATFORM_TARE_GRAMS
                    slot.full_grams = PLATFORM_TARE_GRAMS + (product.typical_full_grams or 1000)
                    db.add(slot)
                    db.flush()
                    grams = slot.tare_grams + INITIAL_STOCK[pname] * (slot.full_grams - slot.tare_grams)
                    db.add(models.SlotReading(slot_id=slot.id, weight_grams=round(grams, 1)))
                else:
                    db.add(slot)
    db.commit()

    for pname, fraction in INITIAL_STOCK.items():
        set_remaining(db, household, products[pname].id, fraction)

    return {
        "products": db.query(models.Product).count(),
        "vendors": len(vendors),
        "device_token": device_token,
        "message": "Dev data seeded" if device_token else "Dev data already present (device token not re-issued)",
    }
