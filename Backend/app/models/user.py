"""User account + profile model.

Per the task scope the profile carries `username`, plus MOCKED `score` and
`skill_level` fields. Score belongs to the Gameification feature and skill_level
to the Baseline Assessment feature; both are stubbed here with default values
until those features are built.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import new_uuid, utcnow


class AuthProvider(str, enum.Enum):
    EMAIL = "email"
    GOOGLE = "google"
    APPLE = "apple"


# Learning goals from ONB-US-08 / ONB-US-10.
LEARNING_GOALS = {
    "improve_english": "Improve English",
    "job_interviews": "Job Interviews",
    "workplace_communication": "Workplace Communication",
    "public_speaking": "Public Speaking",
}
DEFAULT_GOAL = "improve_english"  # ONB-US-08 E-03 drop-off default


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)

    # --- Profile fields (task scope) ---
    username: Mapped[Optional[str]] = mapped_column(String(50), unique=True, index=True, nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(20), default="en-GB", nullable=False)

    # MOCK fields — owned by other features, stubbed for now.
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # MOCK: Gameification
    skill_level: Mapped[str] = mapped_column(String(30), default="Unassessed", nullable=False)  # MOCK: Baseline Assessment

    # --- Auth ---
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # null for SSO-only accounts
    auth_provider: Mapped[AuthProvider] = mapped_column(
        Enum(AuthProvider, native_enum=False, length=20), default=AuthProvider.EMAIL, nullable=False
    )
    # SSO linkage (mocked providers)
    apple_sub_hash: Mapped[Optional[str]] = mapped_column(String(128), unique=True, index=True, nullable=True)
    google_sub: Mapped[Optional[str]] = mapped_column(String(128), unique=True, index=True, nullable=True)
    uses_private_relay: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Apple Hide-My-Email

    # --- Onboarding / goal ---
    learning_goal: Mapped[str] = mapped_column(String(40), default=DEFAULT_GOAL, nullable=False)

    # --- Verification / activation (ONB-US-02) ---
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- Lockout tracking (ONB-US-01 E-03) ---
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_failed_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # --- Deletion (ONB-US-07) ---
    deletion_requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deletion_scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    sessions: Mapped[list["DeviceSession"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def is_pending_deletion(self) -> bool:
        return self.deletion_scheduled_for is not None and not self.is_deleted
