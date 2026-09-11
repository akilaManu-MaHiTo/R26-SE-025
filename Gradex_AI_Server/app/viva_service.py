from pathlib import Path
import sys
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIVA_ENGINE_ROOT = PROJECT_ROOT / "VivaEvaluationEngine"

# Only the repo root needs to be on sys.path so `VivaEvaluationEngine` itself
# is importable as a package. Importing it runs its own __init__.py, which
# registers the engine's directory for its internal absolute imports
# (`from services.x import y`, `from config import ...`) — no separate
# sys.path entry for VIVA_ENGINE_ROOT is needed here any more.
project_root_str = str(PROJECT_ROOT)
if project_root_str not in sys.path:
    sys.path.append(project_root_str)

from VivaEvaluationEngine.config import AppConfig
from VivaEvaluationEngine.services.analysis_service import analyze_video
from VivaEvaluationEngine.services.llm_judge import attach_llm_evaluation
from VivaEvaluationEngine.services.qa_relevance import attach_qa_analysis
from VivaEvaluationEngine.services.viva_analysis import analyze_audio_from_video


def _assert_required_models_exist() -> None:
    required = [
        VIVA_ENGINE_ROOT / "models" / "hsemotion_improved.pt",
        VIVA_ENGINE_ROOT / "models" / "engagement_cnn.pt",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing Viva model files: " + ", ".join(missing)
        )


def analyze_video_file(video_path: str, debug: bool = False) -> Dict[str, Any]:
    video = Path(video_path)
    if not video.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    _assert_required_models_exist()

    # output_path / emotion_model_path / engagement_model_path all default to
    # paths resolved against the engine's own directory (see config.py), so
    # no override is needed here regardless of this process's CWD.
    config = AppConfig(
        video_path=str(video),
        debug=debug,
    )

    result = analyze_video(config, include_summary=True)
    face_cues = list(result.get("face_cues") or [])
    face_times = [
        float(item.get("time"))
        for item in (result.get("timeline") or [])
        if item.get("valid") and item.get("time") is not None
    ]
    audio_result = analyze_audio_from_video(
        str(video), debug=debug, face_times=face_times, face_cues=face_cues
    )

    if isinstance(audio_result, dict):
        result.update(audio_result)

    merged = attach_llm_evaluation(result, debug=debug)
    merged = attach_qa_analysis(merged, debug=debug)
    from VivaEvaluationEngine.services.assessment_scoring import attach_assessment

    return attach_assessment(merged)
