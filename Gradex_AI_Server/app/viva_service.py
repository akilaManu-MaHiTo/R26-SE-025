"""Viva Evaluation Engine Service wrapper for the Gradex AI Server."""
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any

# Add VivaEvaluationEngine to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIVA_ENGINE_ROOT = PROJECT_ROOT / "VivaEvaluationEngine"
if str(VIVA_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(VIVA_ENGINE_ROOT))

try:
    from config import AppConfig
    from services.analysis_service import analyze_video
except ImportError as e:
    raise ImportError(f"Failed to import VivaEvaluationEngine modules: {e}")


def analyze_video_file(video_path: str, debug: bool = False) -> Dict[str, Any]:
    """
    Analyze a video file using the VivaEvaluationEngine.
    
    Args:
        video_path: Path to the video file
        debug: Enable debug output
        
    Returns:
        Dictionary containing the analysis results with timeline, scores, and summary
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
    
    # Create AppConfig with absolute model paths so imports work when called
    # from a different working directory (the server process).
    emotion_model_abs = str(VIVA_ENGINE_ROOT / "models" / "hsemotion_improved.pt")
    engagement_model_abs = str(VIVA_ENGINE_ROOT / "models" / "engagement_cnn.pt")

    config = AppConfig(
        video_path=video_path,
        output_path="",
        debug=debug,
        emotion_model_path=emotion_model_abs,
        engagement_model_path=engagement_model_abs,
    )
    
    # Run the analysis
    result = analyze_video(config, include_summary=True)
    
    return result
