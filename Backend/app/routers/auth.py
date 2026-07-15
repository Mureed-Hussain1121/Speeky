"""Authentication & onboarding endpoints.

Covers:
  ONB-US-08  User Registration & Profile Setup
  ONB-US-02  Email Verification & Account Activation
  ONB-US-01  User Login & Authentication
  ONB-US-03  Forgot Password & Reset
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import (
    hash_password,
    validate_password_policy,
    verify_password,
)
from app.database import get_db
from app.models import TokenType, User
from app.models.common import utcnow
from app.models.user import DEFAULT_GOAL, LEARNING_GOALS, AuthProvider
from app.schemas.auth import (
    AccessTokenResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.schemas.user import UserPublic
from app.services import email as email_svc
from app.services import sessions as session_svc
from app.services import tokens as token_svc
from app.services import users as user_svc
from app.services.audit import record_audit
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

# Deliberately identical message for wrong-password and unknown-email to prevent
# account enumeration (ONB-US-01 E-01/E-02).
_GENERIC_LOGIN_ERROR = "Incorrect email or password"
# Deliberately identical response whether or not the email exists (ONB-US-03 E-04).
_GENERIC_RESET_MESSAGE = (
    "If an account exists for that email, a password reset link has been sent."
)


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    return ua, ip


def _issue_and_send_verification(db: Session, user: User) -> None:
    token = token_svc.issue_verification_token(db, user.id)
    email_svc.send_verification_email(db, user.email, token.token)


# --------------------------------------------------------------------------- #
# ONB-US-08 — Registration
# --------------------------------------------------------------------------- #
@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()

    # E-01: Duplicate identity detection.
    if user_svc.get_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "account_exists", "message": "An account with this email already exists."},
        )

    if payload.learning_goal not in LEARNING_GOALS:
        raise HTTPException(status_code=422, detail="Invalid learning goal.")

    # Password policy enforced up-front.
    problems = validate_password_policy(payload.password)
    if problems:
        raise HTTPException(status_code=422, detail={"code": "weak_password", "requirements": problems})

    if payload.username and user_svc.get_by_username(db, payload.username):
        raise HTTPException(status_code=409, detail={"code": "username_taken", "message": "Username is taken."})

    user = User(
        email=email,
        username=payload.username,
        password_hash=hash_password(payload.password),
        auth_provider=AuthProvider.EMAIL,
        learning_goal=payload.learning_goal,
        is_verified=False,
    )
    db.add(user)
    db.flush()

    user_svc.record_password(db, user.id, user.password_hash)
    user_svc.seed_mandatory_consents(db, user.id)
    _issue_and_send_verification(db, user)
    record_audit(db, "register", user.id, f"provider=email goal={payload.learning_goal}")
    db.commit()

    return MessageResponse(
        message="Registration successful. Please check your email to verify your account."
    )


# --------------------------------------------------------------------------- #
# ONB-US-02 — Email verification & activation
# --------------------------------------------------------------------------- #
@router.post("/verify-email", response_model=MessageResponse)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    token = token_svc.find_token(db, payload.token, TokenType.EMAIL_VERIFICATION)

    # E-02: invalid/tampered token.
    if token is None:
        record_audit(db, "verify_email_failed", None, "invalid_token")
        db.commit()
        raise HTTPException(status_code=400, detail={"code": "invalid_token", "message": "Invalid verification link."})

    user = db.get(User, token.user_id)

    # E-04 / E-05: already verified -> report success without changing state.
    if user and user.is_verified:
        return MessageResponse(message="Your account is already verified. Please log in.")

    now = utcnow()
    # E-01: expired token.
    if not token.is_active(now):
        raise HTTPException(
            status_code=400,
            detail={"code": "expired_token", "message": "This verification link has expired. Request a new one."},
        )

    token.used_at = now
    user.is_verified = True
    email_svc.send_welcome_email(db, user.email)
    record_audit(db, "verify_email", user.id)
    db.commit()
    return MessageResponse(message="Email verified. You can now log in.")


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(payload: ResendVerificationRequest, db: Session = Depends(get_db)):
    user = user_svc.get_by_email(db, payload.email)
    # Do not disclose whether the account exists.
    if user and not user.is_verified:
        _issue_and_send_verification(db, user)
        record_audit(db, "resend_verification", user.id)
        db.commit()
    elif user and user.is_verified:
        return MessageResponse(message="This account is already verified. Please log in.")
    return MessageResponse(message="If an unverified account exists for that email, a new verification link has been sent.")


# --------------------------------------------------------------------------- #
# ONB-US-01 — Login
# --------------------------------------------------------------------------- #
@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = user_svc.get_by_email(db, payload.email)

    # E-01/E-02: generic error, no field/account disclosure.
    if user is None or user.password_hash is None:
        raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": _GENERIC_LOGIN_ERROR})

    if user.is_deleted:
        raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": _GENERIC_LOGIN_ERROR})

    # E-03: account currently locked.
    if user_svc.is_locked(user):
        raise HTTPException(
            status_code=423,
            detail={
                "code": "account_locked",
                "message": "Account temporarily locked due to failed attempts. Reset your password or try again later.",
            },
        )

    if not verify_password(payload.password, user.password_hash):
        locked_now = user_svc.register_failed_login(db, user)
        record_audit(db, "login_failed", user.id, f"count={user.failed_login_count}")
        if locked_now:
            email_svc.send_account_locked_alert(db, user.email)
            record_audit(db, "account_locked", user.id)
            db.commit()
            raise HTTPException(
                status_code=423,
                detail={
                    "code": "account_locked",
                    "message": "Account temporarily locked due to failed attempts. Reset your password or try again later.",
                },
            )
        db.commit()
        raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": _GENERIC_LOGIN_ERROR})

    # E-04: unverified email blocks login.
    if not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "email_unverified",
                "message": "Please verify your email before logging in.",
                "can_resend": True,
            },
        )

    # Successful auth: clear lockout counters, create session.
    user_svc.clear_lockout(user)
    ua, ip = _client_meta(request)

    # E-07: new/unrecognized device -> security notification (mock email).
    if not session_svc.is_known_device(db, user, ua, ip):
        session, access, refresh = session_svc.create_session(db, user, ua, ip)
        email_svc.send_new_device_alert(db, user.email, session.device_label, session.location)
        record_audit(db, "login_new_device", user.id, session.device_label)
    else:
        session, access, refresh = session_svc.create_session(db, user, ua, ip)
        record_audit(db, "login", user.id)

    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=access, refresh_token=refresh, user=UserPublic.model_validate(user))


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    result = session_svc.rotate_access_token(db, payload.refresh_token)
    if result is None:
        # E-06: expired/tampered/revoked -> silent invalidation.
        raise HTTPException(status_code=401, detail={"code": "invalid_session", "message": "Session expired. Please log in again."})
    access, _session = result
    db.commit()
    return AccessTokenResponse(access_token=access)


@router.post("/logout", response_model=MessageResponse)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    result = session_svc.rotate_access_token(db, payload.refresh_token)
    if result:
        _, session = result
        session_svc.revoke_session(db, session)
        record_audit(db, "logout", session.user_id)
        db.commit()
    return MessageResponse(message="Logged out.")


# --------------------------------------------------------------------------- #
# ONB-US-03 — Forgot / reset password
# --------------------------------------------------------------------------- #
@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = user_svc.get_by_email(db, payload.email)

    if user and user.password_hash is not None and not user.is_deleted:
        # E-05: rate-limit excessive requests.
        if token_svc.count_recent_reset_requests(db, user.id) >= settings.reset_request_max:
            record_audit(db, "reset_rate_limited", user.id)
            db.commit()
            # Still return the generic message to avoid enumeration/timing leaks.
            return MessageResponse(message=_GENERIC_RESET_MESSAGE)

        token = token_svc.issue_reset_token(db, user.id)
        email_svc.send_password_reset_email(db, user.email, token.token)
        record_audit(db, "reset_requested", user.id)
        db.commit()

    # E-04: never reveal whether the account exists.
    return MessageResponse(message=_GENERIC_RESET_MESSAGE)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    token = token_svc.find_token(db, payload.token, TokenType.PASSWORD_RESET)
    now = utcnow()

    # E-01 / invalid: expired or non-existent token.
    if token is None or not token.is_active(now):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_or_expired_token", "message": "This reset link is invalid or has expired."},
        )

    # E-02: weak password.
    problems = validate_password_policy(payload.new_password)
    if problems:
        raise HTTPException(status_code=422, detail={"code": "weak_password", "requirements": problems})

    user = db.get(User, token.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail={"code": "invalid_or_expired_token", "message": "Invalid reset link."})

    # E-03: previously-used password.
    if user_svc.is_password_reused(db, user.id, payload.new_password):
        raise HTTPException(
            status_code=422,
            detail={"code": "password_reused", "message": "Please choose a password you have not used recently."},
        )

    token.used_at = now
    user_svc.set_password(db, user, payload.new_password)
    user_svc.clear_lockout(user)  # a successful reset also clears any lockout

    # AC: revoke all active sessions, forcing re-authentication everywhere.
    revoked = session_svc.revoke_all_sessions(db, user.id)
    record_audit(db, "password_reset", user.id, f"sessions_revoked={revoked}")
    db.commit()
    return MessageResponse(message="Password updated. Please log in with your new password.")
