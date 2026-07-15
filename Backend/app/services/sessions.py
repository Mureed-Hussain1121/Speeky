"""Device-session lifecycle: creation, refresh-token lookup, and revocation."""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_opaque_token,
)
from app.models import DeviceSession, User
from app.models.common import utcnow


def _device_label_from_agent(user_agent: Optional[str]) -> str:
    """Best-effort human label from a User-Agent string (no geo-IP in scope)."""
    if not user_agent:
        return "Unknown device"
    ua = user_agent.lower()
    if "iphone" in ua or "ios" in ua:
        return "iPhone / iOS"
    if "ipad" in ua:
        return "iPad"
    if "android" in ua:
        return "Android device"
    if "windows" in ua:
        return "Windows PC"
    if "mac os" in ua or "macintosh" in ua:
        return "Mac"
    if "linux" in ua:
        return "Linux device"
    return user_agent[:60]


def is_known_device(db: Session, user: User, user_agent: Optional[str], ip: Optional[str]) -> bool:
    """Has this user signed in from a matching device/IP before? (ONB-US-01 E-07)."""
    label = _device_label_from_agent(user_agent)
    existing = db.execute(
        select(DeviceSession).where(
            DeviceSession.user_id == user.id,
            DeviceSession.device_label == label,
        )
    ).first()
    return existing is not None


def create_session(
    db: Session,
    user: User,
    user_agent: Optional[str] = None,
    ip: Optional[str] = None,
) -> tuple[DeviceSession, str, str]:
    """Create a device session; return (session, access_token, raw_refresh_token)."""
    raw_refresh = generate_refresh_token()
    session = DeviceSession(
        user_id=user.id,
        refresh_token_hash=hash_opaque_token(raw_refresh),
        device_label=_device_label_from_agent(user_agent),
        user_agent=user_agent,
        ip_address=ip,
        location="Unknown location",  # geo-IP resolution is out of scope (mocked)
        expires_at=utcnow() + timedelta(days=settings.refresh_token_ttl_days),
    )
    db.add(session)
    db.flush()
    access = create_access_token(user.id, session.id)
    return session, access, raw_refresh


def rotate_access_token(db: Session, raw_refresh: str) -> Optional[tuple[str, DeviceSession]]:
    """Given a raw refresh token, return a fresh access token if the session is live."""
    token_hash = hash_opaque_token(raw_refresh)
    session = db.execute(
        select(DeviceSession).where(DeviceSession.refresh_token_hash == token_hash)
    ).scalar_one_or_none()
    now = utcnow()
    if session is None or not session.is_active(now):
        return None
    session.last_active_at = now
    access = create_access_token(session.user_id, session.id)
    return access, session


def revoke_session(db: Session, session: DeviceSession) -> None:
    if session.revoked_at is None:
        session.revoked_at = utcnow()


def revoke_all_sessions(db: Session, user_id: str, except_session_id: Optional[str] = None) -> int:
    """Revoke all active sessions for a user; return the count revoked."""
    now = utcnow()
    sessions = db.execute(
        select(DeviceSession).where(
            DeviceSession.user_id == user_id,
            DeviceSession.revoked_at.is_(None),
        )
    ).scalars().all()
    count = 0
    for s in sessions:
        if except_session_id and s.id == except_session_id:
            continue
        s.revoked_at = now
        count += 1
    return count
