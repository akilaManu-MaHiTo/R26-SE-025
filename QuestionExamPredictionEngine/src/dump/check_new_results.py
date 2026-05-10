import json
from pathlib import Path

# Get the latest output
output_dir = Path("QuestionExamPredictionEngine/output/2024/IT2040_–_Database_Management_Systems").glob("*")
latest = sorted(list(output_dir), key=lambda p: p.name)[-1]

# Load weak topics
with open(latest / "weak_topics.json") as f:
    weak_topics = json.load(f)

print(f"📊 WEAK TOPIC DETECTION RESULTS (with newly trained model)")
print(f"{'='*70}\n")

print(f"Total topics found: {len(weak_topics)}")
print(f"Status breakdown:\n")

status_counts = {}
for topic in weak_topics:
    status = topic.get("status", "UNKNOWN")
    status_counts[status] = status_counts.get(status, 0) + 1

for status, count in sorted(status_counts.items()):
    print(f"  {status}: {count}")

print(f"\n{'='*70}\n")

for i, topic in enumerate(weak_topics, 1):
    print(f"{i}. {topic['topic']}")
    print(f"   Status: {topic.get('status')} | Weak probability: {topic.get('weak_probability')}")
    print(f"   Weak students: {topic['weak_student_count']} / {topic['students_attempted']}")
    print(f"   Avg learning score: {topic['average_learning_score']}")
    print()
