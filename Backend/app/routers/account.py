"""Account deletion (ONB-US-07 / US-005).

Flow: identity reverification -> grace-period scheduling -> permanent deletion.
Recovery is possible any time during the grace period (E-05).

Subscription/payment/legal-hold checks (E-02/E-03/E-04) require systems that do
not exist yet; they are represented by the mocked `_deletion_blockers` hook so
the branch is wired and testable.
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_current_user
from app.core.security import verify_password
from app.database import get_db
from app.models import (
    ConsentRecord,
    DeviceSession,
    OneTimeToken,
    PasswordHistory,
    User,
)
from app.models.common import utcnow
from app.models.user import AuthProvider
from app.schemas.account import DeleteAccountRequest, DeletionStatusResponse
from app.schemas.auth import MessageResponse
from app.services import sessions as session_svc
from app.services.audit import record_audit

router = APIRouter(prefix="/account", tags=["account"])


def _deletion_blockers(user: User) -> list[str]:
    """MOCK: checks for active subscription / pending payment / legal hold.

    Returns a list of human-readable blockers. Currently always empty because the
    billing and compliance subsystems are not built. Wire real checks here later
    (ONB-US-07 E-02/E-03/E-04).
    """
    return []


@router.get("/deletion-status", response_model=DeletionStatusResponse)
def deletion_status(user: User = Depends(get_current_user)):
    if user.is_pending_deletion:
        msg = f"Your account is scheduled for deletion on {user.deletion_scheduled_for:%Y-%m-%d %H:%M UTC}. You can still cancel."
    else:
        msg = "Your account is active."
    return DeletionStatusResponse(
        is_pending_deletion=user.is_pending_deletion,
        deletion_requested_at=user.deletion_requested_at,
        deletion_scheduled_for=user.deletion_scheduled_for,
        message=msg,
    )


@router.post("/delete", response_model=DeletionStatusResponse)
def request_deletion(
    payload: DeleteAccountRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Identity reverification (AC): password for email accounts, explicit confirm for SSO.
    if user.auth_provider == AuthProvider.EMAIL and user.password_hash:
        if not payload.password or not verify_password(payload.password, user.password_hash):
            # E-01: incorrect password -> rejected.
            raise HTTPException(
                status_code=401,
                detail={"code": "reverification_failed", "message": "Password is incorrect. Deletion not authorised."},
            )
    else:
        if not payload.confirm:
            raise HTTPException(
                status_code=400,
                detail={"code": "confirmation_required", "message": "Please confirm you want to delete your account."},
            )

    # E-02/E-03/E-04: blockers (mocked).
    blockers = _deletion_blockers(user)
    if blockers:
        raise HTTPException(status_code=409, detail={"code": "deletion_blocked", "blockers": blockers})

    now = utcnow()
    user.deletion_requested_at = now
    user.deletion_scheduled_for = now + timedelta(days=settings.deletion_grace_days)
    # Revoke sessions so the account is effectively logged out everywhere while pending.
    session_svc.revoke_all_sessions(db, user.id)
    record_audit(db, "deletion_requested", user.id, f"scheduled_for={user.deletion_scheduled_for.isoformat()}")
    db.commit()
    db.refresh(user)
    return DeletionStatusResponse(
        is_pending_deletion=True,
        deletion_requested_at=user.deletion_requested_at,
        deletion_scheduled_for=user.deletion_scheduled_for,
        message=f"Account scheduled for deletion on {user.deletion_scheduled_for:%Y-%m-%d %H:%M UTC}. "
        f"Log in and cancel any time before then to keep your account.",
    )


@router.post("/delete/cancel", response_model=MessageResponse)
def cancel_deletion(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # E-05: recovery during grace period.
    if not user.is_pending_deletion:
        raise HTTPException(status_code=409, detail={"code": "not_pending", "message": "No pending deletion to cancel."})
    user.deletion_requested_at = None
    user.deletion_scheduled_for = None
    record_audit(db, "deletion_cancelled", user.id)
    db.commit()
    return MessageResponse(message="Account restored. Your deletion request has been cancelled.")


def _purge_user(db: Session, user: User) -> None:
    """Permanently erase a user's personal data (GDPR right-to-be-forgotten).

    The audit log intentionally retains a user-less record of the deletion action
    for compliance; the user_id FK is set NULL via ON DELETE SET NULL.
    """
    db.execute(delete(OneTimeToken).where(OneTimeToken.user_id == user.id))
    db.execute(delete(PasswordHistory).where(PasswordHistory.user_id == user.id))
    db.execute(delete(ConsentRecord).where(ConsentRecord.user_id == user.id))
    db.execute(delete(DeviceSession).where(DeviceSession.user_id == user.id))
    record_audit(db, "account_permanently_deleted", None, f"user={user.id}")
    db.delete(user)


@router.post("/process-deletions", response_model=MessageResponse, tags=["account", "admin"])
def process_due_deletions(db: Session = Depends(get_db)):
    """Purge accounts whose grace period has elapsed.

    In production this runs on a scheduler; exposed here so the deletion lifecycle
    can be driven/tested without a cron. Idempotent.
    """
    now = utcnow()
    due = (
        db.execute(
            select(User).where(
                User.deletion_scheduled_for.is_not(None),
                User.deletion_scheduled_for <= now,
                User.is_deleted.is_(False),
            )
        )
        .scalars()
        .all()
    )
    for user in due:
        _purge_user(db, user)
    db.commit()
    return MessageResponse(message=f"{len(due)} account(s) permanently deleted.")
