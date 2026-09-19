from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import ts_column


class Device(Base):
    """One physical fridge controller (Raspberry Pi). Authenticates with a bearer token; only its hash is stored."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = ts_column()

    trays: Mapped[list["Tray"]] = relationship(back_populates="device", order_by="Tray.position")


class Tray(Base):
    __tablename__ = "trays"
    __table_args__ = (UniqueConstraint("device_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    position: Mapped[int]
    label: Mapped[str | None] = mapped_column(String(60))

    device: Mapped["Device"] = relationship(back_populates="trays")
    slots: Mapped[list["Slot"]] = relationship(back_populates="tray", order_by="Slot.position")


class Slot(Base):
    """One load cell. remaining = (weight - tare_grams) / (full_grams - tare_grams)."""

    __tablename__ = "slots"
    __table_args__ = (UniqueConstraint("tray_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tray_id: Mapped[int] = mapped_column(ForeignKey("trays.id"), index=True)
    position: Mapped[int]
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    tare_grams: Mapped[float | None]
    full_grams: Mapped[float | None]

    tray: Mapped["Tray"] = relationship(back_populates="slots")
    readings: Mapped[list["SlotReading"]] = relationship(order_by="SlotReading.recorded_at.desc()")


class SlotReading(Base):
    """One raw weight sample from one load cell. Calibration and learning read these."""

    __tablename__ = "slot_readings"
    __table_args__ = (Index("ix_slot_readings_slot_time", "slot_id", "recorded_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"))
    weight_grams: Mapped[float]
    recorded_at: Mapped[datetime] = ts_column()
