from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import ts_column


class Notification(Base):
    """What we asked the household and what they answered. Channels (in-app, Telegram) only deliver these."""

    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_household_answered", "household_id", "responded_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    channel: Mapped[str] = mapped_column(String(12), default="inapp")
    kind: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    payload: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    sent_at: Mapped[datetime] = ts_column()
    response: Mapped[str | None] = mapped_column(String(16))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
