"""Tests for ONB-US-04/05/06/07/09/10 and Google SSO."""
from __future__ import annotations

from tests.conftest import auth_headers, login, register_and_verify


# ------------------------- ONB-US-04 Profile ------------------------- #
def test_profile_get_and_update(client):
    email, pw = register_and_verify(client, email="p@ex.com")
    tokens = login(client, email, pw)
    h = auth_headers(tokens)

    r = client.get("/profile", headers=h)
    assert r.status_code == 200

    r = client.patch("/profile", json={"display_name": "Alice", "username": "alice1"}, headers=h)
    assert r.status_code == 200
    assert r.json()["display_name"] == "Alice"
    assert r.json()["username"] == "alice1"


def test_profile_rejects_unsupported_image(client):
    email, pw = register_and_verify(client, email="img@ex.com")
    h = auth_headers(login(client, email, pw))
    r = client.patch("/profile", json={"photo_url": "http://x/pic.bmp"}, headers=h)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "unsupported_image"


def test_profile_username_conflict(client):
    e1, p1 = register_and_verify(client, email="u1@ex.com")
    e2, p2 = register_and_verify(client, email="u2@ex.com")
    client.patch("/profile", json={"username": "shared"}, headers=auth_headers(login(client, e1, p1)))
    r = client.patch("/profile", json={"username": "shared"}, headers=auth_headers(login(client, e2, p2)))
    assert r.status_code == 409


def test_requires_auth(client):
    assert client.get("/profile").status_code == 401
    assert client.get("/profile", headers={"Authorization": "Bearer garbage"}).status_code == 401


# ------------------------- ONB-US-10 Goal ------------------------- #
def test_goal_update_preserves_mock_history(client):
    email, pw = register_and_verify(client, email="goal@ex.com", goal="improve_english")
    h = auth_headers(login(client, email, pw))
    r = client.put("/profile/goal", json={"learning_goal": "job_interviews"}, headers=h)
    assert r.status_code == 200
    assert r.json()["learning_goal"] == "job_interviews"
    # Mock score/skill preserved.
    assert r.json()["score"] == 0
    assert r.json()["skill_level"] == "Unassessed"


def test_goal_invalid(client):
    email, pw = register_and_verify(client, email="goal2@ex.com")
    h = auth_headers(login(client, email, pw))
    r = client.put("/profile/goal", json={"learning_goal": "flying"}, headers=h)
    assert r.status_code == 422


# ------------------------- ONB-US-05 Sessions ------------------------- #
def test_session_list_and_terminate(client):
    email, pw = register_and_verify(client, email="sess@ex.com")
    t1 = login(client, email, pw)
    t2 = login(client, email, pw)
    h1 = auth_headers(t1)
    r = client.get("/sessions", headers=h1)
    assert r.status_code == 200
    sessions = r.json()
    assert len(sessions) == 2
    current = [s for s in sessions if s["is_current"]]
    assert len(current) == 1
    # Terminate the other session.
    other = [s for s in sessions if not s["is_current"]][0]
    r = client.delete(f"/sessions/{other['id']}", headers=h1)
    assert r.status_code == 200
    # t2 refresh now fails.
    assert client.post("/auth/refresh", json={"refresh_token": t2["refresh_token"]}).status_code == 401


# ------------------------- ONB-US-06 Privacy ------------------------- #
def test_consents_default_and_mandatory_block(client):
    email, pw = register_and_verify(client, email="priv@ex.com")
    h = auth_headers(login(client, email, pw))
    r = client.get("/privacy/consents", headers=h)
    assert r.status_code == 200
    by_type = {c["consent_type"]: c for c in r.json()}
    assert by_type["privacy_policy"]["granted"] is True
    # Cannot withdraw a mandatory consent.
    r = client.put("/privacy/consents", json={"consent_type": "privacy_policy", "granted": False}, headers=h)
    assert r.status_code == 409
    # Can toggle an optional one, and it shows in history.
    r = client.put("/privacy/consents", json={"consent_type": "marketing_emails", "granted": True}, headers=h)
    assert r.status_code == 200
    r = client.put("/privacy/consents", json={"consent_type": "marketing_emails", "granted": False}, headers=h)
    assert r.status_code == 200
    hist = client.get("/privacy/consents/history", headers=h).json()
    marketing = [x for x in hist if x["consent_type"] == "marketing_emails"]
    assert len(marketing) == 2


