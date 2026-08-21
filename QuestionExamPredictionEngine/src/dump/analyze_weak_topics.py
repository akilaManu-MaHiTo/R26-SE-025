import sys
import json
from pathlib import Path
sys.path.insert(0, '.')

OUTPUT_BASE_DIR = Path(__file__).resolve().parent / "QuestionExamPredictionEngine" / "output"

# Find the most recent output
output_dirs = sorted([d for d in (OUTPUT_BASE_DIR / "2025").rglob("weak_topics.json")])
if not output_dirs:
    print("No weak_topics.json found")
    sys.exit(1)

latest = output_dirs[-1]
output_dir = latest.parent

print(f"Latest output: {output_dir}\n")

# Load weak topics
with open(output_dir / "weak_topics.json") as f:
    weak_topics = json.load(f)

print(f"Total topics found: {len(weak_topics)}")
print(f"Status breakdown:")
status_counts = {}
for topic in weak_topics:
    status = topic.get("status", "UNKNOWN")
    status_counts[status] = status_counts.get(status, 0) + 1
    
for status, count in sorted(status_counts.items()):
    print(f"  {status}: {count}")

print("\n" + "="*70)
print("Top 4 topics (highest weak_probability):")
print("="*70 + "\n")

for i, topic in enumerate(weak_topics[:4], 1):
    print(f"{i}. {topic['topic']}")
    print(f"   Status: {topic.get('status', 'N/A')}")
    print(f"   Weak probability: {topic.get('weak_probability', 'N/A')}")
    print(f"   Weak student count: {topic['weak_student_count']} / {topic['students_attempted']}")
    print(f"   Learning score: {topic['average_learning_score']} (stddev: {topic['score_stddev']})")
    print(f"   Performance: {topic['average_performance_score']}")
    print(f"   Cognitive gap: {topic['average_level_gap']}")
    print()
