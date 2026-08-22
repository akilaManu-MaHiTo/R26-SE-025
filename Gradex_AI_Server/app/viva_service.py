from pathlib import Path
import sys
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIVA_ENGINE_ROOT = PROJECT_ROOT / "VivaEvaluationEngine"

for path in (PROJECT_ROOT, VIVA_ENGINE_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.append(path_str)

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

    config = AppConfig(
        video_path=str(video),
        output_path=str(VIVA_ENGINE_ROOT / "outputs" / "results.json"),
        emotion_model_path=str(VIVA_ENGINE_ROOT / "models" / "hsemotion_improved.pt"),
        engagement_model_path=str(VIVA_ENGINE_ROOT / "models" / "engagement_cnn.pt"),
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
