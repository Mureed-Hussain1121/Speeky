from fastapi import Request

from middlewares.error_handler import AuthError
from utils.jwt_utils import verify_access_token


async def require_auth(request: Request) -> str:
    """FastAPI dependency equivalent of requireAuth — use as:
    `user_id: str = Depends(require_auth)` on a route.
    Returns the userId (payload["sub"]), same as req.userId did in Express."""
    token = request.cookies.get("access_token")
    if not token:
        raise AuthError("Not authenticated")
    try:
        payload = verify_access_token(token)
    except Exception:
        raise AuthError("Invalid or expired access token")
    return payload["sub"]
