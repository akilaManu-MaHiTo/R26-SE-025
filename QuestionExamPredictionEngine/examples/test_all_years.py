"""
Comprehensive test for predict_topics and analyze_trends across all exam years (2021-2025).
"""
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.prediction.topic_prediction import predict_topics
from src.prediction.trend_analysis import analyze_trends


def main():
    exams_dir = PROJECT_ROOT / "data" / "exams"
    answers_dir = PROJECT_ROOT / "data" / "answers"
    
    exam_files = sorted(exams_dir.glob("exam*.json"))
    answer_files = sorted(answers_dir.glob("student_answers*.json"))
    
    print("="*70)
    print("COMPREHENSIVE TEST: predict_topics & analyze_trends (2021-2025)")
    print("="*70)
    
    # Test 1: predict_topics across all exam years
    print("\n[TEST 1] predict_topics() on each exam year:")
    print("-" * 70)
    for exam_file in exam_files:
        with exam_file.open() as f:
            exam = json.load(f)
        year = exam.get("year")
        exam_name = exam.get("exam", "Unknown")
        topics = [q.get("topic", f"Q{q.get('question_number')}") for q in exam.get("questions", [])]
        
        print(f"\n  {exam_file.name} (Year {year})")
        print(f"    Exam: {exam_name}")
        print(f"    Topics: {len(topics)}")
        print(f"    Topics: {', '.join(topics[:2])}...")
        
        # Test prediction on a sample answer
        sample_answer = "Database design and entity relationship models"
        preds = predict_topics(sample_answer, str(exam_file), top_n=2)
        if preds:
            print(f"    Sample prediction: {preds[0]['topic']} (score: {preds[0]['score']})")
    
    # Test 2: analyze_trends across multiple years
    print("\n\n[TEST 2] analyze_trends() on aggregated student data:")
    print("-" * 70)
    
    all_reports = []
    for answer_file in answer_files:
        year_match = answer_file.name.replace("student_answers", "").replace(".json", "")
        try:
            year = int(year_match) if year_match else 2021
        except:
            year = 2021
        
        with answer_file.open() as f:
            data = json.load(f)
        
        students = data if isinstance(data, list) else [data]
        for student in students:
            for q in student.get("answers", []):
                for part in q.get("parts", []):
                    topic = f"Q{q.get('question_number')}"
                    score = part.get("score", 0)
                    max_marks = part.get("max_marks", 1)
                    all_reports.append({
                        "year": year,
                        "topic": topic,
                        "learning_score": (score / max_marks) if max_marks else 0,
                        "student_id": student.get("student_id"),
                    })
    
    print(f"  Total mock reports: {len(all_reports)}")
    
    if all_reports:
        trends = analyze_trends(all_reports, by="topic", time_key="year")
        print(f"  Topics analyzed: {len(trends)}")
        
        print("\n  Top 3 topics by trend slope (improvement over time):")
        sorted_trends = sorted(trends.items(), key=lambda x: x[1]["slope"], reverse=True)
        for topic, summary in sorted_trends[:3]:
            print(f"    {topic}: slope={summary['slope']:.4f}, change={summary['change']:.4f}")
        
        print("\n  Sample topic trend details (Q1):")
        if "Q1" in trends:
            q1_trend = trends["Q1"]
            print(f"    Years available: {list(q1_trend['years'].keys())}")
            print(f"    Overall change: {q1_trend['change']}")
    
    print("\n" + "="*70)
    print("✅ Comprehensive test completed!")
    print("="*70)


if __name__ == "__main__":
    main()
