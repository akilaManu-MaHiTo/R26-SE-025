import json
import sys
from pathlib import Path
from collections import defaultdict

# --------------------------------------------------
# Project setup
# --------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATA_EXAM_DIR = PROJECT_ROOT / "data" / "exams"
DATA_ANSWERS_DIR = PROJECT_ROOT / "data" / "answers"
OUTPUT_DIR = PROJECT_ROOT / "output"

sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis.scoring.cognitive import cognitive_score
from src.analysis.scoring.concept_scoring import extract_keywords, concept_score

# --------------------------------------------------
# Load data
# --------------------------------------------------
with (DATA_EXAM_DIR / "exam2021.json").open(encoding="utf-8") as f:
    exam_data = json.load(f)

with (DATA_ANSWERS_DIR / "student_answers2021.json").open(encoding="utf-8") as f:
    student_data = json.load(f)

# --------------------------------------------------
# Normalize student data (single or multiple)
# --------------------------------------------------
if isinstance(student_data, dict):
    students = [student_data]
else:
    students = student_data

# --------------------------------------------------
# Storage
# --------------------------------------------------
topic_stats = defaultdict(list)
student_reports = []

# --------------------------------------------------
# Helper: get question text
# --------------------------------------------------
def get_question_text(q_id, part_id):
    for q in exam_data["questions"]:
        if str(q["question_number"]) == str(q_id):
            for part in q["parts"]:
                if part["part"] == part_id:
                    return part["question"]
    return ""

# --------------------------------------------------
# MAIN LOOP
# --------------------------------------------------
print("Starting Analytics Engine...\n")

for student in students:

    student_id = student.get("student_id", "UNKNOWN")
    year = student.get("year", "UNKNOWN")
    exam_name = student.get("exam", "UNKNOWN")

    print(f"\n📘 Processing Student: {student_id}")

    for question in student.get("answers", []):
        q_id = str(question.get("question_number"))

        for part in question.get("parts", []):
            part_id = part.get("part")
            student_answer = part.get("answer", "")

            # --------------------------------------------------
            # External Score Input
            # --------------------------------------------------
            score = part.get("score", 0)
            max_marks = part.get("max_marks", 1)

            performance_score = score / max_marks if max_marks else 0

            # --------------------------------------------------
            # Question Text
            # --------------------------------------------------
            question_text = get_question_text(q_id, part_id)

            # --------------------------------------------------
            # Concept Analysis
            # --------------------------------------------------
            keywords = extract_keywords(student_answer)
            concept = concept_score(student_answer, keywords)

            # --------------------------------------------------
            # Cognitive Analysis
            # --------------------------------------------------
            cog = cognitive_score(question_text, student_answer)

            # --------------------------------------------------
            # Final Learning Score
            # --------------------------------------------------
            learning_score = round(
                (0.6 * performance_score) +
                (0.25 * concept) +
                (0.15 * cog["cognitive_score"]),
                3
            )

            # --------------------------------------------------
            # Topic tracking (Q + part level)
            # --------------------------------------------------
            topic_key = f"Q{q_id}{part_id}"
            topic_stats[topic_key].append(learning_score)

            # --------------------------------------------------
            # Store result
            # --------------------------------------------------
            student_reports.append({
                "student_id": student_id,
                "exam": exam_name,
                "year": year,
                "question": q_id,
                "part": part_id,
                "performance_score": round(performance_score, 3),
                "concept_score": round(concept, 3),
                "cognitive_score": cog["cognitive_score"],
                "student_level": cog["student_level"],
                "required_level": cog["required_level"],
                "learning_score": learning_score
            })

            print(f"{student_id} → Q{q_id}{part_id} → LS: {learning_score} | Cog: {cog['student_level']}")

# --------------------------------------------------
# Weak Topic Detection
# --------------------------------------------------
weak_topics = []

for topic, scores in topic_stats.items():
    avg = sum(scores) / len(scores)

    if avg < 0.5:
        weak_topics.append({
            "topic": topic,
            "average_learning_score": round(avg, 3),
            "status": "WEAK"
        })

# --------------------------------------------------
# Save outputs
# --------------------------------------------------
OUTPUT_DIR.mkdir(exist_ok=True)

with (OUTPUT_DIR / "student_report.json").open("w", encoding="utf-8") as f:
    json.dump(student_reports, f, indent=2)

with (OUTPUT_DIR / "weak_topics.json").open("w", encoding="utf-8") as f:
    json.dump(weak_topics, f, indent=2)

print("\nAnalytics Completed!")
print(f"Weak Topics Found: {len(weak_topics)}")