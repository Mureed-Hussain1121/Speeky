"""Shared helpers for models."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC now, used as the default for all timestamp columns.

    We deliberately keep timestamps naive-UTC so comparisons behave identically on
    SQLite (test-suite) and Postgres (production). All stored datetimes are UTC.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_uuid() -> str:
    return str(uuid.uuid4())
