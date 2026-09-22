from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import ts_column
from .enums import OfferSource, VendorKind


class Product(Base):
    """Canonical catalog entry, e.g. name="milk", brand="Amul Taaza", pack_size=1, unit="l"."""

    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("name", "brand", "pack_size"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    brand: Mapped[str | None] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(40))
    unit: Mapped[str] = mapped_column(String(8))
    pack_size: Mapped[float]
    typical_full_grams: Mapped[float | None]
    created_at: Mapped[datetime] = ts_column()


class Vendor(Base):
    """A seller: a kirana on our own marketplace, or an external platform (Blinkit, Zepto, ...)."""

    __tablename__ = "vendors"
    __table_args__ = (UniqueConstraint("owner_user_id", name="uq_vendors_owner_user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    kind: Mapped[str] = mapped_column(String(16), default=VendorKind.KIRANA)
    # One shop per login: the kirana owner who manages this listing in the portal.
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    pincode: Mapped[str | None] = mapped_column(String(10))
    lat: Mapped[float | None]
    lng: Mapped[float | None]
    address: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    rating: Mapped[float] = mapped_column(default=4.0)
    review_count: Mapped[int] = mapped_column(default=0)
    service_score: Mapped[float] = mapped_column(default=0.5)
    eta_minutes: Mapped[int | None]
    delivery_radius_km: Mapped[float | None]
    opens_at: Mapped[str | None] = mapped_column(String(5))  # "HH:MM" local time
    closes_at: Mapped[str | None] = mapped_column(String(5))
    min_order_amount: Mapped[float] = mapped_column(default=0.0)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = ts_column()

    offers: Mapped[list["VendorOffer"]] = relationship(back_populates="vendor")


class VendorOffer(Base):
    """Current price of one product at one vendor."""

    __tablename__ = "vendor_offers"
    __table_args__ = (UniqueConstraint("vendor_id", "product_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    price: Mapped[float]
    in_stock: Mapped[bool] = mapped_column(default=True)
    eta_minutes: Mapped[int | None]
    source: Mapped[str] = mapped_column(String(16), default=OfferSource.PORTAL)
    fetched_at: Mapped[datetime] = ts_column()

    vendor: Mapped["Vendor"] = relationship(back_populates="offers")
    product: Mapped["Product"] = relationship()
