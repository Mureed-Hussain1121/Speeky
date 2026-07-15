"""Privacy & consent records (ONB-US-06).

Every consent decision is stored as a new immutable row tied to the policy
version in effect at the time. The current state of a given consent type is the
most recent row; older rows form the auditable history shown to the user.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.common import new_uuid, utcnow

# Consent catalogue. Mandatory items cannot be withdrawn (ONB-US-06 E-01).
CONSENT_CATALOGUE = {
    "terms_of_service": {"label": "Terms of Service", "mandatory": True},
    "privacy_policy": {"label": "Privacy Policy", "mandatory": True},
    "marketing_emails": {"label": "Marketing communications", "mandatory": False},
    "data_sharing": {"label": "Data sharing with partners", "mandatory": False},
}


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    consent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
