import re
from typing import Dict, Tuple, List, Optional

# Bloom's Taxonomy keyword mapping
BLOOM_LEVELS = {
    "remember": ["define", "list", "identify", "name", "state", "recite", "recall", "match", "label"],
    "understand": ["explain", "describe", "summarize", "interpret", "paraphrase", "clarify", "classify", "discuss"],
    "apply": ["use", "solve", "implement", "demonstrate", "execute", "compute", "calculate", "operate"],
    "analyze": ["analyze", "compare", "differentiate", "examine", "contrast", "categorize", "distinguish", "investigate"],
    "evaluate": ["justify", "argue", "critique", "evaluate", "assess", "defend", "judge", "validate"],
    "create": ["design", "develop", "construct", "formulate", "propose", "synthesize", "compose", "plan"]
}

# Numeric scores for each level (1-6)
LEVEL_SCORES = {
    "remember": 1,
    "understand": 2,
    "apply": 3,
    "analyze": 4,
    "evaluate": 5,
    "create": 6
}

# Human-readable labels
LEVEL_LABELS = {
    "remember": "Low (Recall)",
    "understand": "Basic (Comprehension)",
    "apply": "Intermediate (Application)",
    "analyze": "Advanced (Analysis)",
    "evaluate": "High (Evaluation)",
    "create": "Expert (Creation)"
}


def detect_level(text: str, context: str = "question") -> Tuple[str, float]:
    """
    Detect Bloom's Taxonomy level from text with confidence score.
    
    Args:
        text (str): Text to analyze (question or answer)
        context (str): Either "question" or "answer" (affects default behavior)
    
    Returns:
        Tuple[str, float]: (level, confidence_score)
    """
    if not text or not text.strip():
        return "understand", 0.5
    
    text_lower = text.lower()
    word_count = len(text_lower.split())
    
    # Score each level based on keyword matches
    level_scores = {}
    
    for level, keywords in BLOOM_LEVELS.items():
        matches = 0
        for keyword in keywords:
            # Count all occurrences, not just first match
            matches += len(re.findall(rf'\b{re.escape(keyword)}\b', text_lower))
        
        if matches > 0:
            level_scores[level] = matches
    
    if not level_scores:
        # No keywords found - infer from text characteristics
        if word_count < 10:
            return "remember", 0.4
        elif word_count < 25:
            return "understand", 0.5
        elif word_count < 50:
            return "apply", 0.5
        else:
            return "analyze", 0.4
    
    # Get level with highest match count
    best_level = max(level_scores, key=level_scores.get)
    
    # Calculate confidence based on match density and uniqueness
    max_matches = level_scores[best_level]
    total_keywords = max(1, sum(level_scores.values()))
    confidence = min(max_matches / total_keywords, 1.0)
    
    # Adjust for very short texts
    if word_count < 5 and confidence > 0.8:
        confidence = 0.6  # Lower confidence for very short answers
    
    return best_level, round(confidence, 2)


def cognitive_score(question: str, student_answer: str, use_strict: bool = False) -> Dict:
    """
    Calculate cognitive alignment score between question and answer.
    
    Args:
        question (str): The question or model answer text
        student_answer (str): Student's answer
        use_strict (bool): If True, requires exact level match for high scores
    
    Returns:
        Dict: Cognitive analysis results
    """
    q_level, q_conf = detect_level(question, "question")
    s_level, s_conf = detect_level(student_answer, "answer")
    
    q_score = LEVEL_SCORES.get(q_level, 3)
    s_score = LEVEL_SCORES.get(s_level, 3)
    
    # Base ratio score (can't exceed required level)
    ratio_score = min(s_score / q_score, 1.0)
    
    # Confidence adjustment
    confidence_penalty = (1 - s_conf) * 0.25  # Max 25% penalty
    adjusted_score = ratio_score * (1 - confidence_penalty)
    
    # Bonus for exceeding required level (capped at 1.0)
    if s_score > q_score:
        adjusted_score = min(adjusted_score + 0.1, 1.0)
    
    # Strict mode penalty for level mismatch
    if use_strict and q_level != s_level:
        adjusted_score *= 0.7
    
    # Additional metrics
    level_gap = s_score - q_score
    if level_gap < 0:
        cognitive_gap = "below_required"
        gap_severity = abs(level_gap)
    elif level_gap == 0:
        cognitive_gap = "matched"
        gap_severity = 0
    else:
        cognitive_gap = "above_required"
        gap_severity = level_gap
    
    return {
        "required_level": q_level,
        "student_level": s_level,
        "required_label": LEVEL_LABELS.get(q_level, "Basic"),
        "student_label": LEVEL_LABELS.get(s_level, "Basic"),
        "required_score": q_score,
        "student_score": s_score,
        "required_confidence": q_conf,
        "student_confidence": s_conf,
        "cognitive_score": round(adjusted_score, 2),
        "ratio_score": round(ratio_score, 2),
        "cognitive_gap": cognitive_gap,
        "gap_severity": gap_severity
    }


