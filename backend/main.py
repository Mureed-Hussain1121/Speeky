import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()  # must run before any os.environ reads below

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from lib.prisma_client import db
from middlewares.error_handler import (
    AuthError,
    app_error_handler,
    auth_error_handler,
    unhandled_exception_handler,
    validation_error_handler,
)
from routers.auth_routes import router as auth_router
from utils.app_error import AppError


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await db.connect()
    yield
    await db.disconnect()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("CLIENT_ORIGIN", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["GET", "POST","PATCH", "DELETE"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(AuthError, auth_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.get("/health")
async def health():
    return HTMLResponse("<h1>Speeky API is running!</h1>")


app.include_router(auth_router, prefix="/api/auth")


# Port of app.js's `app.all("/{*path}", ...)` catch-all 404 — must stay the LAST
# route registered, same as Express (route order = match order in both frameworks).
@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def not_found(full_path: str, request: Request):
    raise AppError(f"Route not found: {request.url.path}", 404)


if __name__ == "__main__":
    import uvicorn

    # ponytail: no uncaughtException/unhandledRejection handlers — uvicorn's worker
    # process model already exits/logs on unhandled errors; Node needed those
    # explicitly, Python's asyncio + uvicorn combo doesn't need the same guard.
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=os.environ.get("NODE_ENV") != "production",
    )
