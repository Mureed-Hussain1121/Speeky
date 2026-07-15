"""User / profile schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import LEARNING_GOALS


class UserPublic(BaseModel):
    """Profile as returned to the owning user."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    username: Optional[str]
    display_name: Optional[str]
    photo_url: Optional[str]
    preferred_language: str
    learning_goal: str
    auth_provider: str
    is_verified: bool
    uses_private_relay: bool
    is_pending_deletion: bool
    # MOCK fields (Gameification / Baseline Assessment) — read-only here.
    score: int
    skill_level: str
    created_at: datetime


class ProfileUpdateRequest(BaseModel):
    """ONB-US-04 profile edits. All fields optional; mandatory ones validated if present."""
    username: Optional[str] = Field(default=None, min_length=3, max_length=50)
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    photo_url: Optional[str] = Field(default=None, max_length=500)
    preferred_language: Optional[str] = Field(default=None, min_length=2, max_length=20)


class GoalUpdateRequest(BaseModel):
    """ONB-US-10 dynamic goal recalibration."""
    learning_goal: str = Field(description=f"One of {list(LEARNING_GOALS.keys())}")