def level_to_label(level: str) -> str:
    """Convert Bloom level to human-readable label."""
    return LEVEL_LABELS.get(level, "Basic")


def get_cognitive_feedback(cognitive_result: Dict) -> str:
    """
    Generate feedback based on cognitive analysis.
    
    Args:
        cognitive_result (Dict): Output from cognitive_score()
    
    Returns:
        str: Feedback message
    """
    required = cognitive_result["required_level"]
    student = cognitive_result["student_level"]
    gap = cognitive_result["cognitive_gap"]
    score = cognitive_result["cognitive_score"]
    
    if score >= 0.9:
        return f"Excellent! Your answer demonstrates {required.upper()} level thinking perfectly."
    
    if score >= 0.7:
        return f"Good cognitive alignment. You're thinking at the {student.upper()} level (required: {required.upper()})."
    
    if gap == "below_required":
        if cognitive_result["gap_severity"] >= 2:
            return f"Your answer shows {student.upper()} level thinking, but this question requires {required.upper()} level. Try to analyze, evaluate, or create rather than just recall."
        else:
            return f"Your answer is at {student.upper()} level, slightly below the required {required.upper()} level. Add more depth to your response."
    
    if gap == "above_required":
        return f"Your answer exceeds the required {required.upper()} level! Excellent critical thinking."
    
    # Matched but low score
    return f"Your answer matches the required {required.upper()} level, but could be more thorough. Add specific details and examples."


def batch_cognitive_analysis(questions_and_answers: List[Tuple[str, str]]) -> Dict:
    """
    Analyze multiple question-answer pairs.
    
    Args:
        questions_and_answers: List of (question, student_answer) tuples
    
    Returns:
        Dict: Aggregated statistics
    """
    results = []
    level_counts = {"remember": 0, "understand": 0, "apply": 0, "analyze": 0, "evaluate": 0, "create": 0}
    
    for q, a in questions_and_answers:
        result = cognitive_score(q, a)
        results.append(result)
        level_counts[result["student_level"]] += 1
    
    total = len(results)
    avg_score = sum(r["cognitive_score"] for r in results) / total if total > 0 else 0
    
    return {
        "total_analyzed": total,
        "average_cognitive_score": round(avg_score, 2),
        "level_distribution": level_counts,
        "level_percentages": {k: round(v/total*100, 2) for k, v in level_counts.items()},
        "detailed_results": results
    }


if __name__ == "__main__":
    # Test the cognitive scoring
    print("=" * 70)
    print("COGNITIVE ANALYSIS TEST")
    print("=" * 70)
    
    # Test Case 1: Low-level answer to high-level question
    question = "Evaluate the effectiveness of different database indexing strategies"
    answer = "B-tree indexing is used in databases"
    
    result = cognitive_score(question, answer)
    print(f"\n Question: {question}")
    print(f" Answer: {answer}")
    print(f"\n Results:")
    print(f"   Required level: {result['required_level']} (score: {result['required_score']})")
    print(f"   Student level: {result['student_level']} (score: {result['student_score']})")
    print(f"   Cognitive score: {result['cognitive_score']}")
    print(f"   Gap: {result['cognitive_gap']} (severity: {result['gap_severity']})")
    print(f"   Feedback: {get_cognitive_feedback(result)}")
    
    # Test Case 2: High-level answer
    question2 = "What is a primary key?"
    answer2 = "A primary key uniquely identifies each row in a table and cannot be null"
    
    result2 = cognitive_score(question2, answer2)
    print(f"\n Question: {question2}")
    print(f" Answer: {answer2}")
    print(f"\n Results:")
    print(f"   Required level: {result2['required_level']}")
    print(f"   Student level: {result2['student_level']}")
    print(f"   Cognitive score: {result2['cognitive_score']}")
    print(f"   Feedback: {get_cognitive_feedback(result2)}")