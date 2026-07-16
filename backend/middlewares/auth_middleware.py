from fastapi import Depends, Request

from lib.prisma_client import db
from middlewares.error_handler import AuthError
from utils.jwt_utils import verify_access_token


async def require_auth(request: Request) -> str:
    token = request.cookies.get("access_token")
    if not token:
        raise AuthError("Not authenticated")
    try:
        payload = verify_access_token(token)
    except Exception:
        raise AuthError("Invalid or expired access token")
    return payload["sub"]


async def require_admin(user_id: str = Depends(require_auth)) -> str:
    """Admin-only dependency — use as `user_id: str = Depends(require_admin)`.
    Checks role from DB (not the JWT) so a role downgrade takes effect immediately
    instead of waiting for the access token to expire."""
    user = await db.user.find_unique(where={"id": user_id})
    if not user or user.role != "ADMIN":
        raise AuthError("Admin access required", 403)
    return user_id
