from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Sequence

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "model" / "cognitive_bloom" / "cognitive_bloom_model.joblib"

LEVEL_SCORES = {
    "remember": 1,
    "understand": 2,
    "apply": 3,
    "analyze": 4,
    "evaluate": 5,
    "create": 6,
}

DEFAULT_TEXT_COLUMNS = (
    "question",
    "answer",
    "source_text",
    "summary",
    "topic",
    "subtopic",
    "difficulty",
    "language",
    "cognitive_skill",
)


def normalize_level(value):
    if value is None:
        return ""

    return str(value).strip().lower()


def load_tabular_dataset(path: Path):
    suffix = path.suffix.lower()

    if suffix in {".json", ".jsonl"}:
        with path.open("r", encoding="utf-8") as handle:
            if suffix == ".jsonl":
                return [json.loads(line) for line in handle if line.strip()]

            data = json.load(handle)

        if isinstance(data, dict):
            for key in ("data", "rows", "records", "items"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            return [data]

        return data

    if suffix in {".csv", ".tsv"}:
        with path.open("r", encoding="utf-8", newline="") as handle:
            sample = handle.read(4096)
            handle.seek(0)

            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=[",", "\t", ";", "|"])
                delimiter = dialect.delimiter
            except csv.Error:
                delimiter = "\t" if "\t" in sample and "," not in sample else ","

            return list(csv.DictReader(handle, delimiter=delimiter))

    raise ValueError(f"Unsupported dataset format: {path.suffix}")


def build_text(record, text_columns: Sequence[str] = DEFAULT_TEXT_COLUMNS):
    parts = []

    for column in text_columns:
        value = record.get(column)
        if value is None:
            continue

        text = str(value).strip()
        if text:
            parts.append(f"{column}: {text}")

    if not parts:
        fallback = record.get("question") or record.get("answer") or record.get("source_text") or ""
        return str(fallback).strip()

    return " \n ".join(parts)


class CognitiveBloomModel:
    def __init__(self, model_path=DEFAULT_MODEL_PATH, label_column="bloom_level", text_columns=DEFAULT_TEXT_COLUMNS):
        self.model_path = Path(model_path) if model_path else None
        self.label_column = label_column
        self.text_columns = tuple(text_columns)
        self.pipeline = None
        self.metadata = {}

        if self.model_path and self.model_path.exists():
            self.load()

    def fit(self, rows):
        training_rows = []

        for row in rows or []:
            label = normalize_level(row.get(self.label_column) or row.get("cognitive_skill"))
            text = build_text(row, self.text_columns)
            if label and text:
                training_rows.append((text, label))

        if not training_rows:
            raise ValueError("No usable training rows were found")

        texts = [text for text, _ in training_rows]
        labels = [label for _, label in training_rows]

        label_counts = Counter(labels)
        if len(label_counts) < 2:
            raise ValueError("Cognitive Bloom model needs at least two label classes")

        stratify = labels if min(label_counts.values()) >= 2 and len(labels) >= 10 else None
        if stratify is not None:
            train_texts, test_texts, train_labels, test_labels = train_test_split(
                texts,
                labels,
                test_size=0.2,
                random_state=42,
                stratify=stratify,
            )
        else:
            train_texts, test_texts, train_labels, test_labels = texts, [], labels, []

        self.pipeline = Pipeline([
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    analyzer="word",
                    ngram_range=(1, 2),
                    min_df=2 if len(train_texts) >= 20 else 1,
                    max_features=50000,
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=3000,
                    random_state=42,
                ),
            ),
        ])

        self.pipeline.fit(train_texts, train_labels)

        self.metadata = {
            "label_column": self.label_column,
            "text_columns": list(self.text_columns),
            "label_counts": dict(label_counts),
            "training_rows": len(texts),
        }

        if test_texts:
            predictions = self.pipeline.predict(test_texts)
            accuracy = accuracy_score(test_labels, predictions)
            self.metadata["validation_accuracy"] = round(float(accuracy), 4)
            self.metadata["validation_report"] = classification_report(test_labels, predictions, zero_division=0, output_dict=True)

        return self

    def predict_level(self, text: str):
        if not self.pipeline:
            raise ValueError("Cognitive Bloom model is not trained or loaded")

        normalized_text = (text or "").strip()
        probabilities = self.pipeline.predict_proba([normalized_text])[0]
        classes = list(self.pipeline.classes_)
        best_index = int(probabilities.argmax())
        return classes[best_index], float(probabilities[best_index])

    def compare(self, question: str, student_answer: str, use_strict: bool = False):
        required_level, required_confidence = self.predict_level(question)
        student_level, student_confidence = self.predict_level(student_answer)

        required_score = LEVEL_SCORES.get(required_level, 3)
        student_score = LEVEL_SCORES.get(student_level, 3)

        ratio_score = min(student_score / required_score, 1.0) if required_score else 0.0
        confidence_penalty = (1 - student_confidence) * 0.25
        adjusted_score = ratio_score * (1 - confidence_penalty)

        if student_score > required_score:
            adjusted_score = min(adjusted_score + 0.1, 1.0)

        if use_strict and required_level != student_level:
            adjusted_score *= 0.7

        level_gap = student_score - required_score
        if level_gap < 0:
            cognitive_gap = "below_required"
            gap_severity = abs(level_gap)
        elif level_gap == 0:
            cognitive_gap = "matched"
            gap_severity = 0
        else:
            cognitive_gap = "above_required"
            gap_severity = level_gap

        return {
            "required_level": required_level,
            "student_level": student_level,
            "required_label": required_level.replace("_", " ").title() or "Basic",
            "student_label": student_level.replace("_", " ").title() or "Basic",
            "required_score": required_score,
            "student_score": student_score,
            "required_confidence": round(required_confidence, 2),
            "student_confidence": round(student_confidence, 2),
            "cognitive_score": round(float(adjusted_score), 2),
            "ratio_score": round(float(ratio_score), 2),
            "cognitive_gap": cognitive_gap,
            "gap_severity": gap_severity,
            "model_used": True,
        }

    def save(self):
        if not self.model_path or not self.pipeline:
            return

        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "pipeline": self.pipeline,
                "metadata": self.metadata,
            },
            self.model_path,
        )

    def load(self):
        payload = joblib.load(self.model_path)
        self.pipeline = payload["pipeline"]
        self.metadata = payload.get("metadata", {})
        self.label_column = self.metadata.get("label_column", self.label_column)
        self.text_columns = tuple(self.metadata.get("text_columns", self.text_columns))
        return self