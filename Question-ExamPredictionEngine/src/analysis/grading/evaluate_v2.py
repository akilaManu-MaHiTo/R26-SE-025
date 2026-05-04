from pathlib import Path

from sentence_transformers import SentenceTransformer, util

from src.analysis.scoring.concept_scoring import extract_keywords, concept_score

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = PROJECT_ROOT / "model" / "similarity" / "exam_similarity_model"

model = SentenceTransformer(str(MODEL_PATH))

def grade_answer(model_answer, student_answer, max_marks):
    """
    Grade a student answer against the model answer.
    
    Args:
        model_answer (str): The correct/model answer
        student_answer (str): The student's answer
        max_marks (float): Maximum marks for this question
    
    Returns:
        tuple: (similarity_score, concept_score, marks_obtained)
    """
    # Encode and calculate semantic similarity
    emb1 = model.encode(model_answer, convert_to_tensor=True)
    emb2 = model.encode(student_answer, convert_to_tensor=True)
    similarity = float(util.cos_sim(emb1, emb2))
    
    # Extract keywords and calculate concept score
    keywords = extract_keywords(model_answer)
    concept = concept_score(student_answer, keywords)
    
    # Apply penalty for completely wrong concepts
    if concept < 0.2:
        # Student fundamentally misunderstood the concept
        penalty = 0.3
    elif concept < 0.4:
        # Student has major conceptual errors
        penalty = 0.6
    elif concept < 0.6:
        # Student has partial understanding
        penalty = 0.85
    else:
        # Student understands the concept well
        penalty = 1.0
    
    # Weighted combination (concept matters more for conceptual questions)
    # Weights: 30% similarity, 70% concept
    raw_score = (0.3 * similarity + 0.7 * concept) * penalty
    
    # Ensure score doesn't exceed 1.0
    final_score = min(raw_score, 1.0)
    
    # Calculate marks
    marks = round(final_score * max_marks, 2)
    
    return similarity, concept, marks


def grade_answer_with_feedback(model_answer, student_answer, max_marks):
    """
    Grade a student answer and return detailed feedback.
    
    Args:
        model_answer (str): The correct/model answer
        student_answer (str): The student's answer
        max_marks (float): Maximum marks for this question
    
    Returns:
        dict: Detailed grading results with feedback
    """
    # Get base scores
    similarity, concept, marks = grade_answer(model_answer, student_answer, max_marks)
    
    # Generate feedback based on scores
    if concept >= 0.8:
        feedback = "Excellent! You have a strong understanding of the concept."
    elif concept >= 0.6:
        feedback = "Good understanding, but there are minor gaps in your knowledge."
    elif concept >= 0.4:
        feedback = "Fair understanding. Review the key concepts and try again."
    elif concept >= 0.2:
        feedback = "Weak understanding. Major conceptual errors detected."
    else:
        feedback = "Poor understanding. Please thoroughly review this topic."
    
    # Add specific feedback for similarity vs concept mismatch
    if similarity > 0.7 and concept < 0.4:
        feedback += " Note: Your answer sounds correct but is conceptually wrong. Focus on understanding concepts, not just memorizing phrases."
    
    return {
        "similarity": similarity,
        "concept_score": concept,
        "marks_obtained": marks,
        "max_marks": max_marks,
        "percentage": round((marks / max_marks) * 100, 2),
        "feedback": feedback
    }


if __name__ == "__main__":
    print("=" * 60)
    print("Exam Grading System - Test Run")
    print("=" * 60)
    
    # Test Case 1: Wrong answer (2NF vs 3NF confusion)
    print("\n[TEST 1] Student confuses 2NF with 3NF")
    print("-" * 40)
    model_answer = "Second normal form (2NF) eliminates partial dependencies; a table is in 2NF if it is in 1NF and all non-key attributes are fully functionally dependent on the entire primary key"
    student_answer = "2NF removes transitive dependencies from a table"
    
    result = grade_answer_with_feedback(model_answer, student_answer, 2)
    print(f"Similarity Score: {result['similarity']:.4f}")
    print(f"Concept Score: {result['concept_score']:.4f}")
    print(f"Marks: {result['marks_obtained']} / {result['max_marks']}")
    print(f"Percentage: {result['percentage']}%")
    print(f"Feedback: {result['feedback']}")
    
    # Test Case 2: Correct answer
    print("\n[TEST 2] Student gives correct answer")
    print("-" * 40)
    model_answer2 = "ACID stands for Atomicity, Consistency, Isolation, Durability"
    student_answer2 = "ACID = Atomicity, Consistency, Isolation, Durability"
    
    result2 = grade_answer_with_feedback(model_answer2, student_answer2, 2)
    print(f"Similarity Score: {result2['similarity']:.4f}")
    print(f"Concept Score: {result2['concept_score']:.4f}")
    print(f"Marks: {result2['marks_obtained']} / {result2['max_marks']}")
    print(f"Percentage: {result2['percentage']}%")
    print(f"Feedback: {result2['feedback']}")
    
    # Test Case 3: Partially correct answer
    print("\n[TEST 3] Student gives partially correct answer")
    print("-" * 40)
    model_answer3 = "A primary key uniquely identifies each row and cannot be null; a foreign key references a primary key in another table"
    student_answer3 = "Primary key is unique, foreign key links to another table"
    
    result3 = grade_answer_with_feedback(model_answer3, student_answer3, 3)
    print(f"Similarity Score: {result3['similarity']:.4f}")
    print(f"Concept Score: {result3['concept_score']:.4f}")
    print(f"Marks: {result3['marks_obtained']} / {result3['max_marks']}")
    print(f"Percentage: {result3['percentage']}%")
    print(f"Feedback: {result3['feedback']}")
    
    # Test Case 4: Completely wrong answer
    print("\n[TEST 4] Student gives completely wrong answer")
    print("-" * 40)
    model_answer4 = "A JOIN combines rows from two tables based on a related column"
    student_answer4 = "JOIN deletes duplicate rows from a single table"
    
    result4 = grade_answer_with_feedback(model_answer4, student_answer4, 2)
    print(f"Similarity Score: {result4['similarity']:.4f}")
    print(f"Concept Score: {result4['concept_score']:.4f}")
    print(f"Marks: {result4['marks_obtained']} / {result4['max_marks']}")
    print(f"Percentage: {result4['percentage']}%")
    print(f"Feedback: {result4['feedback']}")
    
    print("\n" + "=" * 60)
    print("Testing Complete")
    print("=" * 60)