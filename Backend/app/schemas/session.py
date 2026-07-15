"""Device-session schemas (ONB-US-05)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class SessionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    device_label: str
    location: str
    ip_address: Optional[str]
    created_at: datetime
    last_active_at: datetime
    is_current: bool = False
