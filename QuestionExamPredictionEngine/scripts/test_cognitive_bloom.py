"""Quick test script for the cognitive Bloom model.

Loads model/cognitive_bloom/cognitive_bloom_model.joblib and runs
predict_level and compare on sample questions and student answers.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analysis.scoring.cognitive_bloom_model import CognitiveBloomModel

SAMPLE_QUESTIONS = [
    "What is the primary key?",
    "Explain the difference between specialization and generalization in EER modeling.",
    "Apply normalization to remove the partial dependency from this table.",
    "Analyze whether this schema satisfies BCNF.",
    "Design a relational schema for the library system from the given ER diagram.",
]

SAMPLE_COMPARISONS = [
    ("Explain normalization and its normal forms.", "Normalization removes redundancy. 3NF removes transitive dependencies."),
    ("What is a foreign key?", "A foreign key references a primary key in another table."),
    ("Create a query that lists all members with overdue loans.", "SELECT Name FROM Member WHERE MemberID IN (SELECT MemberID FROM Loan WHERE DueDate < CURDATE());"),
]


def main():
    model = CognitiveBloomModel()
    if model.pipeline is None:
        print("Error: cognitive Bloom model could not be loaded")
        sys.exit(1)

    print("=" * 60)
    print("COGNITIVE BLOOM MODEL TEST")
    print("=" * 60)
    print(f"Label column: {model.metadata.get('label_column')}")
    print(f"Training rows: {model.metadata.get('training_rows')}")
    print(f"Label counts: {model.metadata.get('label_counts')}")
    if "validation_accuracy" in model.metadata:
        print(f"Validation accuracy: {model.metadata['validation_accuracy']}")
    print()

    print("TEST 1: predict_level()")
    print("-" * 60)
    for question in SAMPLE_QUESTIONS:
        level, confidence = model.predict_level(question)
        print(f"[{level:<9} {confidence:.2f}] {question}")

    print()
    print("TEST 2: compare(question, student_answer)")
    print("-" * 60)
    for question, answer in SAMPLE_COMPARISONS:
        result = model.compare(question, answer)
        print(f"Q: {question}")
        print(f"A: {answer}")
        print(f"  required={result['required_level']} ({result['required_score']}) "
              f"student={result['student_level']} ({result['student_score']})")
        print(f"  cognitive_score={result['cognitive_score']} gap={result['cognitive_gap']}")
        print()


if __name__ == "__main__":
    main()
