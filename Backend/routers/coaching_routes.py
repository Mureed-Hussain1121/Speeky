from fastapi import APIRouter

from services.coaching_service import (
    get_scenarios,
    get_session,
    roleplay_turn,
    start_session,
    submit_session,
)

router = APIRouter()

# Workplace English Coach (WEC-US-08 .. WEC-US-12)
router.add_api_route("/scenarios", get_scenarios, methods=["GET"])
router.add_api_route("/start", start_session, methods=["POST"])
router.add_api_route("/{session_id}/turn", roleplay_turn, methods=["POST"])
router.add_api_route("/{session_id}/submit", submit_session, methods=["POST"])
router.add_api_route("/{session_id}", get_session, methods=["GET"])
