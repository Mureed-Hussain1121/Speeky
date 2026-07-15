"""Application configuration.

Values are sourced from environment variables (see .env.example). The backend
targets PostgreSQL, but DATABASE_URL can point at any SQLAlchemy-supported URL
so the test-suite can fall back to SQLite without a running Postgres instance.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+psycopg2://speeky:speeky@localhost:5432/speeky_onboarding"

    # JWT / security
    jwt_secret: str = "change-me-in-production-please-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    # Onboarding token lifetimes
    email_verification_ttl_hours: int = 24
    password_reset_ttl_minutes: int = 60

    # Account lockout (ONB-US-01 E-03)
    max_failed_logins: int = 5
    failed_login_window_minutes: int = 15
    account_lock_minutes: int = 15

    # Password reset rate limiting (ONB-US-03 E-05)
    reset_request_max: int = 3
    reset_request_window_minutes: int = 15

    # Account deletion grace period (ONB-US-07 E-05)
    deletion_grace_days: int = 30

    # Privacy / consent (ONB-US-06)
    current_policy_version: str = "1.0"

    # Frontend
    frontend_origin: str = "http://localhost:3000"

    # Dev conveniences
    dev_mode: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
