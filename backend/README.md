# Speeky AI — Backend (FastAPI)

FastAPI REST API for the Speeky AI application. Handles authentication, JWT session
management, and password reset flows. Uses **the same** Prisma schema/migrations as
the original Express backend — Prisma Postgres cloud or local Docker — via
[prisma-client-py](https://prisma-client-py.readthedocs.io/).

Ported 1:1 from the Express/Node version. Same routes, same request/response shapes,
same cookies, same DB schema. Frontend needs zero changes.

---

## Tech Stack

| Layer            | Choice                                                                             |
| ---------------- | ---------------------------------------------------------------------------------- |
| Runtime          | Python 3.11+                                                                       |
| Framework        | FastAPI + Uvicorn                                                                  |
| ORM              | prisma-client-py (reuses the original `prisma/schema.prisma` and migrations as-is) |
| Database         | PostgreSQL (Prisma Postgres cloud or local Docker) — unchanged                     |
| Auth             | JWT (access + refresh tokens via HTTP-only cookies) — PyJWT                        |
| Validation       | Pydantic v2                                                                        |
| Password hashing | `bcrypt` (cost 12)                                                                 |
| Email            | aiosmtplib (SMTP_HOST/PORT/USER/PASS from env — e.g. Mailtrap sandbox in dev)      |

---

## Project Structure

```
backend/
├── main.py                  # FastAPI app setup + entrypoint (was app.js + server.js)
├── requirements.txt
│
├── services /  # Business Logic
│   └── auth_services.py   # signup, login, refresh, logout, me, forgot_password, reset_password
│
├── routers/
│   └── auth_routes.py       # /api/auth/* route definitions (was routes/auth_routes.js)
│
├── middlewares/
│   ├── auth_middleware.py   # require_auth — FastAPI dependency, verifies access_token cookie
│   └── error_handler.py     # Global exception handlers (was errorHandler.js)
│
├── lib/
│   └── prisma_client.py     # Singleton Prisma() client instance (`db`)
│
├── schemas/
│   └── auth_schemas.py      # Pydantic request models (was the Zod schemas)
│
├── utils/
│   ├── app_error.py         # AppError class (used by the 404 catch-all)
│   ├── jwt_utils.py         # Token sign/verify helpers, cookie option factories, hash_token
│   └── email_utils.py       # send_password_reset_email — Ethereal (dev) / SMTP (prod)
│
└── prisma/
    ├── schema.prisma        # UNCHANGED data models — generator switched to prisma-client-py
    └── migrations/          # UNCHANGED — copied verbatim from the JS backend
```

---

## What changed vs. the Express version (and why)

- **`prisma/schema.prisma`**: only the `generator client` block changed, from
  `provider = "prisma-client-js"` to `provider = "prisma-client-py"`. Models, `@map`
  table names, and both migrations are byte-for-byte identical — same Postgres tables,
  same columns, nothing to re-migrate if you're pointing at the same DB.
- **`datasource.url`**: added directly into `schema.prisma` (`url = env("DATABASE_URL")`).
  The original relied on `prisma.config.js` for this (a Prisma 7 JS-only feature);
  prisma-client-py doesn't read that file, so the url has to live in the schema itself.
  `prisma.config.js` itself was dropped — nothing else used it.
- **Response shapes**: kept **exactly** the same on purpose, since your frontend teammate's
  code already expects them:
  - Validation failures → `{"error": {"formErrors": [...], "fieldErrors": {...}}}`, 400
    (Pydantic now validates automatically; the response shape mimics Zod's `.flatten()`).
  - `requireAuth` failures → `{"error": "..."}`, 401 (bypasses the general error handler,
    same as the original — see `middlewares/error_handler.py`'s `AuthError`).
  - Everything else (business-logic failures like "already registered") → `{"error": "..."}`
    with the original status code, same as before.
  - Uncaught/unexpected errors → `{"status": "error", "message": "Something went wrong!"}`, 500.
  - 404 catch-all → `{"status": "fail", "message": "Route not found: ..."}` (same as `app.js`).
- **Login's constant-time dummy hash**: the JS file hardcodes a dummy bcrypt string for
  timing-attack resistance when the user doesn't exist. That exact string isn't a
  structurally valid hash for Python's `bcrypt` package (raises `Invalid salt` instead of
  just failing the comparison) — regenerated an equivalent dummy hash at the same cost
  factor (12) instead. Same property, different literal string.
- **Email TLS**: nodemailer's `secure: false` does _opportunistic_ STARTTLS (upgrade if the
  server offers it, don't require it). The naive Python mapping (`start_tls=True`) actually
  means "require STARTTLS, hard-fail if unsupported" in `aiosmtplib` — fixed to use
  `start_tls=None` (aiosmtplib's own opportunistic default) to match nodemailer's real behavior.
- **`catchAsync`**: dropped — never actually used in the controllers (Express 5 already
  auto-propagates async errors, and so does FastAPI). Nothing lost.

Everything else — validation rules, token TTLs, cookie paths/flags, refresh-token
rotation + reuse detection, password-reset one-time-use + expiry checks, the
constant-time login comparison — is a direct line-for-line port.

---

## Environment Variables

Same `.env` as the original — copy it over as-is, or use `.env.example` here. All the
same variables (`DATABASE_URL`, `JWT_ACCESS_SECRET`, `CLIENT_ORIGIN`, etc.) mean the
same thing and are read the same way.

> **Dev email**: `SMTP_HOST`/`PORT`/`USER`/`PASS` required — point at a Mailtrap sandbox
> inbox for dev. Reset link also logs to console when `NODE_ENV != production`.

---

## Getting Started

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Generate the Prisma Python client

```bash
prisma generate
```

This reads `prisma/schema.prisma` and generates the `db.user` / `db.refreshtoken` /
`db.passwordresettoken` client used throughout `controllers/auth_controller.py`.
Re-run this any time `schema.prisma` changes.

### 3. Set up the database

Tables already exist if you're pointing `DATABASE_URL` at the same DB the JS backend
used — migrations are unchanged, nothing to re-run. Fresh DB:

```bash
prisma migrate deploy
```

### 4. Start the dev server

```bash
python main.py
# or: uvicorn main:app --reload
# → Speeky-AI backend listening on port 8000
```

Health check: `GET http://localhost:8000/health`

Interactive API docs (FastAPI freebie, wasn't in the JS version): `http://localhost:8000/docs`

---

## API Reference

All routes are prefixed `/api/auth`. Unchanged from the original.

### Public

| Method | Path               | Body                         | Description                                                         |
| ------ | ------------------ | ---------------------------- | ------------------------------------------------------------------- |
| `POST` | `/signup`          | `{ email, password, name? }` | Register. Sets access + refresh cookies. Returns `{ user }`.        |
| `POST` | `/login`           | `{ email, password }`        | Login. Sets access + refresh cookies. Returns `{ user }`.           |
| `POST` | `/refresh`         | —                            | Rotate refresh token (reads cookie). Returns `{ user }`.            |
| `POST` | `/logout`          | —                            | Revokes refresh token, clears cookies. Returns `204`.               |
| `POST` | `/forgot-password` | `{ email }`                  | Sends reset email. Always returns `200` (no user enumeration).      |
| `POST` | `/reset-password`  | `{ token, password }`        | Resets password, revokes all refresh tokens. Returns `{ message }`. |

### Protected (requires valid `access_token` cookie)

| Method | Path  | Description                                            |
| ------ | ----- | ------------------------------------------------------ |
| `GET`  | `/me` | Returns current user `{ id, email, name, createdAt }`. |

---

## Authentication Flow

Identical to the original — see the JS README's diagram if you have it, or:

```
Client                        Server
  │── POST /signup ──────────▶│ hash password, create user
  │◀── Set-Cookie: access_token, refresh_token ──│
  │
  │── GET /me (cookie auto-sent) ──▶│ require_auth dependency verifies access_token
  │◀── { user } ────────────────────│
  │
  │── POST /refresh ─────────▶│ verify refresh_token, rotate (revoke old, issue new)
  │◀── Set-Cookie (new tokens) ──────│
  │
  │── POST /logout ──────────▶│ revoke refresh_token, clear cookies
  │◀── 204 ──────────────────────────│
```

### Token details

| Token           | Storage                            | TTL                   | Purpose                   |
| --------------- | ---------------------------------- | --------------------- | ------------------------- |
| `access_token`  | HTTP-only cookie, `path=/`         | 30 min (configurable) | Authenticate API requests |
| `refresh_token` | HTTP-only cookie, `path=/api/auth` | 7 days (configurable) | Obtain new access tokens  |

- Refresh tokens are **hashed (SHA-256)** before DB storage — raw token never persisted.
- **Token rotation** on every refresh — old token immediately revoked.
- **Reuse detection** — if a revoked refresh token is presented, all tokens for that user are revoked.

---

## Data Models

Unchanged — see `prisma/schema.prisma`. `User`, `RefreshToken`, `PasswordResetToken`.

---

## Error Handling

`AppError(message, status_code)` is only raised by the 404 catch-all route in
`main.py` and goes through `middlewares/error_handler.py`. Every other expected
failure (bad login, duplicate email, expired token, etc.) is returned directly from
the controller as `{"error": "..."}`, matching what the JS controllers did — they
never routed those through `AppError` either.

---

## Security Notes

Unchanged from the original:

- All JWT secrets must be at least 256-bit random hex.
- `access_token` cookie has `path=/`; `refresh_token` has `path=/api/auth`.
- Both cookies are `httponly`, `secure` (in production), `samesite=none` (prod) / `lax` (dev).
- Login uses constant-time bcrypt comparison even when the user doesn't exist.
- Forgot-password always returns 200 regardless of whether the email exists.
- Password reset tokens are hashed in DB (never stored raw).
- On password reset, all existing refresh tokens are revoked.

**Before this goes anywhere near production**: rotate `JWT_ACCESS_SECRET` /
`JWT_REFRESH_SECRET` and the `DATABASE_URL` credentials in `.env` — they were carried
over as-is from the JS backend's `.env` for a zero-friction drop-in, but that means
they're now sitting in two places.
