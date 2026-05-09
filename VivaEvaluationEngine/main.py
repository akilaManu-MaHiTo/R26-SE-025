import argparse
import json
import os
import sys
from typing import Dict

from config import AppConfig
from services.analysis_service import analyze_video


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Facial Emotion Analysis CLI")
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
        save_output(result, config.output_path)

        print(json.dumps(result, indent=2))
        print(f"\nResults written to: {config.output_path}")

        if not result["timeline"]:
            print("Warning: No faces detected in sampled frames (1 FPS).")

        return 0

    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 1
    except Exception as exc:
        print(f"Unexpected error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
