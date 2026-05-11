from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.analytics.weak_topic_model import DEFAULT_MODEL_PATH, WeakTopicModel, build_topic_feature_rows


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT_PATH = PROJECT_ROOT / "data" / "traindata" / "student_data_V3.json"


def load_records(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main():
    parser = argparse.ArgumentParser(description="Train the weak topic detection model")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH, help="Path to student_report.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_MODEL_PATH, help="Path to save the trained model")
    parser.add_argument("--weak-threshold", type=float, default=0.5, help="Learning score threshold used to bootstrap labels")
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")

    records = load_records(args.input)
    topic_rows = build_topic_feature_rows(records, weak_threshold=args.weak_threshold)

    if not topic_rows:
        raise ValueError("No topic rows were built from the input data")

    model = WeakTopicModel(model_path=args.output)
    model.fit(topic_rows)
    model.save()

    weak_topics = model.predict(topic_rows)
    print(f"Trained weak topic model on {len(topic_rows)} topics")
    print(f"Saved model to {args.output}")
    print(f"Detected {sum(1 for item in weak_topics if item['status'] == 'WEAK')} weak topics in the training set")


if __name__ == "__main__":
    main()
