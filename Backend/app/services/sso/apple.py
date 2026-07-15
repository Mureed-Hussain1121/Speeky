"""MOCK 'Sign in with Apple' provider (ONB-US-09).

The real Apple SSO service has not been purchased yet, so this module simulates
the token exchange entirely in-process. It models the two behaviours the story
depends on:

  * "Hide My Email" -> Apple issues a stable per-user @privaterelay.appleid.com
    proxy address instead of the real iCloud email.
  * A stable `sub` (Apple user identifier) that lets us re-link a returning user
    to their existing profile even after they revoke and re-grant access (E-02).

Replace this module with the real Apple OAuth exchange once credentials exist;
the returned AppleIdentity shape is what the router consumes.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass


class AppleSSOError(Exception):
    """Raised when the mock provider cannot resolve an identity (E-02 timeout/failure)."""


@dataclass
class AppleIdentity:
    sub: str  # stable Apple user id
    sub_hash: str  # sha256(sub) stored on our side for linking
    email: str  # real or private-relay address
    is_private_relay: bool


def _relay_email(sub: str) -> str:
    # Deterministic proxy address derived from the Apple sub, mirroring Apple's
    # opaque @privaterelay.appleid.com addresses.
    digest = hashlib.sha256(sub.encode("utf-8")).hexdigest()[:16]
    return f"{digest}@privaterelay.appleid.com"


def exchange_identity_token(
    *,
    mock_sub: str,
    hide_email: bool,
    real_email: str | None = None,
    fail: bool = False,
) -> AppleIdentity:
    """Simulate exchanging an Apple identity token for a normalized identity.

    Parameters mimic what the client would surface from the native Apple prompt.
    `fail=True` simulates E-02 (revoked access / provider error).
    """
    if fail or not mock_sub:
        raise AppleSSOError("Apple authentication service unavailable")

    if hide_email:
        email = _relay_email(mock_sub)
        is_relay = True
    else:
        if not real_email:
            raise AppleSSOError("Apple did not return an email address")
        email = real_email.lower().strip()
        is_relay = False

    sub_hash = hashlib.sha256(mock_sub.encode("utf-8")).hexdigest()
    return AppleIdentity(sub=mock_sub, sub_hash=sub_hash, email=email, is_private_relay=is_relay)
