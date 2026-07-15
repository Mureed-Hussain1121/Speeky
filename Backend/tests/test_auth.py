"""Tests for ONB-US-01/02/03/08 auth & onboarding flows."""
from __future__ import annotations

from tests.conftest import auth_headers, latest_link, login, register_and_verify, token_from_link


# ------------------------- ONB-US-08 Registration ------------------------- #
def test_register_success_and_verification_gate(client):
    r = client.post("/auth/register", json={"email": "a@ex.com", "password": "Str0ngPass", "learning_goal": "job_interviews"})
    assert r.status_code == 201
    # Login blocked before verification (ONB-US-02 AC / E-04).
    r = client.post("/auth/login", json={"email": "a@ex.com", "password": "Str0ngPass"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "email_unverified"


def test_register_duplicate_email(client):
    client.post("/auth/register", json={"email": "dup@ex.com", "password": "Str0ngPass", "learning_goal": "improve_english"})
    r = client.post("/auth/register", json={"email": "dup@ex.com", "password": "Str0ngPass", "learning_goal": "improve_english"})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "account_exists"


def test_register_weak_password(client):
    r = client.post("/auth/register", json={"email": "w@ex.com", "password": "weak", "learning_goal": "improve_english"})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "weak_password"


def test_register_invalid_goal(client):
    r = client.post("/auth/register", json={"email": "g@ex.com", "password": "Str0ngPass", "learning_goal": "nope"})
    assert r.status_code == 422


# ------------------------- ONB-US-02 Verification ------------------------- #
def test_verify_twice_reports_already_verified(client):
    register_and_verify(client, email="v@ex.com")
    # Second verify with a fresh token attempt: request a resend -> already verified message.
    r = client.post("/auth/resend-verification", json={"email": "v@ex.com"})
    assert "already verified" in r.json()["message"].lower()


def test_verify_invalid_token(client):
    r = client.post("/auth/verify-email", json={"token": "does-not-exist"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "invalid_token"


# ------------------------- ONB-US-01 Login ------------------------- #
def test_login_success(client):
    email, pw = register_and_verify(client, email="l@ex.com")
    tokens = login(client, email, pw)
    assert tokens["access_token"] and tokens["refresh_token"]
    assert tokens["user"]["email"] == email
    # Mock profile fields present.
    assert tokens["user"]["score"] == 0
    assert tokens["user"]["skill_level"] == "Unassessed"


def test_login_wrong_password_generic_error(client):
    email, _ = register_and_verify(client, email="wp@ex.com")
    r = client.post("/auth/login", json={"email": email, "password": "WrongPass9"})
    assert r.status_code == 401
    assert r.json()["detail"]["message"] == "Incorrect email or password"


def test_login_unknown_email_same_generic_error(client):
    r = client.post("/auth/login", json={"email": "nobody@ex.com", "password": "WhateverPass9"})
    assert r.status_code == 401
    assert r.json()["detail"]["message"] == "Incorrect email or password"


def test_account_lockout_after_5_failures(client):
    email, _ = register_and_verify(client, email="lock@ex.com")
    for _ in range(4):
        r = client.post("/auth/login", json={"email": email, "password": "WrongPass9"})
        assert r.status_code == 401
    r = client.post("/auth/login", json={"email": email, "password": "WrongPass9"})
    assert r.status_code == 423  # locked on the 5th
    # Even the correct password is now refused while locked.
    r = client.post("/auth/login", json={"email": email, "password": "Str0ngPass"})
    assert r.status_code == 423
    # A security alert email was queued.
    assert latest_link(client, email, "account_locked")


def test_refresh_and_logout(client):
    email, pw = register_and_verify(client, email="rf@ex.com")
    tokens = login(client, email, pw)
    r = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200 and r.json()["access_token"]
    r = client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    # After logout the refresh token no longer works.
    r = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401


# ------------------------- ONB-US-03 Forgot / reset ------------------------- #
def test_forgot_password_unknown_email_generic(client):
    r = client.post("/auth/forgot-password", json={"email": "ghost@ex.com"})
    assert r.status_code == 200
    assert "if an account exists" in r.json()["message"].lower()


def test_reset_password_flow_revokes_sessions(client):
    email, pw = register_and_verify(client, email="rp@ex.com")
    tokens = login(client, email, pw)
    client.post("/auth/forgot-password", json={"email": email})
    link = latest_link(client, email, "password_reset")
    new_pw = "N3wStrongPass"
    r = client.post("/auth/reset-password", json={"token": token_from_link(link), "new_password": new_pw})
    assert r.status_code == 200
    # Old session revoked.
    r = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401
    # Old password no longer works; new one does.
    assert client.post("/auth/login", json={"email": email, "password": pw}).status_code == 401
    assert client.post("/auth/login", json={"email": email, "password": new_pw}).status_code == 200


def test_reset_password_rejects_reuse(client):
    email, pw = register_and_verify(client, email="reuse@ex.com")
    client.post("/auth/forgot-password", json={"email": email})
    link = latest_link(client, email, "password_reset")
    r = client.post("/auth/reset-password", json={"token": token_from_link(link), "new_password": pw})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "password_reused"


def test_reset_rate_limit(client):
    email, _ = register_and_verify(client, email="rl@ex.com")
    for _ in range(5):
        client.post("/auth/forgot-password", json={"email": email})
    # Still generic message; internally rate-limited after 3.
    from app.database import SessionLocal
    from app.models import OneTimeToken, TokenType, User
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    count = db.query(OneTimeToken).filter(
        OneTimeToken.user_id == user.id, OneTimeToken.token_type == TokenType.PASSWORD_RESET
    ).count()
    db.close()
    assert count == 3  # capped at reset_request_max
