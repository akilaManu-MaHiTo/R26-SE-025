"""
Handwritten grading API on the common Gradex AI Server.

Routes are served at ``/api/grading/*`` (GradingEngine sub-app), same pattern as
``/api/analytics/*`` and ``/api/viva-*``.
"""
from __future__ import annotations

from fastapi import FastAPI

from Gradex_AI_Server.app.grading_integration import (
    GRADING_MOUNT_PATH,
    grading_enabled,
    preload_grading_engine,
    register_grading_routes,
)


def setup_grading_api(app: FastAPI) -> bool:
    """Preload GradingEngine (if needed) and mount at /api/grading."""
    if not grading_enabled():
        preload_grading_engine()
    return register_grading_routes(app)


__all__ = ["GRADING_MOUNT_PATH", "setup_grading_api"]
