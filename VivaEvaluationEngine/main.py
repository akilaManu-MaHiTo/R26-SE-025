import argparse
import json
import os
import sys
from typing import Dict

from config import AppConfig
from services.analysis_service import analyze_video
from services.llm_judge import attach_llm_evaluation
from services.qa_relevance import attach_qa_analysis
from services.viva_analysis import analyze_audio_from_video


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Viva video + audio analysis CLI")
    parser.add_argument("--video", required=True, help="Path to the input video file")
    parser.add_argument(
        "--output",
        default="outputs/results.json",
        help="Path for output JSON file (default: outputs/results.json)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug output",
    )
    parser.add_argument(
        "--video-only",
        action="store_true",
        help="Skip audio pipeline (video scores only)",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM-as-judge enrichment (formula scores only still available via --skip-llm false default attaches fallback)",
    )
    return parser.parse_args()


def save_output(data: Dict[str, object], output_path: str) -> None:
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def main() -> int:
    args = parse_args()
    config = AppConfig(video_path=args.video, output_path=args.output, debug=args.debug)

    try:
        if not os.path.exists(config.video_path):
            raise FileNotFoundError(f"Video file not found: {config.video_path}")

        result = analyze_video(config, include_summary=True)
        if not args.video_only:
            face_cues = list(result.get("face_cues") or [])
            face_times = [
                float(item.get("time"))
                for item in (result.get("timeline") or [])
                if item.get("valid") and item.get("time") is not None
            ]
            audio_result = analyze_audio_from_video(
                config.video_path,
                debug=args.debug,
                face_times=face_times,
                face_cues=face_cues,
            )
            if isinstance(audio_result, dict):
                result.update(audio_result)

        if not args.skip_llm:
            result = attach_llm_evaluation(result, debug=args.debug)
        if not args.video_only:
            result = attach_qa_analysis(result, debug=args.debug)

        from services.assessment_scoring import attach_assessment

        result = attach_assessment(result)
        save_output(result, config.output_path)

        print(json.dumps(result, indent=2))
        print(f"\nResults written to: {config.output_path}")

        if not result.get("timeline"):
            print("Warning: No faces detected in sampled frames (1 FPS).")
        if result.get("video_status") == "insufficient_face_coverage":
            print("Error: Face coverage too low — official mark is INCOMPLETE. Point the camera at the student.")
        assessment = result.get("assessment") or {}
        if assessment.get("status") == "INCOMPLETE":
            print(f"Assessment INCOMPLETE: {assessment.get('validation', {}).get('message')}")
        llm = result.get("llm_evaluation") or {}
        if llm.get("status") == "fallback":
            print(f"Note: LLM judge used formula fallback ({llm.get('error')})")

        return 0

    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 1
    except Exception as exc:
        from services.video_processor import VideoUnreadableError

        if isinstance(exc, VideoUnreadableError):
            print(f"Error: {exc}")
            return 1
        print(f"Unexpected error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
