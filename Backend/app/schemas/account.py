"""Account deletion schemas (ONB-US-07)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DeleteAccountRequest(BaseModel):
    # Identity reverification: password for email accounts. SSO-only accounts pass
    # confirm=True (no password to re-enter) — see router for the exact rule.
    password: Optional[str] = None
    confirm: bool = False


class DeletionStatusResponse(BaseModel):
    is_pending_deletion: bool
    deletion_requested_at: Optional[datetime]
    deletion_scheduled_for: Optional[datetime]
    message: str
