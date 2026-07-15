"""Privacy & consent management (ONB-US-06)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_current_user
from app.database import get_db
from app.models import ConsentRecord, User
from app.models.consent import CONSENT_CATALOGUE
from app.schemas.auth import MessageResponse
from app.schemas.consent import ConsentHistoryEntry, ConsentState, ConsentUpdateRequest
from app.services.audit import record_audit

router = APIRouter(prefix="/privacy", tags=["privacy"])


def _latest_by_type(db: Session, user_id: str) -> dict[str, ConsentRecord]:
    rows = (
        db.execute(
            select(ConsentRecord)
            .where(ConsentRecord.user_id == user_id)
            .order_by(ConsentRecord.created_at.desc())
        )
        .scalars()
        .all()
    )
    latest: dict[str, ConsentRecord] = {}
    for row in rows:
        latest.setdefault(row.consent_type, row)
    return latest


@router.get("/consents", response_model=list[ConsentState])
def get_consents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    latest = _latest_by_type(db, user.id)
    out: list[ConsentState] = []
    for ctype, meta in CONSENT_CATALOGUE.items():
        record = latest.get(ctype)
        out.append(
            ConsentState(
                consent_type=ctype,
                label=meta["label"],
                mandatory=meta["mandatory"],
                granted=record.granted if record else meta["mandatory"],
                policy_version=record.policy_version if record else settings.current_policy_version,
                updated_at=record.created_at if record else None,
            )
        )
    return out


@router.put("/consents", response_model=MessageResponse)
def update_consent(
    payload: ConsentUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meta = CONSENT_CATALOGUE.get(payload.consent_type)
    if meta is None:
        raise HTTPException(status_code=404, detail={"code": "unknown_consent", "message": "Unknown consent type."})

    # E-01: mandatory consents cannot be withdrawn while the account stays active.
    if meta["mandatory"] and not payload.granted:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "mandatory_consent",
                "message": f"'{meta['label']}' is required to keep your account active and cannot be withdrawn.",
            },
        )

    # Each change is a new immutable row tied to the current policy version.
    record = ConsentRecord(
        user_id=user.id,
        consent_type=payload.consent_type,
        granted=payload.granted,
        policy_version=settings.current_policy_version,
    )
    db.add(record)
    record_audit(db, "consent_update", user.id, f"{payload.consent_type}={payload.granted}")
    db.commit()
    verb = "granted" if payload.granted else "withdrawn"
    return MessageResponse(message=f"'{meta['label']}' {verb}.")


@router.get("/consents/history", response_model=list[ConsentHistoryEntry])
def consent_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.execute(
            select(ConsentRecord)
            .where(ConsentRecord.user_id == user.id)
            .order_by(ConsentRecord.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [ConsentHistoryEntry.model_validate(r) for r in rows]
