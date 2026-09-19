import hashlib
from datetime import UTC, datetime, timedelta

import jwt

from .config import get_settings


def hash_otp(email: str, code: str) -> str:
    """One-way hash of an OTP so a leaked database does not leak live codes."""
    secret = get_settings().jwt_secret
    return hashlib.sha256(f"{email.lower()}:{code}:{secret}".encode()).hexdigest()


def hash_device_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: int, household_id: int) -> str:
    s = get_settings()
    payload = {
        "sub": str(user_id),
        "hid": household_id,
        "exp": datetime.now(UTC) + timedelta(hours=s.jwt_expires_hours),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError on a bad or expired token."""
    return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