# ------------------------- ONB-US-07 Deletion ------------------------- #
def test_deletion_requires_password_then_grace_then_cancel(client):
    email, pw = register_and_verify(client, email="del@ex.com")
    h = auth_headers(login(client, email, pw))
    # Wrong password rejected.
    r = client.post("/account/delete", json={"password": "WrongPass9"}, headers=h)
    assert r.status_code == 401
    # Correct password schedules deletion.
    r = client.post("/account/delete", json={"password": pw}, headers=h)
    assert r.status_code == 200
    assert r.json()["is_pending_deletion"] is True
    # During grace, user can log in and cancel (E-05).
    h2 = auth_headers(login(client, email, pw))
    r = client.post("/account/delete/cancel", headers=h2)
    assert r.status_code == 200
    r = client.get("/account/deletion-status", headers=auth_headers(login(client, email, pw)))
    assert r.json()["is_pending_deletion"] is False


def test_permanent_deletion_blocks_login(client):
    email, pw = register_and_verify(client, email="perm@ex.com")
    h = auth_headers(login(client, email, pw))
    client.post("/account/delete", json={"password": pw}, headers=h)
    # Force the scheduled time into the past then process.
    from app.database import SessionLocal
    from app.models import User
    from app.models.common import utcnow
    from datetime import timedelta
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    user.deletion_scheduled_for = utcnow() - timedelta(seconds=1)
    db.commit()
    db.close()
    r = client.post("/account/process-deletions")
    assert r.status_code == 200
    # Login now blocked entirely (TC-004).
    assert client.post("/auth/login", json={"email": email, "password": pw}).status_code == 401


# ------------------------- ONB-US-09 Apple SSO (mock) ------------------------- #
def test_apple_sso_hide_email_creates_relay_profile(client):
    r = client.post("/auth/sso/apple", json={"mock_sub": "apple-user-1", "hide_email": True, "learning_goal": "public_speaking"})
    assert r.status_code == 200
    user = r.json()["user"]
    assert user["email"].endswith("privaterelay.appleid.com")
    assert user["uses_private_relay"] is True
    assert user["is_verified"] is True
    # Returning the same Apple sub links back to the same profile (E-02).
    r2 = client.post("/auth/sso/apple", json={"mock_sub": "apple-user-1", "hide_email": True})
    assert r2.json()["user"]["id"] == user["id"]


def test_apple_sso_share_email(client):
    r = client.post("/auth/sso/apple", json={"mock_sub": "apple-user-2", "hide_email": False, "real_email": "real@icloud.com"})
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "real@icloud.com"
    assert r.json()["user"]["uses_private_relay"] is False


def test_apple_sso_failure(client):
    r = client.post("/auth/sso/apple", json={"mock_sub": "x", "hide_email": True, "simulate_failure": True})
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "apple_unavailable"


# ------------------------- Google SSO (mock) ------------------------- #
def test_google_sso_register_and_login(client):
    r = client.post("/auth/sso/google", json={"mock_sub": "g-1", "email": "g@gmail.com", "name": "Gina"})
    assert r.status_code == 200
    uid = r.json()["user"]["id"]
    r2 = client.post("/auth/sso/google", json={"mock_sub": "g-1", "email": "g@gmail.com"})
    assert r2.json()["user"]["id"] == uid


def test_google_sso_timeout(client):
    r = client.post("/auth/sso/google", json={"mock_sub": "g-2", "email": "g2@gmail.com", "simulate_failure": True})
    assert r.status_code == 502
