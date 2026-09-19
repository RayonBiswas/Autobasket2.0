from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import ts_column, utcnow
from .enums import EventSource, StockStatus

if TYPE_CHECKING:
    from .catalog import Product


class InventoryEvent(Base):
    """Every observation of how much of a product is left. This is the history the predictor learns from."""

    __tablename__ = "inventory_events"
    __table_args__ = (Index("ix_inventory_events_hh_prod_time", "household_id", "product_id", "recorded_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    slot_id: Mapped[int | None] = mapped_column(ForeignKey("slots.id"))
    source: Mapped[str] = mapped_column(String(16), default=EventSource.MANUAL)
    weight_grams: Mapped[float | None]
    remaining_fraction: Mapped[float]
    recorded_at: Mapped[datetime] = ts_column()


class InventoryState(Base):
    """Latest known state per household x product, plus the prediction derived from it."""

    __tablename__ = "inventory_state"
    __table_args__ = (UniqueConstraint("household_id", "product_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    remaining_fraction: Mapped[float] = mapped_column(default=1.0)
    daily_rate: Mapped[float | None]
    # Where daily_rate came from: confidence 0..1, method prior|blended|learned, days of history counted.
    rate_confidence: Mapped[float | None]
    rate_method: Mapped[str | None] = mapped_column(String(12))
    observed_days: Mapped[float | None]
    days_left: Mapped[float | None]
    status: Mapped[str] = mapped_column(String(16), default=StockStatus.UNKNOWN)
    updated_at: Mapped[datetime] = ts_column(onupdate=utcnow)

    product: Mapped["Product"] = relationship()
