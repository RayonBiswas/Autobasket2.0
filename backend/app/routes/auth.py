import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_household, current_user, get_db
from ..core.config import get_settings
from ..core.security import create_access_token, hash_otp

router = APIRouter()

OTP_WINDOW = timedelta(minutes=10)
OTP_MAX_PER_WINDOW = 5


class OtpRequest(BaseModel):
    email: EmailStr


class OtpVerify(BaseModel):
    email: EmailStr
    code: str


def send_otp(email: str, code: str) -> None:
    """Delivery hook. Dev mode logs it; Phase 6 wires email/SMS delivery here."""
    print(f"[auth] OTP for {email}: {code}")


def _as_utc(dt: datetime) -> datetime:
    # SQLite hands back naive datetimes; Postgres returns aware ones.
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


@router.post("/request-otp")
def request_otp(body: OtpRequest, db: Session = Depends(get_db)):
    settings = get_settings()
    email = body.email.lower()
    now = datetime.now(UTC)

    recent = (
        db.query(models.OtpCode)
        .filter(models.OtpCode.email == email, models.OtpCode.created_at >= now - OTP_WINDOW)
        .count()
    )
    if recent >= OTP_MAX_PER_WINDOW:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many codes requested; try again later")

    code = f"{secrets.randbelow(10**6):06d}"
    db.add(
        models.OtpCode(
            email=email,
            code_hash=hash_otp(email, code),
            expires_at=now + timedelta(minutes=settings.otp_ttl_minutes),
        )
    )
    db.commit()
    send_otp(email, code)

    if settings.auth_dev_mode:
        return {"dev_code": code}
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/verify-otp")
def verify_otp(body: OtpVerify, db: Session = Depends(get_db)):
    email = body.email.lower()
    now = datetime.now(UTC)

    candidate = (
        db.query(models.OtpCode)
        .filter(models.OtpCode.email == email, models.OtpCode.consumed_at.is_(None))
        .order_by(models.OtpCode.id.desc())
        .first()
    )
    if (
        candidate is None
        or _as_utc(candidate.expires_at) < now
        or candidate.code_hash != hash_otp(email, body.code)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired code")
    candidate.consumed_at = now

    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        user = models.User(email=email)
        household = models.Household(name=f"{email}'s home")
        db.add_all([user, household])
        db.flush()
        db.add(models.HouseholdMember(user_id=user.id, household_id=household.id, role=models.MemberRole.OWNER))
    else:
        household = user.memberships[0].household
    db.commit()

    return {
        "access_token": create_access_token(user.id, household.id),
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name},
        "household": {"id": household.id, "name": household.name},
    }


@router.get("/me")
def me(
    user: models.User = Depends(current_user),
    household: models.Household = Depends(current_household),
):
    return {
        "user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role},
        "household": {
            "id": household.id,
            "name": household.name,
            "adults": household.adults,
            "children": household.children,
            "food_habit": household.food_habit,
            "pincode": household.pincode,
            "priority": household.priority,
        },
        "memberships": [{"household_id": m.household_id, "role": m.role} for m in user.memberships],
    }
