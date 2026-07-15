"""Device sessions backing refresh tokens (ONB-US-05)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import new_uuid, utcnow


class DeviceSession(Base):
    __tablename__ = "device_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # The refresh token is stored hashed; the raw value only ever lives in the client.
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    device_label: Mapped[str] = mapped_column(String(200), default="Unknown device", nullable=False)
    user_agent: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    location: Mapped[str] = mapped_column(String(120), default="Unknown location", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions")  # noqa: F821

    def is_active(self, now: datetime) -> bool:
        return self.revoked_at is None and self.expires_at > now
