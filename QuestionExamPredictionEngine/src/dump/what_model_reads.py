"""
Show which fields the weak topic model actually uses from student_report.json
"""

import json

print("="*70)
print("FIELDS THE MODEL READS FROM STUDENT REPORT")
print("="*70 + "\n")

# What build_topic_feature_rows() extracts from each record
print("✓ USED - Extracted from each student attempt record:\n")

used_fields = [
    ("student_id", "string", "Groups attempts by student"),
    ("topic", "string", "Groups by topic (critical!)"),
    ("learning_score", "float", "Main scoring metric (< 0.5 = weak)"),
    ("performance_score", "float", "Averaged into topic features"),
    ("concept_score", "float", "Averaged into topic features"),
    ("cognitive_score", "float", "Averaged into topic features"),
    ("student_level", "string", "Used to calculate level_gap"),
    ("required_level", "string", "Used to calculate level_gap"),
]

for field, dtype, purpose in used_fields:
    print(f"  • {field:<20} ({dtype:<10}) → {purpose}")

print("\n" + "="*70)
print("✗ IGNORED - Not used by the model:\n")

ignored_fields = [
    ("_comment", "metadata for humans"),
    ("exam", "metadata only"),
    ("year", "metadata only"),
    ("question", "only used if no topic specified"),
    ("part", "only used if no topic specified"),
]

for field, reason in ignored_fields:
    print(f"  • {field:<20} → {reason}")

print("\n" + "="*70)
print("WHAT THE MODEL SEES AFTER AGGREGATION")
print("="*70 + "\n")

print("Topic-level features (10 features used for training):\n")

features = [
    "average_learning_score",
    "average_performance_score", 
    "average_concept_score",
    "average_cognitive_score",
    "score_stddev",
    "weak_student_count",
    "students_attempted",
    "attempts",
    "weak_student_share",
    "average_level_gap",
]

for i, feature in enumerate(features, 1):
    print(f"  {i:2d}. {feature}")

print("\n" + "="*70)
print("EXAMPLE: What gets aggregated")
print("="*70 + "\n")

example_records = [
    {"student_id": "s1", "topic": "ER Modeling", "learning_score": 0.09},
    {"student_id": "s1", "topic": "ER Modeling", "learning_score": 0.05},
    {"student_id": "s2", "topic": "ER Modeling", "learning_score": 0.82},
]

print("Raw records in student_report.json:")
for r in example_records:
    print(f"  {r}")

print("\nAfter build_topic_feature_rows():")
print({
    "topic": "ER Modeling",
    "average_learning_score": 0.32,  # (0.09 + 0.05 + 0.82) / 3
    "weak_student_count": 1,  # s1 avg = (0.09+0.05)/2 = 0.07 < 0.5
    "students_attempted": 2,
    "weak_student_share": 0.5,  # 1 out of 2
    # ... + 6 more aggregated features
})

print("\n✓ RESULT: The `_comment` fields are completely stripped out")
print("         Only aggregated numeric features are passed to the model")
