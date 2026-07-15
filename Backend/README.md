# Speeky — Onboarding & Account Management API

FastAPI + PostgreSQL backend implementing the **Onboarding & Account Management**
user stories (ONB-US-01 … ONB-US-10). It is decoupled from the `speeky/` speech
pipeline and lives outside that package by design.

## Scope & mocks

| Area | Status |
| --- | --- |
| Registration, email verification, login, forgot/reset password | Implemented |
| Profile management + dynamic goal recalibration | Implemented |
| Session/device management, privacy & consent, account deletion | Implemented |
| **Apple SSO** (`services/sso/apple.py`) | **MOCK** — service not yet purchased |
| **Google OAuth** (`services/sso/google.py`) | **MOCK** — service not yet purchased |
| **Email delivery** (`services/email.py`) | **MOCK** — logged + stored in `email_outbox`, exposed via `/dev/*` |
| Profile `score` (Gameification) & `skill_level` (Baseline Assessment) | **MOCK** fields, read-only defaults |
| Payment/subscription & legal-hold deletion blockers (ONB-US-07 E-02..E-04) | **MOCK** hook `_deletion_blockers`, always clear |
| Geo-IP device location / CAPTCHA / brute-force IP throttling | Out of scope for MVP (device label derived from User-Agent) |

## Run it

```bash
cd Backend
python -m venv .venv
.venv/Scripts/activate            # Windows;  source .venv/bin/activate on *nix
pip install -r requirements.txt
cp .env.example .env              # adjust JWT_SECRET etc.

# Start Postgres (matches .env default DATABASE_URL)
docker compose up -d

uvicorn app.main:app --reload
```

Interactive docs: http://localhost:8000/docs · Health: http://localhost:8000/health

Tables are auto-created on startup (`init_db`); no migration step for the MVP.

## Local testing without Postgres

The test-suite runs against a throwaway SQLite database (see `tests/conftest.py`),
so no Postgres instance is needed:

```bash
.venv/Scripts/python -m pytest -q
```

Because email is mocked, `DEV_MODE=true` exposes:

- `GET /dev/outbox` — every "sent" email
- `GET /dev/latest-link?email=<addr>&kind=email_verification|password_reset` — the newest actionable link

## Key endpoints

| Story | Method & path |
| --- | --- |
| ONB-US-08 Register | `POST /auth/register` |
| ONB-US-02 Verify / resend | `POST /auth/verify-email`, `POST /auth/resend-verification` |
| ONB-US-01 Login / refresh / logout | `POST /auth/login`, `/auth/refresh`, `/auth/logout` |
| ONB-US-03 Forgot / reset | `POST /auth/forgot-password`, `/auth/reset-password` |
| ONB-US-09 Apple SSO (mock) | `POST /auth/sso/apple` |
| Google SSO (mock) | `POST /auth/sso/google` |
| ONB-US-04 Profile | `GET/PATCH /profile` |
| ONB-US-10 Goal | `PUT /profile/goal`, `GET /profile/goals` |
| ONB-US-05 Sessions | `GET /sessions`, `DELETE /sessions/{id}`, `POST /sessions/logout-all` |
| ONB-US-06 Privacy | `GET/PUT /privacy/consents`, `GET /privacy/consents/history` |
| ONB-US-07 Deletion | `POST /account/delete`, `/account/delete/cancel`, `GET /account/deletion-status`, `POST /account/process-deletions` |

## Security notes (from the acceptance criteria)

- Passwords hashed with bcrypt; never stored/transmitted in plaintext.
- Short-lived JWT access tokens (15 min) + opaque refresh tokens stored hashed as device sessions.
- Generic login/reset messages prevent account enumeration.
- Account lockout after N failed attempts within a rolling window.
- Password reset revokes **all** active sessions and rejects recent-password reuse.
- Mandatory consents cannot be withdrawn; every consent decision is versioned & auditable.
- Account deletion re-verifies identity, honours a grace period, and permanently purges personal data.
