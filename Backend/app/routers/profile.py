"""Profile management & goal recalibration.

Covers:
  ONB-US-04  Profile Management
  ONB-US-10  Dynamic Goal Updating & Profile Recalibration
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models import User
from app.models.user import LEARNING_GOALS
from app.schemas.user import GoalUpdateRequest, ProfileUpdateRequest, UserPublic
from app.services import users as user_svc
from app.services.audit import record_audit

router = APIRouter(prefix="/profile", tags=["profile"])

_ALLOWED_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")


@router.get("", response_model=UserPublic)
def get_profile(user: User = Depends(get_current_user)):
    return UserPublic.model_validate(user)


@router.patch("", response_model=UserPublic)
def update_profile(
    payload: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    changed: list[str] = []

    if payload.username is not None and payload.username != user.username:
        # E-01: mandatory-field validity (uniqueness) enforced before save.
        existing = user_svc.get_by_username(db, payload.username)
        if existing and existing.id != user.id:
            raise HTTPException(status_code=409, detail={"code": "username_taken", "message": "Username is taken."})
        user.username = payload.username
        changed.append("username")

    if payload.display_name is not None:
        user.display_name = payload.display_name
        changed.append("display_name")

    if payload.photo_url is not None:
        # E-02: unsupported image format rejected.
        lowered = payload.photo_url.lower().split("?", 1)[0]
        if not lowered.endswith(_ALLOWED_IMAGE_EXT):
            raise HTTPException(
                status_code=422,
                detail={"code": "unsupported_image", "message": f"Supported formats: {', '.join(_ALLOWED_IMAGE_EXT)}"},
            )
        user.photo_url = payload.photo_url
        changed.append("photo_url")

    if payload.preferred_language is not None:
        user.preferred_language = payload.preferred_language
        changed.append("preferred_language")

    if not changed:
        raise HTTPException(status_code=422, detail={"code": "no_changes", "message": "No valid fields to update."})

    # AC: every change is recorded for traceability (audit log).
    record_audit(db, "profile_update", user.id, ",".join(changed))
    db.commit()
    db.refresh(user)
    return UserPublic.model_validate(user)


@router.put("/goal", response_model=UserPublic)
def update_goal(
    payload: GoalUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # E-02: cannot end up with no goal selected.
    if payload.learning_goal not in LEARNING_GOALS:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_goal", "message": f"Goal must be one of {list(LEARNING_GOALS.keys())}."},
        )

    previous = user.learning_goal
    user.learning_goal = payload.learning_goal
    # Historical data (score / skill_level) is intentionally preserved (AC).
    record_audit(db, "goal_update", user.id, f"{previous} -> {payload.learning_goal}")
    db.commit()
    db.refresh(user)
    return UserPublic.model_validate(user)


@router.get("/goals", tags=["profile"])
def list_goals():
    """Catalogue of selectable learning goals for the UI."""
    return {"goals": [{"key": k, "label": v} for k, v in LEARNING_GOALS.items()]}
