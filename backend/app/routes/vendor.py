"""Kirana vendor portal: the shop owner's side of the marketplace.

Every route is scoped to the shop owned by the signed-in user (see api.deps.current_vendor).
"""

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_user, current_vendor, get_db
from ..models.base import utcnow
from ..services.orders import OPEN_FOR_VENDOR, IllegalTransition, order_row, transition

router = APIRouter()

HHMM = r"^\d{2}:\d{2}$"
PIN = r"^\d{6}$"


class ShopIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    pincode: str = Field(pattern=PIN)
    address: str | None = None
    phone: str | None = None
    lat: float | None = None
    lng: float | None = None
    opens_at: str | None = Field(default=None, pattern=HHMM)
    closes_at: str | None = Field(default=None, pattern=HHMM)
    eta_minutes: int | None = Field(default=30, ge=5, le=24 * 60)
    delivery_radius_km: float | None = Field(default=3.0, ge=0.5, le=50)
    min_order_amount: float = Field(default=0.0, ge=0)


class ShopUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    pincode: str | None = Field(default=None, pattern=PIN)
    address: str | None = None
    phone: str | None = None
    lat: float | None = None
    lng: float | None = None
    opens_at: str | None = Field(default=None, pattern=HHMM)
    closes_at: str | None = Field(default=None, pattern=HHMM)
    eta_minutes: int | None = Field(default=None, ge=5, le=24 * 60)
    delivery_radius_km: float | None = Field(default=None, ge=0.5, le=50)
    min_order_amount: float | None = Field(default=None, ge=0)
    is_active: bool | None = None


class OfferIn(BaseModel):
    product_id: int
    price: float = Field(gt=0)
    in_stock: bool = True
    eta_minutes: int | None = None


class OffersIn(BaseModel):
    offers: list[OfferIn] = Field(min_length=1)


def shop_row(db: Session, vendor: models.Vendor) -> dict:
    offer_count = db.query(models.VendorOffer).filter_by(vendor_id=vendor.id).count()
    open_orders = (
        db.query(models.Order)
        .filter(models.Order.vendor_id == vendor.id, models.Order.status.in_(OPEN_FOR_VENDOR))
        .count()
    )
    return {
        "id": vendor.id,
        "name": vendor.name,
        "kind": vendor.kind,
        "pincode": vendor.pincode,
        "address": vendor.address,
        "phone": vendor.phone,
        "lat": vendor.lat,
        "lng": vendor.lng,
        "opens_at": vendor.opens_at,
        "closes_at": vendor.closes_at,
        "eta_minutes": vendor.eta_minutes,
        "delivery_radius_km": vendor.delivery_radius_km,
        "min_order_amount": vendor.min_order_amount,
        "rating": vendor.rating,
        "review_count": vendor.review_count,
        "service_score": vendor.service_score,
        "is_active": vendor.is_active,
        "offer_count": offer_count,
        "open_orders": open_orders,
    }


# ---------- shop profile ----------


@router.post("/shop", status_code=201)
def create_shop(body: ShopIn, user: models.User = Depends(current_user), db: Session = Depends(get_db)):
    if db.query(models.Vendor).filter(models.Vendor.owner_user_id == user.id).first():
        raise HTTPException(409, "You already have a shop")
    vendor = models.Vendor(kind=models.VendorKind.KIRANA, owner_user_id=user.id, **body.model_dump())
    user.role = models.UserRole.VENDOR
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return shop_row(db, vendor)


@router.get("/shop")
def get_shop(vendor: models.Vendor = Depends(current_vendor), db: Session = Depends(get_db)):
    return shop_row(db, vendor)


@router.put("/shop")
def update_shop(body: ShopUpdate, vendor: models.Vendor = Depends(current_vendor), db: Session = Depends(get_db)):
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(vendor, key, value)
    db.commit()
    db.refresh(vendor)
    return shop_row(db, vendor)


# ---------- listings ----------


def _offer_row(offer: models.VendorOffer) -> dict:
    p = offer.product
    return {
        "product_id": offer.product_id,
        "name": p.name,
        "brand": p.brand,
        "category": p.category,
        "unit": p.unit,
        "pack_size": p.pack_size,
        "price": offer.price,
        "in_stock": offer.in_stock,
        "eta_minutes": offer.eta_minutes,
        "updated_at": offer.fetched_at.isoformat() if offer.fetched_at else None,
    }


@router.get("/catalog")
def catalog(
    q: str = Query(default="", max_length=60),
    vendor: models.Vendor = Depends(current_vendor),
    db: Session = Depends(get_db),
):
    """The shared product catalog, with this shop's price where it already lists the item."""
    query = db.query(models.Product)
    if q.strip():
        query = query.filter(models.Product.name.ilike(f"%{q.strip()}%"))
    products = query.order_by(models.Product.category, models.Product.name).all()
    mine = {o.product_id: o for o in db.query(models.VendorOffer).filter_by(vendor_id=vendor.id).all()}
    return {
        "products": [
            {
                "id": p.id,
                "name": p.name,
                "brand": p.brand,
                "category": p.category,
                "unit": p.unit,
                "pack_size": p.pack_size,
                "price": mine[p.id].price if p.id in mine else None,
                "in_stock": mine[p.id].in_stock if p.id in mine else None,
            }
            for p in products
        ]
    }


