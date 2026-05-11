import json
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime


# Project setup
PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATA_EXAM_DIR = PROJECT_ROOT / "data" / "exams"
DATA_ANSWERS_DIR = PROJECT_ROOT / "data" / "answers"
OUTPUT_BASE_DIR = PROJECT_ROOT / "output"

sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis.scoring.cognitive import cognitive_score
from src.analysis.scoring.concept_scoring import extract_keywords, concept_score
from src.analytics.cognitive_gap_analysis import CognitiveGapAnalyzer
from src.analytics.misunderstood_questions import MisunderstoodQuestionsAnalyzer
from src.analytics.weak_topic_analysis import WeakTopicAnalyzer
from src.analytics.student_analysis import analyze_student_performance
from src.analytics.topic_utils import resolve_topic
from src.analytics.question_analysis import analyze_questions


# Load data
with (DATA_EXAM_DIR / "exam2021.json").open(encoding="utf-8") as f:
    exam_data = json.load(f)

with (DATA_ANSWERS_DIR / "student_answers2021.json").open(encoding="utf-8") as f:
    student_data = json.load(f)


# Normalize student data (single or multiple)
if isinstance(student_data, dict):
    students = [student_data]
else:
    students = student_data

# Storage
student_topic_scores = defaultdict(lambda: defaultdict(list))
student_reports = []


# Helper: get question text
def get_question_text(q_id, part_id):
    for q in exam_data["questions"]:
        if str(q["question_number"]) == str(q_id):
            for part in q["parts"]:
                if part["part"] == part_id:
                    return part["question"]
    return ""


# MAIN LOOP
print("Starting Analytics Engine...\n")

for student in students:

    student_id = student.get("student_id", "UNKNOWN")
    year = student.get("year", "UNKNOWN")
    exam_name = student.get("exam", "UNKNOWN")

    print(f"\nProcessing Student: {student_id}")

    for question in student.get("answers", []):
        q_id = str(question.get("question_number"))

        for part in question.get("parts", []):
            part_id = part.get("part")
            student_answer = part.get("answer", "")

            
            # External Score Input        
            score = part.get("score", 0)
            max_marks = part.get("max_marks", 1)

            performance_score = score / max_marks if max_marks else 0

        
            # Question Text            
            question_text = get_question_text(q_id, part_id)

            
            # Concept Analysis        
            keywords = extract_keywords(student_answer)
            concept = concept_score(student_answer, keywords)

            
            # Cognitive Analysis            
            cog = cognitive_score(question_text, student_answer)

            
            # Final Learning Score            
            learning_score = round(
                (0.6 * performance_score) +
                (0.25 * concept) +
                (0.15 * cog["cognitive_score"]),
                3
            )
            
            # Topic tracking (topic-level with question fallback)        
            topic_key = resolve_topic(exam_data, q_id, part_id, default=f"Q{q_id}{part_id}")
            student_topic_scores[student_id][topic_key].append(learning_score)

            
            # Store result        
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
                "topic": topic_key,
                "learning_score": learning_score
            })

            print(f"{student_id} → Q{q_id}{part_id} → LS: {learning_score} | Cog: {cog['student_level']}")


# Weak Topic Detection
weak_topics = WeakTopicAnalyzer(exam_data).analyze(student_reports)


# Create organized output directory structure
year = exam_data.get("year", "UNKNOWN")
exam_name = exam_data.get("exam", "PAPERS").replace(" ", "_")

# Create timestamped output folder
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = OUTPUT_BASE_DIR / str(year) / exam_name / timestamp

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print(f"\n📁 Output Directory: {OUTPUT_DIR}\n")


# Save outputs
with (OUTPUT_DIR / "student_report.json").open("w", encoding="utf-8") as f:
    json.dump(student_reports, f, indent=2)


# Question-level Analysis
question_summaries = analyze_questions(student_reports)
with (OUTPUT_DIR / "question_summary.json").open("w", encoding="utf-8") as f:
    json.dump(question_summaries, f, indent=2)

student_summaries = analyze_student_performance(student_reports)
misunderstood_questions = MisunderstoodQuestionsAnalyzer().analyze(student_reports)
cognitive_gaps = CognitiveGapAnalyzer().analyze(student_reports)

with (OUTPUT_DIR / "student_summary.json").open("w", encoding="utf-8") as f:
    json.dump(student_summaries, f, indent=2)

with (OUTPUT_DIR / "misunderstood_questions.json").open("w", encoding="utf-8") as f:
    json.dump(misunderstood_questions, f, indent=2)

with (OUTPUT_DIR / "cognitive_gap_analysis.json").open("w", encoding="utf-8") as f:
    json.dump(cognitive_gaps, f, indent=2)

with (OUTPUT_DIR / "weak_topics.json").open("w", encoding="utf-8") as f:
    json.dump(weak_topics, f, indent=2)

print("\nAnalytics Completed!")
print(f"Weak Topics Found: {len(weak_topics)}")
print(f"Student Summaries Found: {len(student_summaries)}")
print(f"Output saved to: {OUTPUT_DIR}")
print(f"Misunderstood Questions Found: {len(misunderstood_questions)}")
print(f"Cognitive Gaps Found: {len(cognitive_gaps)}")