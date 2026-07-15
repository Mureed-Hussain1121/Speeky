"""Speeky — Onboarding & Account Management API.

Implements the Onboarding & Account Management user stories (ONB-US-01..10).
Speech/NLP features live in the separate `speeky/` Python package; this service
is intentionally decoupled from it.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import account, auth, dev, privacy, profile, sessions, sso

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Speeky Onboarding & Account Management API",
    version="1.0.0",
    description="ONB-US-01..10 — registration, verification, login, profile, sessions, privacy, deletion.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "dev_mode": settings.dev_mode}


app.include_router(auth.router)
app.include_router(sso.router)
app.include_router(profile.router)
app.include_router(sessions.router)
app.include_router(privacy.router)
app.include_router(account.router)

# Dev-only helpers (mock email outbox inspection).
if settings.dev_mode:
    app.include_router(dev.router)
