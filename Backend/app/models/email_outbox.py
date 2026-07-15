"""Mock email outbox (email delivery is mocked per project scope).

Every 'sent' email is persisted here and logged to the console instead of being
delivered over SMTP. In DEV_MODE the /dev/outbox endpoint exposes these rows so
verification/reset flows can be exercised end-to-end without a mail server.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.common import new_uuid, utcnow


class EmailOutbox(Base):
    __tablename__ = "email_outbox"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    to_email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Convenience: the actionable link (verification/reset) extracted for dev use.
    link: Mapped[Optional[str]] = mapped_column(String(600), nullable=True)
    kind: Mapped[str] = mapped_column(String(50), default="generic", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
