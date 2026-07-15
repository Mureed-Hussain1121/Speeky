"""Pytest fixtures: fresh SQLite DB + FastAPI TestClient per test.

The test-suite runs against SQLite (no Postgres required) by setting DATABASE_URL
before the app modules import their settings.
"""
from __future__ import annotations

import os
import tempfile

import pytest

# Configure a throwaway SQLite database BEFORE importing app modules.
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_db_path}"
os.environ["DEV_MODE"] = "true"
os.environ["FRONTEND_ORIGIN"] = "http://localhost:3000"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def latest_link(client, email: str, kind: str | None = None) -> str:
    params = {"email": email}
    if kind:
        params["kind"] = kind
    resp = client.get("/dev/latest-link", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()["link"]


def token_from_link(link: str) -> str:
    return link.split("token=", 1)[1]


def register_and_verify(client, email="learner@example.com", password="Str0ngPass", username=None, goal="improve_english"):
    body = {"email": email, "password": password, "learning_goal": goal}
    if username:
        body["username"] = username
    r = client.post("/auth/register", json=body)
    assert r.status_code == 201, r.text
    link = latest_link(client, email, "email_verification")
    r = client.post("/auth/verify-email", json={"token": token_from_link(link)})
    assert r.status_code == 200, r.text
    return email, password


def login(client, email, password):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def auth_headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}
