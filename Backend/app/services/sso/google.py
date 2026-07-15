"""MOCK Google OAuth provider (ONB-US-01 / ONB-US-08).

The real Google OAuth service has not been purchased/configured yet, so this
module simulates the token exchange in-process. Replace with the real Google
OAuth2 code exchange once credentials exist; the GoogleIdentity shape is what
the router consumes.
"""
from __future__ import annotations

from dataclasses import dataclass


class GoogleSSOError(Exception):
    """Raised when the mock provider cannot resolve an identity (SSO timeout/failure)."""


@dataclass
class GoogleIdentity:
    sub: str  # stable Google account id
    email: str
    name: str | None


def exchange_auth_code(
    *,
    mock_sub: str,
    email: str | None,
    name: str | None = None,
    fail: bool = False,
) -> GoogleIdentity:
    """Simulate exchanging a Google auth code for a normalized identity.

    `fail=True` simulates ONB-US-08 E-02 (SSO authentication timeout).
    """
    if fail or not mock_sub or not email:
        raise GoogleSSOError("Authentication service unavailable")
    return GoogleIdentity(sub=mock_sub, email=email.lower().strip(), name=name)
