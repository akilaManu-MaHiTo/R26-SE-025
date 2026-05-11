"""
Quick test script for predict_topics and analyze_trends.
Tests both functions on real exam/answer data from the data/ folder.
"""
import json
import sys
from pathlib import Path

# Setup paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import from src
from src.prediction.topic_prediction import predict_topics
from src.prediction.trend_analysis import analyze_trends


def test_predict_topics():
    """Test predict_topics on sample answers from 2021."""
    print("\n" + "="*60)
    print("TEST 1: predict_topics()")
    print("="*60)
    
    exam_path = PROJECT_ROOT / "data" / "exams" / "exam2021.json"
    
    # Sample student answers from 2021
    sample_answers = [
        "EER includes specialization and generalization. Specialization is dividing an entity into subtypes.",
        "Type1 JDBC-ODBC bridge, Type2 native API, Type3 network protocol, Type4 pure Java.",
        "SELECT Name, Email FROM Member WHERE MemberID IN (SELECT MemberID FROM Loan WHERE DueDate < CURDATE());",
    ]
    
    for i, answer in enumerate(sample_answers, 1):
        print(f"\n[Sample {i}] Answer: {answer[:60]}...")
        predictions = predict_topics(answer, str(exam_path), top_n=2)
        for pred in predictions:
            print(f"  - Topic: {pred['topic']}")
            print(f"    Score: {pred['score']}")
            print(f"    Matched terms: {pred['matched_terms'][:5]}")


def test_analyze_trends():
    """Test analyze_trends on generated student reports."""
    print("\n" + "="*60)
    print("TEST 2: analyze_trends()")
    print("="*60)
    
    # Load student reports for 2021 (simulated reports from analyze_exam.py output structure)
    # For now, create mock reports from student_answers2021.json
    answers_path = PROJECT_ROOT / "data" / "answers" / "student_answers2021.json"
    
    if not answers_path.exists():
        print(f"⚠ {answers_path} not found, skipping trend analysis test")
        return
    
    with answers_path.open() as f:
        data = json.load(f)
    
    # Convert to mock reports (expected by analyze_trends)
    mock_reports = []
    for student in (data if isinstance(data, list) else [data]):
        for q in student.get("answers", []):
            for part in q.get("parts", []):
                # Create report entry with required fields
                mock_reports.append({
                    "student_id": student.get("student_id"),
                    "year": student.get("year", 2021),
                    "topic": f"Q{q.get('question_number')}",  # Use question as pseudo-topic
                    "question": str(q.get("question_number")),
                    "part": part.get("part"),
                    "learning_score": (part.get("score", 0) / part.get("max_marks", 1)) if part.get("max_marks") else 0,
                })
    
    print(f"\nLoaded {len(mock_reports)} mock reports from student answers")
    
    # Analyze by topic (question)
    trends = analyze_trends(mock_reports, by="topic", time_key="year")
    print(f"\nTopic-level trends:")
    for topic, summary in list(trends.items())[:3]:  # Show first 3 topics
        print(f"\n  Topic: {topic}")
        print(f"    Slope: {summary['slope']}")
        print(f"    Years: {list(summary['years'].keys())}")
        print(f"    Latest avg: {summary['latest_avg']}")


def main():
    print("🚀 Testing predict_topics and analyze_trends implementations...\n")
    
    try:
        test_predict_topics()
        test_analyze_trends()
        print("\n" + "="*60)
        print("✅ All tests completed successfully!")
        print("="*60 + "\n")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
