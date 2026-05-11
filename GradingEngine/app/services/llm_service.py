from groq import Groq
import os
import json
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
client = Groq(api_key=os.getenv("AI_API_KEY"))


def _sum_per_question_scores(evaluation_data: dict) -> float:
    """Recompute paper total from per-question scores (authoritative over model-reported total)."""
    results = evaluation_data.get("results") or []
    if not isinstance(results, list):
        return 0.0
    total = 0.0
    for item in results:
        if not isinstance(item, dict):
            continue
        raw = item.get("score", item.get("marks", 0))
        try:
            total += float(raw)
        except (TypeError, ValueError):
            continue
    return round(total, 4)


async def generate_grading_report(all_text, rubric_data):
    # rubric_data is the doc fetched from Mongo
    questions_list = rubric_data.get('questions', [])
    
    prompt = f"""
    SYSTEM: Expert University Grader.
    RUBRIC: {json.dumps(questions_list)}
    STUDENT TEXT: "{all_text}"
    
    TASK: Map text to questions, score semantically against question_text + criteria points, and return JSON ONLY.
    FORMAT: 
    {{
        "total_score": 0.0,
        "results": [
            {{
              "q_no": "01",
              "score": 0.0,
              "criteria_breakdown": [{{"point": "...", "awarded_marks": 0.0, "reason": "..."}}],
              "justification": "...",
              "feedback": "..."
            }}
        ]
    }}
    """

    completion = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    raw = (completion.choices[0].message.content or "").strip()
    evaluation_data = json.loads(raw) if raw else {}

    if not isinstance(evaluation_data, dict):
        evaluation_data = {"results": [], "raw_model_output": evaluation_data}

    real_total = _sum_per_question_scores(evaluation_data)
    evaluation_data["total_score"] = real_total

    return evaluation_data