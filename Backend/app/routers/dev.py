"""Dev-only helpers (guarded by DEV_MODE).

Because email delivery is mocked, these endpoints expose the outbox and the most
recent verification/reset link so the flows can be driven end-to-end locally.
They are NOT registered when DEV_MODE is false.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EmailOutbox

router = APIRouter(prefix="/dev", tags=["dev"])


@router.get("/outbox")
def outbox(limit: int = Query(default=20, le=100), db: Session = Depends(get_db)):
    rows = (
        db.execute(select(EmailOutbox).order_by(EmailOutbox.created_at.desc()).limit(limit))
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "to_email": r.to_email,
            "subject": r.subject,
            "kind": r.kind,
            "link": r.link,
            "body": r.body,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/latest-link")
def latest_link(email: str, kind: str | None = None, db: Session = Depends(get_db)):
    """Return the newest actionable link sent to an email (for local testing)."""
    stmt = select(EmailOutbox).where(EmailOutbox.to_email == email.lower().strip(), EmailOutbox.link.is_not(None))
    if kind:
        stmt = stmt.where(EmailOutbox.kind == kind)
    row = db.execute(stmt.order_by(EmailOutbox.created_at.desc()).limit(1)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="No link found for that email.")
    return {"to_email": row.to_email, "kind": row.kind, "link": row.link}
