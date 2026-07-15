"""Issuance/consumption of one-time email verification & password-reset tokens."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import generate_url_token
from app.models import OneTimeToken, TokenType
from app.models.common import utcnow


def _invalidate_active(db: Session, user_id: str, token_type: TokenType) -> None:
    """Mark any still-active token of this type as used (single active token rule)."""
    now = utcnow()
    rows = db.execute(
        select(OneTimeToken).where(
            OneTimeToken.user_id == user_id,
            OneTimeToken.token_type == token_type,
            OneTimeToken.used_at.is_(None),
        )
    ).scalars().all()
    for row in rows:
        row.used_at = now


def issue_verification_token(db: Session, user_id: str) -> OneTimeToken:
    _invalidate_active(db, user_id, TokenType.EMAIL_VERIFICATION)
    token = OneTimeToken(
        user_id=user_id,
        token=generate_url_token(),
        token_type=TokenType.EMAIL_VERIFICATION,
        expires_at=utcnow() + timedelta(hours=settings.email_verification_ttl_hours),
    )
    db.add(token)
    db.flush()
    return token


def issue_reset_token(db: Session, user_id: str) -> OneTimeToken:
    _invalidate_active(db, user_id, TokenType.PASSWORD_RESET)
    token = OneTimeToken(
        user_id=user_id,
        token=generate_url_token(),
        token_type=TokenType.PASSWORD_RESET,
        expires_at=utcnow() + timedelta(minutes=settings.password_reset_ttl_minutes),
    )
    db.add(token)
    db.flush()
    return token


def find_token(db: Session, raw: str, token_type: TokenType) -> OneTimeToken | None:
    return db.execute(
        select(OneTimeToken).where(
            OneTimeToken.token == raw,
            OneTimeToken.token_type == token_type,
        )
    ).scalar_one_or_none()


def count_recent_reset_requests(db: Session, user_id: str) -> int:
    """Number of reset tokens issued inside the configured rate-limit window."""
    window_start = utcnow() - timedelta(minutes=settings.reset_request_window_minutes)
    rows = db.execute(
        select(OneTimeToken).where(
            OneTimeToken.user_id == user_id,
            OneTimeToken.token_type == TokenType.PASSWORD_RESET,
            OneTimeToken.created_at >= window_start,
        )
    ).scalars().all()
    return len(rows)
