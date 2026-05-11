"""Viva Evaluation Engine - Frame-by-frame emotion and engagement analysis."""

__version__ = "1.0.0"
__author__ = "Gradex AI Team"

# Expose main API
from services.analysis_service import analyze_video

__all__ = ["analyze_video"]
