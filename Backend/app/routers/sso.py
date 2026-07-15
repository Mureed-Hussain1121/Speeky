"""Mock SSO endpoints.

Covers:
  ONB-US-09  Apple SSO Authentication & Privacy Flow  (Hide My Email)
  ONB-US-08  Google SSO registration path

Both providers are MOCKED (services not yet purchased). Accounts created via SSO
are treated as email-verified because the provider vouches for the address.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models.user import LEARNING_GOALS, DEFAULT_GOAL, AuthProvider
from app.schemas.auth import AppleSSORequest, GoogleSSORequest, TokenResponse
from app.schemas.user import UserPublic
from app.services import email as email_svc
from app.services import sessions as session_svc
from app.services import users as user_svc
from app.services.audit import record_audit
from app.services.sso.apple import AppleSSOError, exchange_identity_token
from app.services.sso.google import GoogleSSOError, exchange_auth_code

router = APIRouter(prefix="/auth/sso", tags=["sso"])


def _resolve_goal(goal: str | None) -> str:
    return goal if goal in LEARNING_GOALS else DEFAULT_GOAL


def _finalize_login(db: Session, user: User, request: Request, is_new: bool) -> TokenResponse:
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    session, access, refresh = session_svc.create_session(db, user, ua, ip)
    record_audit(db, "sso_register" if is_new else "sso_login", user.id, user.auth_provider.value)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=access, refresh_token=refresh, user=UserPublic.model_validate(user))


# --------------------------------------------------------------------------- #
# ONB-US-09 — Apple
# --------------------------------------------------------------------------- #
@router.post("/apple", response_model=TokenResponse)
def apple_sso(payload: AppleSSORequest, request: Request, db: Session = Depends(get_db)):
    try:
        identity = exchange_identity_token(
            mock_sub=payload.mock_sub,
            hide_email=payload.hide_email,
            real_email=payload.real_email,
            fail=payload.simulate_failure,
        )
    except AppleSSOError as exc:
        # E-02 / provider failure -> client offers re-auth or fallback.
        raise HTTPException(status_code=502, detail={"code": "apple_unavailable", "message": str(exc)})

    # Re-link a returning user by their stable Apple id hash (E-02 reconnect).
    user = db.execute(
        select(User).where(User.apple_sub_hash == identity.sub_hash)
    ).scalar_one_or_none()

    if user is None:
        # Guard against an email that already belongs to a non-Apple account.
        existing = user_svc.get_by_email(db, identity.email)
        if existing and existing.apple_sub_hash != identity.sub_hash:
            raise HTTPException(
                status_code=409,
                detail={"code": "account_exists", "message": "An account with this email already exists. Please log in."},
            )
        user = User(
            email=identity.email,
            auth_provider=AuthProvider.APPLE,
            apple_sub_hash=identity.sub_hash,
            uses_private_relay=identity.is_private_relay,
            is_verified=True,
            learning_goal=_resolve_goal(payload.learning_goal),
        )
        db.add(user)
        db.flush()
        user_svc.seed_mandatory_consents(db, user.id)
        # Welcome email routed through the (mock) Apple private relay when hidden.
        email_svc.send_welcome_email(db, user.email)
        is_new = True
    else:
        is_new = False

    return _finalize_login(db, user, request, is_new)


# --------------------------------------------------------------------------- #
# Google
# --------------------------------------------------------------------------- #
@router.post("/google", response_model=TokenResponse)
def google_sso(payload: GoogleSSORequest, request: Request, db: Session = Depends(get_db)):
    try:
        identity = exchange_auth_code(
            mock_sub=payload.mock_sub,
            email=payload.email,
            name=payload.name,
            fail=payload.simulate_failure,
        )
    except GoogleSSOError as exc:
        # ONB-US-08 E-02: SSO timeout/failure -> offer email fallback client-side.
        raise HTTPException(status_code=502, detail={"code": "google_unavailable", "message": str(exc)})

    user = db.execute(select(User).where(User.google_sub == identity.sub)).scalar_one_or_none()

    if user is None:
        existing = user_svc.get_by_email(db, identity.email)
        if existing and existing.google_sub != identity.sub:
            raise HTTPException(
                status_code=409,
                detail={"code": "account_exists", "message": "An account with this email already exists. Please log in."},
            )
        user = User(
            email=identity.email,
            display_name=identity.name,
            auth_provider=AuthProvider.GOOGLE,
            google_sub=identity.sub,
            is_verified=True,
            learning_goal=_resolve_goal(payload.learning_goal),
        )
        db.add(user)
        db.flush()
        user_svc.seed_mandatory_consents(db, user.id)
        email_svc.send_welcome_email(db, user.email)
        is_new = True
    else:
        is_new = False

    return _finalize_login(db, user, request, is_new)
