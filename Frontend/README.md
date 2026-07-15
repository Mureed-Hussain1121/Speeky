# Speeky — Onboarding Frontend (Next.js)

Next.js 14 (App Router, TypeScript) UI for the Onboarding & Account Management
stories (ONB-US-01 … ONB-US-10). It talks to the FastAPI backend in `../Backend`.

## Screens

| Route | Story |
| --- | --- |
| `/register` | ONB-US-08 registration + goal selection (+ mock Apple/Google SSO) |
| `/verify-email?token=…` | ONB-US-02 email verification |
| `/login` | ONB-US-01 login (+ resend verification, SSO, forgot-password link) |
| `/forgot-password` | ONB-US-03 request reset |
| `/reset-password?token=…` | ONB-US-03 set new password |
| `/dashboard` | goal-tailored home with mock score/skill level |
| `/profile` | ONB-US-04 profile edit + ONB-US-10 goal recalibration |
| `/security` | ONB-US-05 active sessions / remote logout |
| `/privacy` | ONB-US-06 consent management + history |
| `/delete-account` | ONB-US-07 deletion, grace period, cancel/restore |

## Run it

```bash
cd Frontend
npm install
cp .env.local.example .env.local   # points at http://localhost:8000 by default
npm run dev                        # http://localhost:3000
```

Start the backend first (see `../Backend/README.md`).

## Notes

- Apple/Google buttons open a small **mock simulator** (the real providers aren't
  wired yet) so you can exercise Hide-My-Email, share-email, and failure paths.
- Because email is mocked, verification/reset links are printed to the backend
  console and available at `GET http://localhost:8000/dev/outbox`.
- Tokens: a short-lived JWT access token + refresh token are stored in
  `localStorage`; the API client (`app/lib/api.ts`) auto-refreshes once on 401.
- `score` and `skill_level` shown on the dashboard/profile are **mock** fields
  owned by the Gameification and Baseline Assessment features.
