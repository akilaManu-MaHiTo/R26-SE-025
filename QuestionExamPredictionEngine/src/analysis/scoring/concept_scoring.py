import re
from typing import List, Dict, Tuple

def extract_keywords(model_answer: str) -> List[str]:
    """
    Extract important keywords from model answer.
    
    Args:
        model_answer (str): The correct/model answer
    
    Returns:
        List[str]: Unique keywords extracted
    """
    # Remove symbols and special characters
    text = re.sub(r'[^a-zA-Z0-9 ]', '', model_answer.lower())
    
    # Split into words
    words = text.split()
    
    # Remove common stopwords and short words
    stopwords = {"the", "is", "are", "and", "of", "a", "to", "in", "for", "on", "with", "by", "at"}
    keywords = [w for w in words if w not in stopwords and len(w) > 3]
    
    # Remove duplicates while preserving some order (optional)
    seen = set()
    unique_keywords = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            unique_keywords.append(k)
    
    return unique_keywords


def concept_score(student_answer: str, keywords: List[str], use_word_boundary: bool = True) -> float:
    """
    Calculate concept score based on keyword matching.
    
    Args:
        student_answer (str): Student's answer
        keywords (List[str]): Keywords from model answer
        use_word_boundary (bool): Whether to use word boundary matching
    
    Returns:
        float: Concept score between 0 and 1
    """
    if not keywords:
        return 0.0
    
    student_text = student_answer.lower()
    matched = 0
    
    for k in keywords:
        if use_word_boundary:
            # Match whole words only
            if re.search(rf'\b{re.escape(k)}\b', student_text):
                matched += 1
            # Partial credit for word stems (e.g., "eliminate" vs "eliminates")
            elif len(k) > 5 and re.search(rf'\b{k[:-1]}[a-z]*\b', student_text):
                matched += 0.5
        else:
            # Simple substring matching (original behavior)
            if k in student_text:
                matched += 1
    
    score = matched / len(keywords)
    return min(score, 1.0)


def keyword_coverage_analysis(student_answer: str, keywords: List[str]) -> Dict:
    """
    Detailed analysis of which keywords were found/missing.
    
    Args:
        student_answer (str): Student's answer
        keywords (List[str]): Keywords from model answer
    
    Returns:
        Dict: Detailed coverage analysis
    """
    student_text = student_answer.lower()
    
    found = []
    missing = []
    partial = []
    
    for k in keywords:
        if re.search(rf'\b{re.escape(k)}\b', student_text):
            found.append(k)
        elif len(k) > 5 and re.search(rf'\b{k[:-1]}[a-z]*\b', student_text):
            partial.append(k)
        else:
            missing.append(k)
    
    return {
        "found": found,
        "missing": missing,
        "partial": partial,
        "found_count": len(found),
        "partial_count": len(partial),
        "missing_count": len(missing),
        "coverage_percentage": round((len(found) + 0.5 * len(partial)) / len(keywords) * 100, 2)
    }


# Optional: Add synonym support
SYNONYM_DICT = {
    "eliminates": ["removes", "deletes", "eradicates", "gets rid of"],
    "identifies": ["recognizes", "distinguishes", "detects"],
    "dependent": ["relies on", "depends on", "contingent on"],
    "attribute": ["property", "field", "column", "characteristic"]
}

def concept_score_with_synonyms(student_answer: str, keywords: List[str]) -> float:
    """
    Enhanced concept scoring with synonym matching.
    
    Args:
        student_answer (str): Student's answer
        keywords (List[str]): Keywords from model answer
    
    Returns:
        float: Concept score between 0 and 1
    """
    if not keywords:
        return 0.0
    
    student_text = student_answer.lower()
    matched = 0
    
    for k in keywords:
        # Check exact match
        if re.search(rf'\b{re.escape(k)}\b', student_text):
            matched += 1
            continue
        
        # Check synonyms
        synonyms_found = False
        if k in SYNONYM_DICT:
            for syn in SYNONYM_DICT[k]:
                if re.search(rf'\b{re.escape(syn)}\b', student_text):
                    matched += 1
                    synonyms_found = True
                    break
        
        # Partial credit for stems
        if not synonyms_found and len(k) > 5:
            if re.search(rf'\b{k[:-1]}[a-z]*\b', student_text):
                matched += 0.5
    
    return min(matched / len(keywords), 1.0)