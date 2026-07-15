"""Privacy & consent schemas (ONB-US-06)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConsentState(BaseModel):
    consent_type: str
    label: str
    mandatory: bool
    granted: bool
    policy_version: str
    updated_at: datetime | None


class ConsentUpdateRequest(BaseModel):
    consent_type: str
    granted: bool


class ConsentHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    consent_type: str
    granted: bool
    policy_version: str
    created_at: datetime
