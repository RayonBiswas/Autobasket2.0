from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import ts_column, utcnow
from .enums import OrderChannel, OrderStatus

if TYPE_CHECKING:
    from .catalog import Product, Vendor


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"))
    status: Mapped[str] = mapped_column(String(24), default=OrderStatus.PROPOSED)
    channel: Mapped[str] = mapped_column(String(16), default=OrderChannel.KIRANA)
    total_amount: Mapped[float] = mapped_column(default=0.0)
    payment_ref: Mapped[str | None] = mapped_column(String(120))
    payment_url: Mapped[str | None] = mapped_column(String(500))
    handoff_url: Mapped[str | None] = mapped_column(String(500))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rating: Mapped[int | None]
    created_at: Mapped[datetime] = ts_column()
    updated_at: Mapped[datetime] = ts_column(onupdate=utcnow)

    vendor: Mapped["Vendor"] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    qty: Mapped[float] = mapped_column(default=1.0)
    unit_price: Mapped[float]

    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()
