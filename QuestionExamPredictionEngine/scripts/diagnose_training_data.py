"""Diagnose the weak topic training data to understand what makes good training data."""
import sys
import json
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, '.')

from QuestionExamPredictionEngine.src.analytics.weak_topic_model import (
    build_topic_feature_rows, WeakTopicModel
)

# Find all student_report.json files to understand training data patterns
output_base = Path("QuestionExamPredictionEngine/output")
reports = list(output_base.rglob("student_report.json"))

print(f"Found {len(reports)} student reports\n")

# Collect stats from each cohort
for report_path in sorted(reports)[-5:]:  # Last 5 cohorts
    with open(report_path) as f:
        student_records = json.load(f)
    
    if not student_records:
        continue
    
    output_dir = report_path.parent
    weak_topics_path = output_dir / "weak_topics.json"
    
    # Get topic features
    rows = build_topic_feature_rows(student_records)
    
    # Count labels
    weak_count = sum(1 for r in rows if r.get("label") == 1)
    non_weak_count = sum(1 for r in rows if r.get("label") == 0)
    
    print(f"📊 {output_dir.parent.name}")
    print(f"   Total topics: {len(rows)}")
    print(f"   Topics labeled WEAK: {weak_count}")
    print(f"   Topics labeled non-weak: {non_weak_count}")
    
    # Topic details
    unique_students = len(set(r.get("student_id") for r in student_records))
    unique_attempts = len(student_records)
    print(f"   Students: {unique_students}, Total attempts: {unique_attempts}")
    
    # Show which topics were marked weak during training
    if weak_topics_path.exists():
        with open(weak_topics_path) as f:
            weak_topics = json.load(f)
        weak_status = sum(1 for t in weak_topics if t.get("status") == "WEAK")
        print(f"   Runtime detection: {weak_status} WEAK topics")
    
    print()

print("\n" + "="*70)
print("WHAT MAKES GOOD TRAINING DATA FOR WEAK TOPIC DETECTION")
print("="*70 + "\n")

print("1. TOPIC VARIETY (coverage)")
print("   - More than 4-6 topics in each exam (current: 4)")
print("   - Multiple exams across different courses/difficulty levels")
print("   - → This gives the model diverse patterns to learn from\n")

print("2. STUDENT DIVERSITY (variance)")
print("   - At least 15-30 students per cohort (current: 10)")
print("   - Wide range of performance levels (not all high performers)")
print("   - → This creates natural weak and non-weak examples\n")

print("3. BALANCED LABELS (equal weak/non-weak topics)")
print("   - Ideally 40-50% topics are actually weak")
print("   - Current: {0} weak, {1} non-weak → {2:.0f}% weak".format(
        weak_count, non_weak_count, 100*weak_count/(weak_count+non_weak_count+0.0001)
    ))
print("   - If imbalanced, model can't learn boundaries well\n")

print("4. SUFFICIENT ATTEMPTS (signal quality)")
print("   - At least 20-30 total student attempts per topic")
print("   - Multiple students per topic (>= 3-5)")
print("   - → Reduces noise from single outliers\n")

print("5. TEMPORAL DIVERSITY (real-world drift)")
print("   - Train on multiple exam cycles (this year, last year, etc.)")
print("   - Different cohorts may struggle with different topics")
print("   - → Model generalizes better to new cohorts\n")
