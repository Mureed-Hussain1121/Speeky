from fastapi import APIRouter

from services.auth_serivce import (
    forgot_password,
    login,
    logout,
    me,
    refresh,
    reset_password,
    signup,
)

router = APIRouter()

# Public routes
router.add_api_route("/signup", signup, methods=["POST"])
router.add_api_route("/login", login, methods=["POST"])
router.add_api_route("/refresh", refresh, methods=["POST"])
router.add_api_route("/logout", logout, methods=["POST"])
router.add_api_route("/forgot-password", forgot_password, methods=["POST"])
router.add_api_route("/reset-password", reset_password, methods=["POST"])

# Protected routes (auth enforced via Depends(require_auth) on me() itself,
router.add_api_route("/me", me, methods=["GET"])
