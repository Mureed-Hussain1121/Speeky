"""Password hashing, JWT issuance/verification, and secure token generation."""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from passlib.context import CryptContext

from app.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: Optional[str]) -> bool:
    if not password_hash:
        return False
    return _pwd_context.verify(password, password_hash)


# Password policy (ONB-US-03 E-02): min 8 chars, upper, lower, digit.
_PASSWORD_MIN_LEN = 8


def validate_password_policy(password: str) -> list[str]:
    """Return a list of unmet policy requirements (empty list == valid)."""
    problems: list[str] = []
    if len(password) < _PASSWORD_MIN_LEN:
        problems.append(f"At least {_PASSWORD_MIN_LEN} characters")
    if not re.search(r"[A-Z]", password):
        problems.append("At least one uppercase letter")
    if not re.search(r"[a-z]", password):
        problems.append("At least one lowercase letter")
    if not re.search(r"\d", password):
        problems.append("At least one number")
    return problems


# --------------------------------------------------------------------------- #
# One-time tokens (verification / reset) — stored raw but high-entropy.
# --------------------------------------------------------------------------- #
def generate_url_token() -> str:
    return secrets.token_urlsafe(32)


def hash_opaque_token(raw: str) -> str:
    """Deterministic hash for refresh tokens stored server-side."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# JWT access tokens
# --------------------------------------------------------------------------- #
def create_access_token(user_id: str, session_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "sid": session_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt.PyJWTError subclasses on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def generate_refresh_token() -> str:
    """Opaque high-entropy refresh token (raw value returned to the client only)."""
    return secrets.token_urlsafe(48)
