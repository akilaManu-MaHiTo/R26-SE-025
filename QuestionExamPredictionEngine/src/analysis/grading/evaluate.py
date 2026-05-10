from pathlib import Path

from sentence_transformers import SentenceTransformer, util

from src.analysis.scoring.concept_scoring import extract_keywords, concept_score

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = PROJECT_ROOT / "model" / "similarity" / "exam_similarity_model"

model = SentenceTransformer(str(MODEL_PATH))

def grade_answer(model_answer, student_answer, max_marks):
    emb1 = model.encode(model_answer, convert_to_tensor=True)
    emb2 = model.encode(student_answer, convert_to_tensor=True)
    similarity = float(util.cos_sim(emb1, emb2))

    keywords = extract_keywords(model_answer)
    concept = concept_score(student_answer, keywords)

    final = (0.6 * similarity + 0.4 * concept)
    marks = round(final * max_marks, 2)

    return similarity, concept, marks


if __name__ == "__main__":
    print("Running test...")

    model_answer = "Second normal form (2NF) eliminates partial dependencies; a table is in 2NF if it is in 1NF and all non-key attributes are fully functionally dependent on the entire primary key"
    student_answer = "2NF removes transitive dependencies from a table"

    sim, concept, marks = grade_answer(model_answer, student_answer, 2)

    print("Similarity:", sim)
    print("Concept:", concept)
    print("Marks:", marks)