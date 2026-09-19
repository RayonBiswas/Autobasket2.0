"""FastAPI dependencies shared by every router: DB session and the authenticated caller."""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .. import models
from ..core.security import decode_access_token, hash_device_token
from ..database import get_db

bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


def _payload(creds: HTTPAuthorizationCredentials | None) -> dict:
    if creds is None:
        raise _unauthorized()
    try:
        return decode_access_token(creds.credentials)
    except jwt.PyJWTError as exc:
        raise _unauthorized("Invalid or expired token") from exc


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> models.User:
    user = db.get(models.User, int(_payload(creds)["sub"]))
    if user is None:
        raise _unauthorized("Unknown user")
    return user


def current_household(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> models.Household:
    payload = _payload(creds)
    membership = db.get(models.HouseholdMember, (int(payload["sub"]), int(payload["hid"])))
    if membership is None:
        raise _unauthorized("Not a member of this household")
    return membership.household


def current_device(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> models.Device:
    if creds is None:
        raise _unauthorized()
    device = db.query(models.Device).filter(models.Device.token_hash == hash_device_token(creds.credentials)).first()
    if device is None:
        raise _unauthorized("Unknown device")
    return device


__all__ = ["get_db", "current_user", "current_household", "current_device"]
