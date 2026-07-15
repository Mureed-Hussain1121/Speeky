"""User creation, password updates, and consent seeding."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import hash_password, verify_password
from app.models import ConsentRecord, PasswordHistory, User
from app.models.common import utcnow
from app.models.consent import CONSENT_CATALOGUE

_PASSWORD_HISTORY_DEPTH = 5


def get_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email.lower().strip())).scalar_one_or_none()


def get_by_username(db: Session, username: str) -> User | None:
    return db.execute(select(User).where(User.username == username)).scalar_one_or_none()


def seed_mandatory_consents(db: Session, user_id: str) -> None:
    """Record acceptance of mandatory policies at registration (ONB-US-06)."""
    for ctype, meta in CONSENT_CATALOGUE.items():
        if meta["mandatory"]:
            db.add(
                ConsentRecord(
                    user_id=user_id,
                    consent_type=ctype,
                    granted=True,
                    policy_version=settings.current_policy_version,
                )
            )


def record_password(db: Session, user_id: str, password_hash: str) -> None:
    db.add(PasswordHistory(user_id=user_id, password_hash=password_hash))


def is_password_reused(db: Session, user_id: str, new_password: str) -> bool:
    """Reject reuse of any of the recent passwords (ONB-US-03 E-03)."""
    rows = (
        db.execute(
            select(PasswordHistory)
            .where(PasswordHistory.user_id == user_id)
            .order_by(PasswordHistory.created_at.desc())
            .limit(_PASSWORD_HISTORY_DEPTH)
        )
        .scalars()
        .all()
    )
    return any(verify_password(new_password, r.password_hash) for r in rows)


def set_password(db: Session, user: User, new_password: str) -> None:
    """Update a user's password and append to history."""
    new_hash = hash_password(new_password)
    user.password_hash = new_hash
    record_password(db, user.id, new_hash)


def register_failed_login(db: Session, user: User) -> bool:
    """Increment failed-login tracking; return True if the account is now locked.

    Lock policy (ONB-US-01 E-03): N failures within a rolling window locks the
    account for a fixed duration.
    """
    now = utcnow()
    window = timedelta(minutes=settings.failed_login_window_minutes)

    if user.first_failed_login_at is None or (now - user.first_failed_login_at) > window:
        # Start a fresh window.
        user.first_failed_login_at = now
        user.failed_login_count = 1
    else:
        user.failed_login_count += 1

    if user.failed_login_count >= settings.max_failed_logins:
        user.locked_until = now + timedelta(minutes=settings.account_lock_minutes)
        return True
    return False


def is_locked(user: User) -> bool:
    return user.locked_until is not None and user.locked_until > utcnow()


def clear_lockout(user: User) -> None:
    user.failed_login_count = 0
    user.first_failed_login_at = None
    user.locked_until = None
