"""Session & device management (ONB-US-05)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import current_session_id, get_current_user
from app.database import get_db
from app.models import DeviceSession, User
from app.models.common import utcnow
from app.schemas.auth import MessageResponse
from app.schemas.session import SessionPublic
from app.services import sessions as session_svc
from app.services.audit import record_audit

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionPublic])
def list_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = utcnow()
    active = (
        db.execute(
            select(DeviceSession)
            .where(DeviceSession.user_id == user.id, DeviceSession.revoked_at.is_(None))
            .order_by(DeviceSession.last_active_at.desc())
        )
        .scalars()
        .all()
    )
    current = current_session_id(user)
    out: list[SessionPublic] = []
    for s in active:
        if not s.is_active(now):
            continue
        item = SessionPublic.model_validate(s)
        item.is_current = s.id == current
        out.append(item)
    return out


@router.delete("/{session_id}", response_model=MessageResponse)
def terminate_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.get(DeviceSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Session not found."})

    session_svc.revoke_session(db, session)
    record_audit(db, "session_terminate", user.id, session.device_label)
    db.commit()
    return MessageResponse(message="Session terminated.")


@router.post("/logout-all", response_model=MessageResponse)
def logout_all(
    keep_current: bool = True,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    except_id = current_session_id(user) if keep_current else None
    count = session_svc.revoke_all_sessions(db, user.id, except_session_id=except_id)
    record_audit(db, "session_logout_all", user.id, f"revoked={count} keep_current={keep_current}")
    db.commit()
    return MessageResponse(message=f"{count} session(s) terminated.")
