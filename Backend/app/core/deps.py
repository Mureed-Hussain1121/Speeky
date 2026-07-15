"""FastAPI dependencies: authenticated-user resolution from a bearer token."""
from __future__ import annotations

from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models import DeviceSession, User
from app.models.common import utcnow

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from an `Authorization: Bearer <jwt>` header.

    Enforces ONB-US-06 (E-06 expired/tampered token -> silent 401) and ensures the
    backing session has not been revoked (remote logout / password reset).
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _UNAUTHORIZED
    token = authorization.split(" ", 1)[1].strip()

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        # Expired or tampered token -> silently invalidate (no internal details leaked).
        raise _UNAUTHORIZED

    if payload.get("type") != "access":
        raise _UNAUTHORIZED

    user_id = payload.get("sub")
    session_id = payload.get("sid")
    if not user_id or not session_id:
        raise _UNAUTHORIZED

    session = db.get(DeviceSession, session_id)
    if session is None or not session.is_active(utcnow()):
        raise _UNAUTHORIZED

    user = db.get(User, user_id)
    if user is None or user.is_deleted:
        raise _UNAUTHORIZED

    # Expose the active session id so routers can special-case "current device".
    user.__dict__["_current_session_id"] = session_id
    return user


def current_session_id(user: User) -> Optional[str]:
    return user.__dict__.get("_current_session_id")
