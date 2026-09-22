from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from .base import ts_column


class VisionResult(Base):
    """What the camera model said was in one slot of one tray, for suggestions, mismatch alerts and audit.

    The photo itself is not kept; image_sha lets us tell two photos apart."""

    __tablename__ = "vision_results"
    __table_args__ = (Index("ix_vision_results_tray_time", "tray_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tray_id: Mapped[int] = mapped_column(ForeignKey("trays.id"))
    slot_position: Mapped[int]
    product_guess: Mapped[str] = mapped_column(String(80))
    matched_product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    confidence: Mapped[float] = mapped_column(default=0.0)
    image_sha: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = ts_column()
