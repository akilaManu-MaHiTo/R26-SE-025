#!/usr/bin/env python
"""
Combine multiple student_report.json files into a single training dataset.

Usage:
  python combine_training_data.py

Output:
  training_data_combined.json (in workspace root)
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

# Root directory
PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_BASE = PROJECT_ROOT / "QuestionExamPredictionEngine" / "output"

def combine_reports():
    """Find all student_report.json files and merge them."""
    
    all_records = []
    sources = []
    
    # Find all student_report.json files
    report_files = sorted(list(OUTPUT_BASE.rglob("student_report.json")))
    
    if not report_files:
        print("❌ No student_report.json files found!")
        print(f"   Searched in: {OUTPUT_BASE}")
        return False
    
    print(f"📂 Found {len(report_files)} student report(s):\n")
    
    # Load and merge
    for report_path in report_files:
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                records = json.load(f)
            
            all_records.extend(records)
            
            # Extract metadata
            exam_name = report_path.parent.parent.name
            timestamp = report_path.parent.name
            cohort_size = len(set(r.get("student_id") for r in records))
            
            sources.append({
                "exam": exam_name,
                "timestamp": timestamp,
                "records": len(records),
                "students": cohort_size
            })
            
            print(f"   ✓ {exam_name}")
            print(f"     {len(records)} records, {cohort_size} students")
            
        except Exception as e:
            print(f"   ✗ Error reading {report_path}: {e}")
            continue
    
    print(f"\n{'='*70}")
    print(f"COMBINED STATISTICS")
    print(f"{'='*70}\n")
    
    # Analyze combined data
    unique_students = set(r.get("student_id") for r in all_records)
    unique_topics = set(r.get("topic") for r in all_records)
    unique_exams = set(r.get("exam") for r in all_records)
    weak_records = [r for r in all_records if r.get("learning_score", 1.0) < 0.5]
    
    print(f"Total records:        {len(all_records)}")
    print(f"Unique students:      {len(unique_students)}")
    print(f"Unique topics:        {len(unique_topics)}")
    print(f"Unique exams:         {len(unique_exams)}")
    print(f"Records < 0.5:        {len(weak_records)} ({100*len(weak_records)/len(all_records):.1f}%)")
    
    # Topic-level analysis
    print(f"\n{'='*70}")
    print(f"TOPIC ANALYSIS (what the model will see)")
    print(f"{'='*70}\n")
    
    topic_stats = defaultdict(lambda: {"weak": 0, "total": 0})
    for record in all_records:
        topic = record.get("topic", "Unknown")
        topic_stats[topic]["total"] += 1
        if record.get("learning_score", 1.0) < 0.5:
            topic_stats[topic]["weak"] += 1
    
    for topic, stats in sorted(topic_stats.items()):
        weak_pct = 100 * stats["weak"] / stats["total"] if stats["total"] else 0
        will_label = "WEAK" if stats["weak"] >= 0.4 * stats["total"] and stats["total"] >= 2 else "NON-WEAK"
        
        print(f"{topic}")
        print(f"  Attempts: {stats['total']:3d} | Weak: {stats['weak']:2d} ({weak_pct:5.1f}%) | Label: {will_label}")
    
    # Save combined file
    output_file = PROJECT_ROOT / "training_data_combined.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_records, f, indent=2)
    
    print(f"\n{'='*70}")
    print(f"✓ Saved to: {output_file}")
    print(f"{'='*70}\n")
    
    # Recommendations
    print("RECOMMENDATIONS:\n")
    
    if len(all_records) < 300:
        print(f"⚠️  Total records ({len(all_records)}) < 300")
        print("    → Collect more exam cycles to improve model")
    else:
        print(f"✓ Total records ({len(all_records)}) >= 300")
    
    if len(unique_students) < 30:
        print(f"⚠️  Unique students ({len(unique_students)}) < 30")
        print("    → Need more diverse student cohorts")
    else:
        print(f"✓ Unique students ({len(unique_students)}) >= 30")
    
    if len(unique_topics) < 10:
        print(f"⚠️  Unique topics ({len(unique_topics)}) < 10")
        print("    → Topics are too few; consider using finer-grained topic labels")
    else:
        print(f"✓ Unique topics ({len(unique_topics)}) >= 10")
    
    weak_pct = 100 * len(weak_records) / len(all_records) if all_records else 0
    if weak_pct < 15:
        print(f"⚠️  Weak records ({weak_pct:.1f}%) < 15%")
        print("    → Consider adding weaker cohorts or adjusting weak_threshold (currently 0.5)")
    else:
        print(f"✓ Weak records ({weak_pct:.1f}%) >= 15%")
    
    # Calculate expected weak topics
    weak_topics_count = sum(1 for stats in topic_stats.values() 
                           if stats["weak"] >= 0.4 * stats["total"] and stats["total"] >= 2)
    total_topics_count = len(topic_stats)
    weak_pct_topics = 100 * weak_topics_count / total_topics_count if total_topics_count else 0
    
    if weak_pct_topics < 20:
        print(f"⚠️  Expected weak topics ({weak_pct_topics:.0f}%) < 20%")
        print(f"    → Model will be trained on {weak_topics_count}/{total_topics_count} weak topics")
        print("    → Consider using historical data with more diverse performance")
    else:
        print(f"✓ Expected weak topics ({weak_pct_topics:.0f}%) >= 20%")
        print(f"    → Model will be trained on {weak_topics_count}/{total_topics_count} weak topics")
    
    print(f"\n{'='*70}")
    print("NEXT STEPS:\n")
    print("1. Review recommendations above")
    print("2. Train the model:")
    print(f"   python -m QuestionExamPredictionEngine.src.analysis.training.train_weak_topic_model \\")
    print(f"     --input training_data_combined.json")
    print("3. Test on new cohort:")
    print(f"   python QuestionExamPredictionEngine/src/analysis/grading/analyze_exam.py")
    print(f"{'='*70}\n")
    
    return True

if __name__ == "__main__":
    sys.exit(0 if combine_reports() else 1)
