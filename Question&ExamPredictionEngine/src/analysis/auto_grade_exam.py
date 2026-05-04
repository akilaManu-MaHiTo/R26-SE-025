import json
import os
from sentence_transformers import SentenceTransformer, util
from concept_scoring import extract_keywords, concept_score
from cognitive import cognitive_score

# 🔹 Load model
model = SentenceTransformer("exam_similarity_model")

# 🔹 Load files
with open("data/model_answers.json", encoding="utf-8") as f:
    model_answers = json.load(f)

with open("data/student_answers.json", encoding="utf-8") as f:
    student_answers = json.load(f)

with open("data/exam.json", encoding="utf-8") as f:
    exam_data = json.load(f)

results = []

print("Starting Auto Grading...\n")

# 🔹 Helper: get question text
def get_question_text(q_id, part_id):
    for q in exam_data["questions"]:
        if str(q["question_number"]) == str(q_id):
            for part in q["parts"]:
                if part["part"] == part_id:
                    return part["question"]
    return ""

# Main loop
for q_id, parts in model_answers.items():
    for part_id, model_answer in parts.items():

        try:
            student_answer = student_answers[q_id][part_id]
        except KeyError:
            print(f"⚠ Missing student answer for Q{q_id}{part_id}")
            continue

        question_text = get_question_text(q_id, part_id)

        # 🔹 Similarity
        emb1 = model.encode(model_answer, convert_to_tensor=True)
        emb2 = model.encode(student_answer, convert_to_tensor=True)
        similarity = float(util.cos_sim(emb1, emb2))

        # 🔹 Concept Score
        keywords = extract_keywords(model_answer)
        concept = concept_score(student_answer, keywords)

        # 🔹 Cognitive Score
        cog = cognitive_score(question_text, student_answer)

        # 🔹 Final Marks (you can tune weights)
        final_marks = round((0.5 * similarity + 0.3 * concept + 0.2 * cog["cognitive_score"]) * 2, 2)

        # 🔹 Store result
        result = {
            "question": q_id,
            "part": part_id,
            "similarity": round(similarity, 3),
            "concept": round(concept, 3),
            "cognitive_score": cog["cognitive_score"],
            "required_level": cog["required_level"],
            "student_level": cog["student_level"],
            "marks": final_marks
        }

        results.append(result)

        print(f"Q{q_id}{part_id} → {final_marks} | Cog: {cog['student_level']}")

# 🔹 Save results
os.makedirs("output", exist_ok=True)
with open("output/results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("\n Auto Grading Completed!")