@router.get("/offers")
def list_offers(vendor: models.Vendor = Depends(current_vendor), db: Session = Depends(get_db)):
    offers = (
        db.query(models.VendorOffer)
        .join(models.Product)
        .filter(models.VendorOffer.vendor_id == vendor.id)
        .order_by(models.Product.category, models.Product.name)
        .all()
    )
    return {"offers": [_offer_row(o) for o in offers]}


def _upsert(db: Session, vendor: models.Vendor, product_id: int, price: float, in_stock: bool, eta: int | None) -> bool:
    """Returns True when a new offer was created, False when an existing one was updated."""
    offer = db.query(models.VendorOffer).filter_by(vendor_id=vendor.id, product_id=product_id).first()
    created = offer is None
    if created:
        offer = models.VendorOffer(vendor_id=vendor.id, product_id=product_id)
        db.add(offer)
    offer.price = round(price, 2)
    offer.in_stock = in_stock
    offer.eta_minutes = eta
    offer.source = models.OfferSource.PORTAL
    offer.fetched_at = utcnow()
    return created


@router.put("/offers")
def upsert_offers(body: OffersIn, vendor: models.Vendor = Depends(current_vendor), db: Session = Depends(get_db)):
    wanted = [o.product_id for o in body.offers]
    known = {pid for (pid,) in db.query(models.Product.id).filter(models.Product.id.in_(wanted))}
    missing = [pid for pid in wanted if pid not in known]
    if missing:
        raise HTTPException(422, f"Unknown product ids: {missing}")
    for o in body.offers:
        _upsert(db, vendor, o.product_id, o.price, o.in_stock, o.eta_minutes)
    db.commit()
    return {"saved": len(body.offers)}


@router.delete("/offers/{product_id}", status_code=204)
def delete_offer(product_id: int, vendor: models.Vendor = Depends(current_vendor), db: Session = Depends(get_db)):
    offer = db.query(models.VendorOffer).filter_by(vendor_id=vendor.id, product_id=product_id).first()
    if offer is None:
        raise HTTPException(404, "You do not list this product")
    db.delete(offer)
    db.commit()


TRUE_WORDS = {"", "1", "y", "yes", "true", "in", "in stock", "instock"}


@router.post("/offers/csv")
async def upload_csv(file: UploadFile, vendor: models.Vendor = Depends(current_vendor), db: Session = Depends(get_db)):
    """Columns: product, price, in_stock (optional). Product is matched by name, case-insensitive."""
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(422, "The file must be UTF-8 text") from exc
    reader = csv.DictReader(io.StringIO(text))
    cols = {c.strip().lower() for c in (reader.fieldnames or [])}
    if not {"product", "price"} <= cols:
        raise HTTPException(422, "The CSV needs 'product' and 'price' columns")

    by_name = {p.name.lower(): p for p in db.query(models.Product).all()}
    added = updated = 0
    unknown: list[str] = []
    for raw_row in reader:
        row = {k.strip().lower(): (v or "").strip() for k, v in raw_row.items() if k}
        name = row.get("product", "")
        if not name:
            continue
        product = by_name.get(name.lower())
        try:
            price = float(row.get("price", ""))
        except ValueError:
            price = 0.0
        if product is None or price <= 0:
            unknown.append(name)
            continue
        in_stock = row.get("in_stock", "").lower() in TRUE_WORDS
        if _upsert(db, vendor, product.id, price, in_stock, None):
            added += 1
        else:
            updated += 1
    db.commit()
    return {"added": added, "updated": updated, "unknown": unknown}


# ---------- order inbox ----------


@router.get("/orders")
def inbox(
    status: str = Query(default="open", pattern="^(open|all)$"),
    vendor: models.Vendor = Depends(current_vendor),
    db: Session = Depends(get_db),
):
    query = db.query(models.Order).filter(models.Order.vendor_id == vendor.id)
    if status == "open":
        query = query.filter(models.Order.status.in_(OPEN_FOR_VENDOR))
    orders = query.order_by(models.Order.id.desc()).limit(200).all()
    return {"orders": [order_row(o) for o in orders]}


def _shop_order(db: Session, vendor: models.Vendor, order_id: int) -> models.Order:
    order = db.get(models.Order, order_id)
    if order is None or order.vendor_id != vendor.id or order.status not in OPEN_FOR_VENDOR:
        raise HTTPException(404, "Order not found")
    return order


def _move(db: Session, order: models.Order, new_status: str) -> dict:
    try:
        transition(order, new_status)
    except IllegalTransition as exc:
        raise HTTPException(409, str(exc)) from exc
    db.commit()
    db.refresh(order)
    return order_row(order)


@router.post("/orders/{order_id}/accept")
def accept_order(order_id: int, vendor: models.Vendor = Depends(current_vendor), db: Session = Depends(get_db)):
    return _move(db, _shop_order(db, vendor, order_id), models.OrderStatus.ACCEPTED)


@router.post("/orders/{order_id}/reject")
def reject_order(order_id: int, vendor: models.Vendor = Depends(current_vendor), db: Session = Depends(get_db)):
    return _move(db, _shop_order(db, vendor, order_id), models.OrderStatus.CANCELLED)


@router.post("/orders/{order_id}/deliver")
def deliver_order(order_id: int, vendor: models.Vendor = Depends(current_vendor), db: Session = Depends(get_db)):
    return _move(db, _shop_order(db, vendor, order_id), models.OrderStatus.DELIVERED)
