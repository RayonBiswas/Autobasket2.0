from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .base import ts_column
from .enums import MemberRole, UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True)
    name: Mapped[str | None] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(16), default=UserRole.HOUSEHOLD)
    created_at: Mapped[datetime] = ts_column()

    memberships: Mapped[list["HouseholdMember"]] = relationship(back_populates="user")


class OtpCode(Base):
    __tablename__ = "otp_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = ts_column()


class Household(Base):
    __tablename__ = "households"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    pincode: Mapped[str | None] = mapped_column(String(10))
    lat: Mapped[float | None]
    lng: Mapped[float | None]
    adults: Mapped[int] = mapped_column(default=2)
    children: Mapped[int] = mapped_column(default=1)
    food_habit: Mapped[str] = mapped_column(String(16), default="mixed")
    # What matters most when we rank shops: balanced | price | speed (see services/ranking.WEIGHTS).
    priority: Mapped[str] = mapped_column(String(12), default="balanced")
    created_at: Mapped[datetime] = ts_column()

    members: Mapped[list["HouseholdMember"]] = relationship(back_populates="household")


class HouseholdMember(Base):
    __tablename__ = "household_members"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), default=MemberRole.MEMBER)

    user: Mapped["User"] = relationship(back_populates="memberships")
    household: Mapped["Household"] = relationship(back_populates="members")
