"""Mock email service.

Per project scope, email delivery is MOCKED: messages are logged to the console
and persisted to the EmailOutbox table rather than sent over SMTP. This lets the
verification, reset, and security-alert flows be exercised end-to-end locally.

Apple private-relay routing (ONB-US-09) is simulated by simply recording the
proxy address as the recipient — no real relay is involved.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.models import EmailOutbox

logger = logging.getLogger("speeky.email")


def _record(db: Session, to_email: str, subject: str, body: str, link: str | None, kind: str) -> EmailOutbox:
    entry = EmailOutbox(to_email=to_email, subject=subject, body=body, link=link, kind=kind)
    db.add(entry)
    db.flush()  # assign id without committing; caller controls the transaction
    relay = " (via Apple private relay)" if to_email.endswith("privaterelay.appleid.com") else ""
    logger.info("[MOCK EMAIL]%s to=%s subject=%s link=%s", relay, to_email, subject, link)
    return entry


def send_verification_email(db: Session, to_email: str, token: str) -> EmailOutbox:
    link = f"{settings.frontend_origin}/verify-email?token={token}"
    body = (
        "Welcome to Speeky!\n\n"
        "Please confirm your email address to activate your account. "
        f"This link is valid for {settings.email_verification_ttl_hours} hours:\n\n{link}\n\n"
        "If you did not sign up, you can ignore this email."
    )
    return _record(db, to_email, "Verify your Speeky email", body, link, "email_verification")


def send_password_reset_email(db: Session, to_email: str, token: str) -> EmailOutbox:
    link = f"{settings.frontend_origin}/reset-password?token={token}"
    body = (
        "We received a request to reset your Speeky password.\n\n"
        f"Use this link within {settings.password_reset_ttl_minutes} minutes to set a new password:\n\n{link}\n\n"
        "If you did not request this, you can safely ignore this email; your password will not change."
    )
    return _record(db, to_email, "Reset your Speeky password", body, link, "password_reset")


def send_welcome_email(db: Session, to_email: str) -> EmailOutbox:
    body = "Your Speeky account is ready. Let's start improving your English!"
    return _record(db, to_email, "Welcome to Speeky", body, None, "welcome")


def send_new_device_alert(db: Session, to_email: str, device_label: str, location: str) -> EmailOutbox:
    body = (
        "New sign-in to your Speeky account\n\n"
        f"Device: {device_label}\nLocation: {location}\n\n"
        "If this was you, no action is needed. If not, reset your password immediately and "
        "review your active sessions in Security settings."
    )
    return _record(db, to_email, "Security alert: new device sign-in", body, None, "security_alert")


def send_account_locked_alert(db: Session, to_email: str) -> EmailOutbox:
    link = f"{settings.frontend_origin}/forgot-password"
    body = (
        "Your Speeky account has been temporarily locked after several failed sign-in attempts.\n\n"
        f"You can reset your password to regain access right away:\n\n{link}\n\n"
        f"Otherwise the lock lifts automatically in {settings.account_lock_minutes} minutes."
    )
    return _record(db, to_email, "Your Speeky account was temporarily locked", body, link, "account_locked")
