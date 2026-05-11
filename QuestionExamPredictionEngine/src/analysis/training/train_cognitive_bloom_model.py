from __future__ import annotations

import argparse
from pathlib import Path

from src.analysis.scoring.cognitive_bloom_model import (
    CognitiveBloomModel,
    DEFAULT_MODEL_PATH,
    load_tabular_dataset,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT_PATH = PROJECT_ROOT / "data" / "train_cognitive_bloom.json"


def main():
    parser = argparse.ArgumentParser(description="Train a Bloom-level cognitive model")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH, help="Path to JSON, JSONL, CSV, or TSV training data")
    parser.add_argument("--output", type=Path, default=DEFAULT_MODEL_PATH, help="Path to save the trained model")
    parser.add_argument("--label-column", default="bloom_level", help="Label column to predict")
    parser.add_argument(
        "--text-columns",
        nargs="+",
        default=["question", "answer", "source_text", "summary", "topic", "subtopic", "difficulty", "language", "cognitive_skill"],
        help="Columns to combine into the text input",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")

    rows = load_tabular_dataset(args.input)
    if not rows:
        raise ValueError("Training file did not contain any rows")

    model = CognitiveBloomModel(model_path=args.output, label_column=args.label_column, text_columns=args.text_columns)
    model.fit(rows)
    model.save()

    print(f"Trained Bloom model on {model.metadata.get('training_rows', 0)} rows")
    print(f"Saved model to {args.output}")

    if "validation_accuracy" in model.metadata:
        print(f"Validation accuracy: {model.metadata['validation_accuracy']:.4f}")


if __name__ == "__main__":
    main()