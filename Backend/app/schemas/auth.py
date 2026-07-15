"""Request/response schemas for authentication & onboarding flows."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.user import LEARNING_GOALS
from app.schemas.user import UserPublic

_GOAL_KEYS = list(LEARNING_GOALS.keys())


# --------------------------- Registration (ONB-US-08) --------------------------- #
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    username: Optional[str] = Field(default=None, max_length=50)
    learning_goal: str = Field(description=f"One of {_GOAL_KEYS}")


# ----------------------------- Login (ONB-US-01) ----------------------------- #
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPublic


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --------------------- Email verification (ONB-US-02) --------------------- #
class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


# --------------------- Forgot / reset password (ONB-US-03) --------------------- #
class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


# ------------------------------- SSO mocks ------------------------------- #
class AppleSSORequest(BaseModel):
    """Mock payload emulating what the native Apple prompt would surface."""
    mock_sub: str = Field(description="Stable Apple user id (mock)")
    hide_email: bool = False
    real_email: Optional[EmailStr] = None
    learning_goal: Optional[str] = None
    simulate_failure: bool = False


class GoogleSSORequest(BaseModel):
    """Mock payload emulating a Google OAuth code exchange."""
    mock_sub: str = Field(description="Stable Google account id (mock)")
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    learning_goal: Optional[str] = None
    simulate_failure: bool = False


class MessageResponse(BaseModel):
    message: str
