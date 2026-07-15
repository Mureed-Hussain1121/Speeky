"""Helper for writing audit-log entries."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import AuditLog


def record_audit(db: Session, action: str, user_id: Optional[str] = None, detail: Optional[str] = None) -> AuditLog:
    entry = AuditLog(user_id=user_id, action=action, detail=detail)
    db.add(entry)
    db.flush()
    return entry
